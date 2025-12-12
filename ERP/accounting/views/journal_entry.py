import json
import logging
import os
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounting.config.settings import journal_entry_settings
from accounting.models import (
    AccountingPeriod,
    Attachment,
    ChartOfAccount,
    CostCenter,
    Currency,
    Department,
    Journal,
    JournalDebugPreference,
    JournalLine,
    JournalType,
    PaymentTerm,
    Project,
    TaxCode,
    VoucherModeConfig,
    VoucherUDFConfig,
    VoucherUIPreference,
    default_ui_schema,
)
from accounting.services.journal_entry_service import JournalEntryService
from usermanagement.utils import PermissionUtils
from utils.calendars import DateSeedStrategy
from utils.file_uploads import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_UPLOAD_BYTES,
    iter_validated_files,
)

logger = logging.getLogger(__name__)


STATUS_LABELS = {
    "draft": "Draft",
    "awaiting_approval": "Awaiting Approval",
    "approved": "Approved",
    "posted": "Posted",
    "rejected": "Rejected",
}


HEADER_STATE_KEY_MAP = {
    "journal_date": "date",
    "journal_type": "journalTypeCode",
    "reference_number": "reference",
    "description": "description",
    "currency": "currency",
    "branch": "branch",
}

LINE_STATE_KEY_MAP = {
    "description": "narr",
    "debit_amount": "dr",
    "credit_amount": "cr",
    "cost_center": "costCenter",
    "project": "project",
    "department": "department",
    "tax_code": "taxCode",
}

WORKFLOW_PERMISSION_RULES = {
    "submit": ("can_submit_for_approval", "submit_journal"),
    "approve": ("can_approve_journal", "approve_journal"),
    "reject": ("can_reject_journal", "reject_journal"),
    "post": ("can_post_journal", "post_journal"),
}


LINE_COLUMN_DEFAULTS = [
    {"key": "account", "default_label": "Account", "default_visible": True, "order": 0, "css_class": "text-start", "configurable": True},
    {"key": "description", "default_label": "Description", "default_visible": True, "order": 1, "css_class": "text-start", "configurable": True},
    {"key": "dr", "default_label": "Debit", "default_visible": True, "order": 2, "css_class": "text-end", "configurable": True},
    {"key": "cr", "default_label": "Credit", "default_visible": True, "order": 3, "css_class": "text-end", "configurable": True},
    {"key": "costCenter", "default_label": "Cost Center", "default_visible": True, "order": 4, "css_class": "text-start", "configurable": True},
    {"key": "project", "default_label": "Project", "default_visible": True, "order": 5, "css_class": "text-start", "configurable": True},
    {"key": "department", "default_label": "Department", "default_visible": True, "order": 6, "css_class": "text-start", "configurable": True},
    {"key": "taxCode", "default_label": "Tax Code", "default_visible": True, "order": 7, "css_class": "text-start", "configurable": True},
    {"key": "actions", "default_label": "", "default_visible": True, "order": 999, "css_class": "text-end", "configurable": False},
]


def _voucher_ui_preferences_for_user(user, organization, scope="voucher_entry"):
    if not user or not organization:
        return {}
    preference = (
        VoucherUIPreference.objects.filter(user=user, organization=organization, scope=scope)
        .first()
    )
    if preference and isinstance(preference.data, dict):
        return preference.data
    return {}


def _ui_settings_from_config(config):
    if not config:
        return default_ui_schema().get("settings", {})
    ui = config.resolve_ui() if hasattr(config, "resolve_ui") else {}
    settings = ui.get("settings") if isinstance(ui, dict) else None
    if settings:
        return settings
    return default_ui_schema().get("settings", {})


def _resolve_prefill_value(definition, config):
    if definition is None:
        return None
    if isinstance(definition, dict):
        if "value" in definition:
            return definition["value"]
        source = definition.get("source")
        if source == "default_cost_center" and getattr(config, "default_cost_center", None):
            return config.default_cost_center.code
        if source == "default_tax_ledger" and getattr(config, "default_tax_ledger", None):
            return config.default_tax_ledger.account_code
        if source == "default_ledger" and getattr(config, "default_ledger", None):
            return config.default_ledger.account_code
        if source == "default_currency" and getattr(config, "default_currency", None):
            return config.default_currency
        return definition.get("value")
    return definition


def _apply_prefill_defaults(target, prefill_defs, config):
    if not isinstance(prefill_defs, dict):
        return
    for key, definition in prefill_defs.items():
        value = _resolve_prefill_value(definition, config)
        if value is not None:
            target[key] = value


def _apply_required_overrides(required_map, required_keys):
    if not isinstance(required_keys, (list, tuple)):
        return
    for key in required_keys:
        if not isinstance(key, str):
            continue
        required_map[key] = True


def _line_columns_from_preferences(line_labels, preferences):
    catalog: List[Dict[str, Any]] = []
    pref_columns = preferences.get("lineColumns") if isinstance(preferences, dict) else []
    pref_map = {}
    if isinstance(pref_columns, list):
        for entry in pref_columns:
            if isinstance(entry, dict) and entry.get("key"):
                pref_map[entry["key"]] = entry
    for base in LINE_COLUMN_DEFAULTS:
        label = line_labels.get(base["key"]) or base["default_label"]
        column = {
            "key": base["key"],
            "label": label,
            "visible": base["default_visible"],
            "order": base["order"],
            "css_class": base.get("css_class", ""),
            "configurable": base.get("configurable", True),
        }
        if base["key"] in pref_map and column["configurable"]:
            pref_entry = pref_map[base["key"]]
            if "visible" in pref_entry:
                column["visible"] = bool(pref_entry["visible"])
            if "order" in pref_entry:
                try:
                    column["order"] = int(pref_entry["order"])
                except (TypeError, ValueError):
                    pass
        catalog.append(column)
    catalog.sort(key=lambda item: item["order"])
    visible = [col for col in catalog if col["visible"]]
    density = preferences.get("density") or preferences.get("lineDensity") or "comfortable"
    return {"visible": visible, "catalog": catalog, "density": density}


def _line_layout_for_request(request, line_labels):
    organization = _active_organization(request.user)
    preferences = _voucher_ui_preferences_for_user(request.user, organization)
    return _line_columns_from_preferences(line_labels, preferences)

def _state_key_for_header(field_key: str) -> str:
    return HEADER_STATE_KEY_MAP.get(field_key, field_key)


def _state_key_for_line(field_key: str) -> str:
    return LINE_STATE_KEY_MAP.get(field_key, field_key)


def _choices_for_model(label: str, organization) -> List[Dict[str, Any]]:
    if not label:
        return []
    normalized = label.lower()
    if normalized == "journaltype":
        qs = (
            JournalType.objects.filter(organization=organization, is_active=True)
            .order_by("name")
        )
        return [
            {"value": jt.code, "label": f"{jt.code} - {jt.name}", "id": jt.pk}
            for jt in qs
        ]
    if normalized == "currency":
        qs = Currency.objects.filter(is_active=True).order_by("currency_code")
        return [
            {"value": cur.currency_code, "label": f"{cur.currency_code} - {cur.currency_name}"}
            for cur in qs
        ]
    if normalized == "costcenter":
        qs = CostCenter.objects.filter(organization=organization, is_active=True).order_by("code")
        return [
            {"value": str(cc.pk), "label": f"{cc.code} - {cc.name}", "code": cc.code}
            for cc in qs
        ]
    if normalized == "department":
        qs = Department.objects.filter(organization=organization, archived_at__isnull=True).order_by("code")
        return [
            {"value": str(dep.pk), "label": f"{dep.code} - {dep.name}", "code": dep.code}
            for dep in qs
        ]
    if normalized == "project":
        qs = Project.objects.filter(organization=organization, archived_at__isnull=True).order_by("code")
        return [
            {"value": str(project.pk), "label": f"{project.code} - {project.name}", "code": project.code}
            for project in qs
        ]
    if normalized == "taxcode":
        qs = TaxCode.objects.filter(organization=organization, is_active=True).order_by("code")
        return [
            {"value": str(code.pk), "label": f"{code.code} - {code.name}", "code": code.code}
            for code in qs
        ]
    if normalized == "chartofaccount":
        # Accounts are resolved through lookups in the UI; avoid dumping the chart here.
        return []
    return []


def _normalize_choices(raw_choices: Any, organization) -> List[Any]:
    if not raw_choices:
        return []
    if isinstance(raw_choices, str):
        return _choices_for_model(raw_choices, organization)
    if isinstance(raw_choices, dict):
        return [
            {"value": str(value), "label": str(label)}
            for value, label in raw_choices.items()
        ]
    if isinstance(raw_choices, (list, tuple)):
        normalized: List[Any] = []
        for item in raw_choices:
            if isinstance(item, dict):
                value = item.get("value")
                normalized.append(
                    {
                        **item,
                        "value": "" if value is None else str(value),
                    }
                )
            else:
                normalized.append({"value": str(item), "label": str(item)})
        return normalized
    return []


def _allowed_values_from_choices(choices: List[Any]) -> Optional[set]:
    if not choices:
        return None
    allowed: set = set()
    for choice in choices:
        if isinstance(choice, dict):
            value = choice.get("value")
            if value is not None and value != "":
                allowed.add(str(value))
        else:
            allowed.add(str(choice))
    return allowed or None

def _get_json_query_param(request, key: str) -> Any:
    value = request.GET.get(key)
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _journal_type_param_from_request(request) -> Optional[str]:
    return (
        request.GET.get("journal_type")
        or request.GET.get("journalType")
        or request.GET.get("journal_type_code")
        or request.GET.get("journalTypeCode")
    )


def _line_schema_context(organization, journal_type_param):
    config = _resolve_voucher_config(organization, journal_type_param)
    schema_source = config.resolve_ui() if config else default_ui_schema()
    settings = _ui_settings_from_config(config)
    raw_line_schema = schema_source.get("lines", {})
    (
        line_schema,
        line_allowed,
        line_required,
        line_defaults,
        line_labels,
    ) = _serialize_line_schema(raw_line_schema, organization)
    prefill_settings = (settings.get("prefill") or {}).get("lines") or {}
    _apply_prefill_defaults(line_defaults, prefill_settings, config)
    required_keys = (settings.get("required_fields") or {}).get("lines") or []
    _apply_required_overrides(line_required, required_keys)
    return config, line_schema, line_allowed, line_required, line_defaults, line_labels


def _header_schema_context(organization, journal_type_param):
    config = _resolve_voucher_config(organization, journal_type_param)
    schema_source = config.resolve_ui() if config else default_ui_schema()
    settings = _ui_settings_from_config(config)
    raw_header_schema = schema_source.get("header", {})
    (
        header_schema,
        header_allowed,
        header_required,
        header_defaults,
        header_labels,
    ) = _serialize_header_schema(raw_header_schema, organization)
    prefill_settings = (settings.get("prefill") or {}).get("header") or {}
    _apply_prefill_defaults(header_defaults, prefill_settings, config)
    required_keys = (settings.get("required_fields") or {}).get("header") or []
    _apply_required_overrides(header_required, required_keys)
    return config, header_schema, header_allowed, header_required, header_defaults, header_labels


def _float_or_zero(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return 0.0


def _sum_totals_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    dr_total = 0.0
    cr_total = 0.0
    for row in rows:
        dr_total += _float_or_zero(row.get("dr") or row.get("debit") or row.get("debit_amount"))
        cr_total += _float_or_zero(row.get("cr") or row.get("credit") or row.get("credit_amount"))
    diff = dr_total - cr_total
    return {"dr": dr_total, "cr": cr_total, "diff": diff}


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _merge_line_row_data(row: Optional[Dict[str, Any]], defaults: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(defaults)
    if isinstance(row, dict):
        for key, value in row.items():
            if value is not None:
                merged[key] = value
    return merged


def _rows_for_validation(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "account": row.get("accountCode") or row.get("account") or "",
                "description": row.get("narr") or row.get("description") or "",
                "debit_amount": row.get("dr") or row.get("debit") or row.get("debit_amount") or 0,
                "credit_amount": row.get("cr") or row.get("credit") or row.get("credit_amount") or 0,
            }
        )
    return normalized


def _header_for_validation(header_values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not header_values:
        return {"journal_date": None, "description": ""}
    return {
        "journal_date": header_values.get("date")
        or header_values.get("journal_date")
        or header_values.get("journalDate"),
        "description": header_values.get("description") or "",
    }


def _journal_type_token_from_header(header_values: Optional[Dict[str, Any]]) -> Optional[str]:
    if not header_values:
        return None
    for key in (
        "journalTypeId",
        "journalTypeCode",
        "journalType",
        "journal_type",
        "journal_type_id",
    ):
        value = header_values.get(key)
        if value:
            return str(value)
    return None


def _render_line_row_html(
    request,
    row_index: int,
    line_defaults: Dict[str, Any],
    line_labels: Dict[str, str],
    line_columns: List[Dict[str, Any]],
    row_data: Optional[Dict[str, Any]] = None,
) -> str:
    merged_row = _merge_line_row_data(row_data, line_defaults)
    context = {
        "row": merged_row,
        "index": row_index,
        "line_labels": line_labels,
        "line_columns": line_columns,
        "lookup_urls": _journal_lookup_urls(),
        "row_json": json.dumps(merged_row),
    }
    return render_to_string(
        "accounting/partials/journal_entry_line_row.html",
        context,
        request=request,
    )


def _render_lines_fragment(
    request,
    rows: List[Dict[str, Any]],
    line_labels: Dict[str, str],
) -> str:
    lookup_urls = _journal_lookup_urls()
    try:
        add_row_endpoint = reverse("accounting:journal_entry_add_row")
    except Exception:
        add_row_endpoint = "/accounting/journal-entry/add-row/"
    line_layout = _line_layout_for_request(request, line_labels)
    column_metadata = {
        "catalog": line_layout["catalog"],
        "density": line_layout["density"],
    }
    context = {
        "rows": rows,
        "line_labels": line_labels,
        "lookup_urls": lookup_urls,
        "add_row_endpoint": add_row_endpoint,
        "line_columns": line_layout["visible"],
        "line_density": line_layout["density"],
        "column_catalog_json": json.dumps(column_metadata),
    }
    return render_to_string(
        "accounting/partials/journal_entry_lines_partial.html",
        context,
        request=request,
    )


def _suspense_account_for_config(config: Optional[VoucherModeConfig]) -> str:
    settings = _ui_settings_from_config(config)
    auto_balance = settings.get("auto_balance", {})
    default_account = auto_balance.get("default_account")
    if default_account:
        return default_account
    if config and getattr(config, "default_ledger", None):
        try:
            return config.default_ledger.account_code
        except Exception:
            pass
    return journal_entry_settings.default_accounts.get("suspense") or journal_entry_settings.default_accounts.get("accounts_payable") or "99999"


def _serialize_header_schema(raw_schema: Dict[str, Any], organization):
    serialized: Dict[str, Dict[str, Any]] = {}
    allowed_map: Dict[str, set] = {}
    required_map: Dict[str, bool] = {}
    defaults: Dict[str, Any] = {}
    labels: Dict[str, str] = {}
    for key, definition in (raw_schema or {}).items():
        if not isinstance(definition, dict):
            continue
        entry: Dict[str, Any] = {
            "label": definition.get("label") or key.replace("_", " ").title(),
            "type": definition.get("type") or "text",
        }
        labels[_state_key_for_header(key)] = entry["label"]
        if definition.get("required"):
            entry["required"] = True
            required_map[_state_key_for_header(key)] = True
        if definition.get("placeholder"):
            entry["placeholder"] = definition["placeholder"]
        if definition.get("help_text"):
            entry["helpText"] = definition["help_text"]
        choices = _normalize_choices(definition.get("choices"), organization)
        if choices:
            entry["choices"] = choices
            allowed = _allowed_values_from_choices(choices)
            if allowed:
                allowed_map[_state_key_for_header(key)] = allowed
        default_value = definition.get("default")
        if default_value not in (None, ""):
            entry["default"] = default_value
            defaults[_state_key_for_header(key)] = default_value
        serialized[key] = entry
    return serialized, allowed_map, required_map, defaults, labels


def _serialize_line_schema(raw_schema: Dict[str, Any], organization):
    serialized: Dict[str, Dict[str, Any]] = {}
    allowed_map: Dict[str, set] = {}
    required_map: Dict[str, bool] = {}
    defaults: Dict[str, Any] = {}
    labels: Dict[str, str] = {}
    for key, definition in (raw_schema or {}).items():
        if not isinstance(definition, dict):
            continue
        entry: Dict[str, Any] = {
            "label": definition.get("label") or key.replace("_", " ").title(),
            "type": definition.get("type") or "text",
        }
        labels[_state_key_for_line(key)] = entry["label"]
        if definition.get("required"):
            entry["required"] = True
            required_map[_state_key_for_line(key)] = True
        if definition.get("placeholder"):
            entry["placeholder"] = definition["placeholder"]
        if definition.get("help_text"):
            entry["helpText"] = definition["help_text"]
        choices = _normalize_choices(definition.get("choices"), organization)
        if choices:
            entry["choices"] = choices
            allowed = _allowed_values_from_choices(choices)
            if allowed:
                allowed_map[_state_key_for_line(key)] = allowed
        default_value = definition.get("default")
        if default_value not in (None, ""):
            entry["default"] = default_value
            defaults[_state_key_for_line(key)] = default_value
        serialized[key] = entry
    return serialized, allowed_map, required_map, defaults, labels


def _collect_udf_definitions(config: Optional[VoucherModeConfig]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not config:
        return [], []
    header_defs: List[Dict[str, Any]] = []
    line_defs: List[Dict[str, Any]] = []
    qs = config.udf_configs.filter(is_active=True, archived_at__isnull=True).order_by("scope", "display_order", "field_name")
    for udf in qs:
        entry: Dict[str, Any] = {
            "id": udf.field_name,
            "label": udf.display_name,
            "type": {
                "decimal": "number",
                "number": "number",
                "date": "date",
                "datetime": "datetime-local",
                "email": "email",
                "phone": "tel",
                "url": "url",
                "textarea": "textarea",
                "multiselect": "multiselect",
                "checkbox": "checkbox",
                "select": "select",
            }.get(udf.field_type, "text"),
            "required": udf.is_required,
        }
        if udf.default_value not in (None, ""):
            entry["default"] = udf.default_value
        if udf.choices:
            entry["options"] = (
                udf.choices
                if isinstance(udf.choices, list)
                else list(udf.choices.values()) if isinstance(udf.choices, dict) else []
            )
        target = header_defs if udf.scope == "header" else line_defs
        target.append(entry)
    return header_defs, line_defs


def _build_numbering_metadata(config: Optional[VoucherModeConfig]) -> Optional[Dict[str, Any]]:
    if not config or not config.journal_type:
        return None
    jt = config.journal_type
    prefix = jt.auto_numbering_prefix or jt.code or "JV"
    next_seq = int(jt.sequence_next or 1)
    width = max(len(str(next_seq)), 4)
    return {
        "prefix": {"Journal": prefix},
        "nextSeq": {"Journal": next_seq},
        "width": width,
        "fiscalYearPrefix": bool(jt.fiscal_year_prefix),
    }


def _resolve_voucher_config(organization, journal_type_param: Optional[str]) -> Optional[VoucherModeConfig]:
    qs = (
        VoucherModeConfig.objects.filter(organization=organization, is_active=True)
        .select_related("journal_type")
        .order_by("-is_default", "name")
    )
    journal_type = None
    token = (journal_type_param or "").strip()
    if token:
        if token.isdigit():
            journal_type = JournalType.objects.filter(organization=organization, pk=int(token)).first()
        if journal_type is None:
            journal_type = JournalType.objects.filter(organization=organization, code__iexact=token).first()
    if journal_type:
        config = qs.filter(journal_type=journal_type).first()
        if config:
            return config
    config = qs.filter(is_default=True).first()
    if config:
        return config
    return qs.first()


def _journal_lookup_urls():
    urls = {}
    try:
        urls["account"] = reverse('accounting:journal_account_lookup')
    except Exception:
        urls["account"] = '/accounting/journal-entry/lookup/accounts/'
    try:
        urls["costCenter"] = reverse('accounting:journal_cost_center_lookup')
    except Exception:
        urls["costCenter"] = '/accounting/journal-entry/lookup/cost-centers/'
    return urls


def _parse_row_payload(request) -> Dict[str, Any]:
    raw = request.POST.get("row") or request.GET.get("row")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _load_config_for_payload(organization, metadata: Dict[str, Any]) -> Optional[VoucherModeConfig]:
    if not organization:
        return None
    if not isinstance(metadata, dict):
        metadata = {}
    config_id = metadata.get("configId") or metadata.get("config_id")
    if config_id:
        try:
            return (
                VoucherModeConfig.objects.select_related("journal_type")
                .filter(organization=organization)
                .get(config_id=int(config_id))
            )
        except (VoucherModeConfig.DoesNotExist, ValueError, TypeError):
            pass
    journal_type_token = (
        metadata.get("journalTypeId")
        or metadata.get("journalTypeCode")
        or metadata.get("journal_type")
    )
    if journal_type_token:
        return _resolve_voucher_config(organization, str(journal_type_token))
    return _resolve_voucher_config(organization, None)


def _validate_header_values(
    header: Dict[str, Any],
    required_map: Dict[str, bool],
    allowed_map: Dict[str, set],
    labels: Dict[str, str],
):
    for key, required in required_map.items():
        if not required:
            continue
        value = header.get(key)
        if value is None:
            raise ValueError(f"{labels.get(key, key)} is required by the selected configuration.")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{labels.get(key, key)} is required by the selected configuration.")
    for key, allowed in allowed_map.items():
        if not allowed:
            continue
        value = header.get(key)
        if value in (None, ""):
            continue
        value_str = value.strip() if isinstance(value, str) else str(value)
        if value_str not in allowed:
            raise ValueError(f"Value '{value}' is not permitted for {labels.get(key, key)}.")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _active_organization(user):
    if hasattr(user, "get_active_organization"):
        org = user.get_active_organization()
        if org:
            return org
    return getattr(user, "organization", None)


def _base_currency_code(organization) -> Optional[str]:
    if not organization:
        return None
    code = getattr(organization, "base_currency_code_id", None)
    if code:
        return code
    base_currency = getattr(organization, "base_currency_code", None)
    return getattr(base_currency, "currency_code", None)


def _supported_currencies(organization) -> List[str]:
    supported = list(journal_entry_settings.supported_currencies or [])
    base_code = _base_currency_code(organization)
    if base_code and base_code not in supported:
        supported.insert(0, base_code)
    return supported


def _seed_default_date(organization) -> str:
    today = timezone.localdate() if hasattr(timezone, "localdate") else timezone.now().date()
    strategy = DateSeedStrategy.DEFAULT
    cfg = getattr(organization, "config", None) if organization else None
    if cfg:
        strategy = DateSeedStrategy.normalize(getattr(cfg, "calendar_date_seed", None))
    if organization and strategy == DateSeedStrategy.LAST_OR_TODAY:
        try:
            last_date = (
                Journal.objects.filter(organization=organization)
                .exclude(journal_date__isnull=True)
                .order_by("-journal_date")
                .values_list("journal_date", flat=True)
                .first()
            )
            if last_date:
                return last_date.isoformat()
        except Exception:
            pass
    return today.isoformat()


def _is_journal_debug_enabled(organization) -> bool:
    return JournalDebugPreference.is_enabled_for(organization)


def _issue_debug_token(action: str, user, organization) -> Optional[str]:
    if not _is_journal_debug_enabled(organization):
        return None
    token = uuid.uuid4().hex[:12]
    org_id = getattr(organization, "pk", None)
    logger.info(
        "journal_debug_token=%s action=%s user=%s org=%s",
        token,
        action,
        getattr(user, "pk", None),
        org_id,
    )
    return token


def _user_can_workflow(user, organization, action: str) -> bool:
    if not organization:
        return False
    rule = WORKFLOW_PERMISSION_RULES.get(action)
    if not rule:
        return False
    global_perm, scoped_perm = rule
    # Respect both Django model perms and tenant-scoped permissions.
    if user.has_perm(f"accounting.{global_perm}"):
        return True
    return PermissionUtils.has_permission(user, organization, "accounting", "journal", scoped_perm)


def _parse_request_json(request) -> Dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON payload") from exc


def _json_error(
    message: str,
    status: int = 400,
    details: Optional[Dict[str, Any]] = None,
    debug_token: Optional[str] = None,
) -> JsonResponse:
    payload: Dict[str, Any] = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    if debug_token:
        payload["debugToken"] = debug_token
    return JsonResponse(payload, status=status)


def _format_value_error(exc: ValueError) -> Tuple[str, Optional[Dict[str, Any]]]:
    details: Optional[Dict[str, Any]] = None
    message = str(exc)
    if exc.args:
        first = exc.args[0]
        if isinstance(first, (list, tuple)):
            details = {"errors": list(first)}
            message = "Validation failed."
    return message, details


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid numeric value '{value}'") from exc


def _resolve_journal_type(organization, metadata: Dict[str, Any]) -> JournalType:
    if metadata is None:
        metadata = {}

    jt_id = metadata.get("journalTypeId")
    if jt_id:
        try:
            return JournalType.objects.get(pk=jt_id, organization=organization)
        except JournalType.DoesNotExist as exc:
            raise ValueError("Selected journal type does not exist.") from exc

    code = metadata.get("journalTypeCode")
    if code:
        jt = JournalType.objects.filter(organization=organization, code__iexact=code).first()
        if jt:
            return jt
        raise ValueError(f"Journal type '{code}' is not available for this organization.")

    default_code = journal_entry_settings.ui_settings.get("default_entry_type") or "JN"
    jt = JournalType.objects.filter(organization=organization, code__iexact=default_code).first()
    if jt:
        return jt

    jt = JournalType.objects.filter(organization=organization).first()
    if jt:
        return jt

    raise ValueError("No journal types configured. Please create a journal type first.")


def _resolve_period(organization, journal_date) -> AccountingPeriod:
    period = (
        AccountingPeriod.objects.select_related("fiscal_year")
        .filter(
            organization=organization,
            start_date__lte=journal_date,
            end_date__gte=journal_date,
            status="open",
        )
        .first()
    )
    if not period:
        raise ValueError("No open accounting period covers the supplied journal date.")
    return period


def _resolve_account(organization, row: Dict[str, Any]) -> ChartOfAccount:
    account_id = row.get("accountId") or row.get("account_id")
    if account_id:
        try:
            return ChartOfAccount.objects.get(pk=int(account_id), organization=organization)
        except (ChartOfAccount.DoesNotExist, ValueError) as exc:
            raise ValueError(f"Account with id '{account_id}' does not exist.") from exc

    for key in ("accountCode", "account"):
        token = row.get(key)
        if not token:
            continue
        token = str(token).strip()
        if not token:
            continue
        code = token.split(" ", 1)[0] if " - " in token else token
        account = ChartOfAccount.objects.filter(organization=organization, account_code__iexact=code).first()
        if account:
            return account

    name = row.get("accountName")
    if name:
        account = ChartOfAccount.objects.filter(organization=organization, account_name__iexact=name.strip()).first()
        if account:
            return account

    raise ValueError(f"Account '{row.get('account') or row.get('accountCode')}' could not be resolved.")


def _resolve_cost_center(organization, row: Dict[str, Any]) -> Optional[CostCenter]:
    center_id = row.get("costCenterId") or row.get("cost_center_id")
    if center_id:
        try:
            return CostCenter.objects.get(pk=int(center_id), organization=organization)
        except (CostCenter.DoesNotExist, ValueError):
            return None

    token = row.get("costCenter")
    if token:
        token = str(token).strip()
        if token:
            center = CostCenter.objects.filter(organization=organization, code__iexact=token).first()
            if center:
                return center
            center = CostCenter.objects.filter(organization=organization, name__iexact=token).first()
            if center:
                return center
    return None


def _resolve_dimension(model, organization, value: Any) -> Optional[Any]:
    if value is None:
        return None
    token = str(value).strip()
    if not token:
        return None
    qs = model.objects.filter(organization=organization)
    try:
        return qs.get(pk=int(token))
    except (ValueError, model.DoesNotExist):
        pass
    obj = qs.filter(code__iexact=token).first()
    if obj:
        return obj
    return qs.filter(name__iexact=token).first()


def _build_lines(
    rows: List[Dict[str, Any]],
    organization,
    udf_line_defs: List[Dict[str, Any]],
    required_map: Optional[Dict[str, bool]] = None,
    allowed_map: Optional[Dict[str, set]] = None,
    labels: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    required_map = required_map or {}
    allowed_map = allowed_map or {}
    labels = labels or {}

    def _label_for(key: str) -> str:
        return labels.get(key, key.replace("_", " ").title())

    def _row_value(row: Dict[str, Any], key: str):
        if key in row and row[key] not in (None, ""):
            return row[key]
        alternatives = (f"{key}Id", f"{key}_id")
        for alt in alternatives:
            if alt in row and row[alt] not in (None, ""):
                return row[alt]
        return row.get(key)

    def _ensure_required(row: Dict[str, Any], key: str):
        if not required_map.get(key):
            return
        value = _row_value(row, key)
        if value is None:
            raise ValueError(f"{_label_for(key)} is required for each journal line.")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{_label_for(key)} is required for each journal line.")

    def _ensure_allowed(row: Dict[str, Any], key: str):
        allowed = allowed_map.get(key)
        if not allowed:
            return
        value = _row_value(row, key)
        if value in (None, ""):
            return
        value_str = str(value).strip()
        if value_str not in allowed:
            raise ValueError(f"Value '{value}' is not permitted for {_label_for(key)}.")

    for row in rows:
        debit = _safe_decimal(row.get("dr"))
        credit = _safe_decimal(row.get("cr"))
        account_fields = (row.get("account"), row.get("accountCode"), row.get("accountId"))

        if not any(account_fields) and debit == 0 and credit == 0:
            continue

        line_number = len(prepared) + 1

        for key in required_map.keys():
            _ensure_required(row, key)
        for key in allowed_map.keys():
            _ensure_allowed(row, key)

        account = _resolve_account(organization, row)

        line_payload: Dict[str, Any] = {
            "line_number": line_number,
            "account": account,
            "description": (row.get("narr") or "").strip(),
            "debit_amount": debit,
            "credit_amount": credit,
        }

        cost_center = _resolve_cost_center(organization, row)
        if cost_center:
            line_payload["cost_center"] = cost_center

        project = _resolve_dimension(Project, organization, row.get("project") or row.get("projectId") or row.get("project_id"))
        if project:
            line_payload["project"] = project

        department = _resolve_dimension(Department, organization, row.get("department") or row.get("departmentId") or row.get("department_id"))
        if department:
            line_payload["department"] = department

        tax_code = _resolve_dimension(TaxCode, organization, row.get("tax_code") or row.get("taxCode") or row.get("taxCodeId"))
        if tax_code:
            line_payload["tax_code"] = tax_code

        udf_values: Dict[str, Any] = {}
        for udf_def in udf_line_defs or []:
            field_id = udf_def.get("id")
            if not field_id:
                continue
            if field_id in row and row[field_id] not in (None, ""):
                udf_values[field_id] = row[field_id]

        if udf_values:
            line_payload["udf_data"] = udf_values

        prepared.append(line_payload)

    if not prepared:
        raise ValueError("At least one journal line with an account and amount is required.")

    return prepared


def _prepare_journal_components(user, payload: Dict[str, Any]) -> Tuple[Any, Dict[str, Any], List[Dict[str, Any]], List[Any]]:
    organization = _active_organization(user)
    if not organization:
        raise ValueError("An active organization is required to work with journal entries.")
    supported_currencies = _supported_currencies(organization)

    header = payload.get("header") or {}
    metadata = payload.get("meta") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    config = _load_config_for_payload(organization, metadata)
    if config and config.journal_type:
        metadata.setdefault("journalTypeId", config.journal_type.pk)
        metadata.setdefault("journalTypeCode", config.journal_type.code)
    if header.get('branch') and 'branch' not in metadata:
        metadata['branch'] = header.get('branch')

    date_value = header.get("date")
    journal_date = parse_date(date_value) if date_value else None
    if not journal_date:
        raise ValueError("Journal date is required.")

    schema_source = config.resolve_ui() if config else default_ui_schema()
    raw_header_schema = schema_source.get("header") or {}
    raw_line_schema = schema_source.get("lines") or {}
    (
        _header_schema_payload,
        header_allowed,
        header_required,
        header_defaults,
        header_labels,
    ) = _serialize_header_schema(raw_header_schema, organization)
    (
        _line_schema_payload,
        line_allowed,
        line_required,
        line_defaults,
        line_labels,
    ) = _serialize_line_schema(raw_line_schema, organization)

    for state_key, default_value in header_defaults.items():
        header.setdefault(state_key, default_value)
    if config and config.default_currency:
        header.setdefault("currency", config.default_currency)

    _validate_header_values(header, header_required, header_allowed, header_labels)

    journal_type = _resolve_journal_type(organization, metadata)
    period = _resolve_period(organization, journal_date)

    currency = (
        header.get("currency")
        or (supported_currencies[0] if supported_currencies else "")
        or ""
    ).upper()
    exchange_rate = _safe_decimal(header.get("exRate"), Decimal("1"))

    notes = (payload.get("notes") or header.get("description") or "").strip()
    if not notes:
        notes = f"Journal entry on {journal_date.isoformat()}"

    reference = (
        header.get("reference")
        or header.get("invoiceNo")
        or metadata.get("reference")
        or ""
    )

    journal_data: Dict[str, Any] = {
        "journal_type": journal_type,
        "period": period,
        "journal_date": journal_date,
        "description": notes,
        "reference": reference,
        "currency_code": currency,
        "exchange_rate": exchange_rate,
        "status": "draft",
    }

    udf_header_defs = payload.get("udfHeaderDefs") or []
    udf_line_defs = payload.get("udfLineDefs") or []
    header_udf_values = {d.get('id'): header.get(d.get('id')) for d in udf_header_defs if d.get('id')}

    metadata_payload = {**metadata, "udfHeaderDefs": udf_header_defs, "udfLineDefs": udf_line_defs}
    if config:
        metadata_payload["configId"] = config.config_id
        metadata_payload["configCode"] = config.code
        metadata_payload["configName"] = config.name
    else:
        metadata_payload["configId"] = metadata.get("configId")
        metadata_payload["configCode"] = metadata.get("configCode")
        metadata_payload["configName"] = metadata.get("configName")
    numbering_meta = _build_numbering_metadata(config)
    if 'numbering' in payload:
        metadata_payload['numbering'] = payload['numbering']
    elif numbering_meta:
        metadata_payload['numbering'] = numbering_meta
    allowable_types = journal_entry_settings.allowable_journal_entry_types or []
    if allowable_types:
        metadata_payload["availableVoucherTypes"] = [entry.get("name") or entry.get("value") for entry in allowable_types]
    metadata_payload["supportedCurrencies"] = _supported_currencies(organization)
    header_extras = {}
    for key, value in header.items():
        if key not in {"party", "date", "currency", "exRate", "creditDays", "reference", "description", "branch"}:
            header_extras[key] = value
    if header_extras:
        metadata_payload["headerExtras"] = header_extras

    journal_data.update({
        "header_udf_data": {k: v for k, v in header_udf_values.items() if v not in (None, '')},
        "charges_data": payload.get("charges") or [],
        "metadata": metadata_payload,
    })

    rows = payload.get("rows") or []
    line_data = _build_lines(rows, organization, udf_line_defs, line_required, line_allowed, line_labels)

    attachments_raw = payload.get("attachments")
    attachments = attachments_raw if attachments_raw is not None else None

    return organization, journal_data, line_data, attachments


def _persist_journal_draft(user, payload: Dict[str, Any]) -> Tuple[Journal, bool]:
    organization, journal_data, line_data, attachments = _prepare_journal_components(user, payload)
    service = JournalEntryService(user, organization)

    journal_id = payload.get("journalId") or payload.get("journal_id")
    created = False
    if journal_id:
        try:
            journal = Journal.objects.select_related("organization").get(pk=int(journal_id), organization=organization)
        except (Journal.DoesNotExist, ValueError) as exc:
            raise ValueError("Journal entry not found.") from exc
        # Attachments are managed below to support re-linking existing uploads by id
        journal = service.update_journal_entry(journal, journal_data, line_data)
    else:
        # Create journal without attachments; we will associate uploaded files by id below
        journal = service.create_journal_entry(journal_data, line_data)
        created = True

    attachment_ids: List[int] = []
    if attachments is not None:
        for entry in attachments:
            if isinstance(entry, dict) and entry.get("id"):
                try:
                    attachment_ids.append(int(entry["id"]))
                except (TypeError, ValueError):
                    continue
        if attachment_ids:
            Attachment.objects.filter(journal=journal).exclude(pk__in=attachment_ids).delete()
            Attachment.objects.filter(
                pk__in=attachment_ids,
                journal__organization=organization,
            ).update(journal=journal)
        else:
            Attachment.objects.filter(journal=journal).delete()

    journal.refresh_from_db()
    return journal, created


def _serialize_line(line: JournalLine) -> Dict[str, Any]:
    account = line.account
    cost_center = line.cost_center
    project = line.project
    department = line.department
    tax_code = line.tax_code
    payload = {
        "id": line.pk,
        "accountId": account.pk if account else None,
        "accountCode": account.account_code if account else "",
        "accountName": account.account_name if account else "",
        "account": f"{account.account_code} - {account.account_name}" if account else "",
        "narr": line.description or "",
        "dr": float(line.debit_amount or 0),
        "cr": float(line.credit_amount or 0),
        "costCenterId": cost_center.pk if cost_center else None,
        "costCenter": cost_center.code if cost_center else "",
    }
    if project:
        payload["projectId"] = project.pk
        payload["project"] = str(project.pk)
        payload["projectLabel"] = project.code or project.name or ""
    if department:
        payload["departmentId"] = department.pk
        payload["department"] = str(department.pk)
        payload["departmentLabel"] = department.code or department.name or ""
    if tax_code:
        payload["taxCodeId"] = tax_code.pk
        payload["taxCode"] = str(tax_code.pk)
        payload["taxCodeLabel"] = tax_code.code or ""
    if line.udf_data:
        payload['udf'] = line.udf_data
    return payload


def _serialize_journal(journal: Journal) -> Dict[str, Any]:
    journal.refresh_from_db()
    lines = journal.lines.select_related("account", "cost_center", "project", "department", "tax_code").order_by("line_number")
    totals = {
        "dr": float(journal.total_debit or 0),
        "cr": float(journal.total_credit or 0),
    }
    totals["diff"] = float(totals["dr"] - totals["cr"])

    metadata = journal.metadata or {}
    if not isinstance(metadata, dict):
        metadata = {}
    udf_header_defs = metadata.get('udfHeaderDefs', [])
    udf_line_defs = metadata.get('udfLineDefs', [])
    header = {
        "date": journal.journal_date.isoformat(),
        "currency": journal.currency_code,
        "exRate": float(journal.exchange_rate or 1),
        "reference": journal.reference or "",
        "description": journal.description or "",
        "branch": metadata.get('branch', ''),
    }
    header_extras = metadata.get('headerExtras')
    if isinstance(header_extras, dict):
        header.update(header_extras)
    attachments = [
        {
            "id": att.pk,
            "name": att.file.name.split('/')[-1],
            "uploadedAt": att.uploaded_at.isoformat() if att.uploaded_at else None,
            "uploadedBy": att.uploaded_by_id,
        }
        for att in journal.attachments.all()
    ]

    charges = []
    for charge in journal.charges_data or []:
        try:
            value = float(charge.get("value", 0))
        except (TypeError, ValueError):
            value = 0.0
        charges.append(
            {
                "id": charge.get("id"),
                "label": charge.get("label", ""),
                "mode": charge.get("mode", "amount"),
                "value": value,
                "sign": charge.get("sign", 1),
            }
        )

    posted_by_id = getattr(journal, "posted_by_id", None)
    posted_by_name = None
    if posted_by_id and getattr(journal, "posted_by", None):
        posted_by_name = getattr(journal.posted_by, "get_full_name", None)
        if callable(posted_by_name):
            posted_by_name = posted_by_name() or journal.posted_by.get_username()
        else:
            posted_by_name = getattr(journal.posted_by, "username", None)

    is_editable = journal.status in ('draft', 'rejected') and not journal.is_locked

    return {
        "id": journal.pk,
        "number": journal.journal_number or "",
        "status": journal.status,
        "statusLabel": STATUS_LABELS.get(journal.status, journal.status.title()),
        "journalTypeCode": journal.journal_type.code if journal.journal_type else "",
        "header": header,
        "headerUdfValues": journal.header_udf_data or {},
        "charges": charges,
        "udfHeaderDefs": udf_header_defs,
        "udfLineDefs": udf_line_defs,
        "rows": [_serialize_line(line) for line in lines],
        "notes": journal.description or "",
        "totals": totals,
        "attachments": attachments,
        "metadata": metadata,
        "createdAt": journal.created_at.isoformat() if journal.created_at else None,
        "updatedAt": journal.updated_at.isoformat() if journal.updated_at else None,
        "isLocked": journal.is_locked,
        "editable": is_editable,
        "postedAt": journal.posted_at.isoformat() if journal.posted_at else None,
        "postedBy": posted_by_id,
        "postedByName": posted_by_name,
        "isReversal": journal.is_reversal,
        "reversalOfId": journal.reversal_of_id,
    }


def _get_user_journal(user, pk: int) -> Journal:
    organization = _active_organization(user)
    if not organization:
        raise ValueError("Active organization required.")
    try:
        return Journal.objects.select_related("journal_type").get(pk=pk, organization=organization)
    except Journal.DoesNotExist as exc:
        raise ValueError("Journal entry not found.") from exc


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@login_required
@require_GET
def journal_config(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    org_currency_code = _base_currency_code(organization)

    journal_type_param = (
        request.GET.get("journal_type")
        or request.GET.get("journalType")
        or request.GET.get("journal_type_code")
        or request.GET.get("journalTypeCode")
    )
    config_id_param = request.GET.get("config_id")
    config: Optional[VoucherModeConfig] = None
    if config_id_param:
        try:
            config = (
                VoucherModeConfig.objects.select_related("journal_type")
                .filter(organization=organization, is_active=True)
                .get(config_id=int(config_id_param))
            )
        except (VoucherModeConfig.DoesNotExist, ValueError, TypeError):
            config = None
    if not config:
        config = _resolve_voucher_config(organization, journal_type_param)
    schema_source = config.resolve_ui() if config else default_ui_schema()
    raw_header_schema = schema_source.get("header") or {}
    raw_line_schema = schema_source.get("lines") or {}

    (
        header_schema,
        header_allowed,
        header_required,
        header_defaults,
        header_labels,
    ) = _serialize_header_schema(raw_header_schema, organization)
    (
        line_schema,
        line_allowed,
        line_required,
        line_defaults,
        line_labels,
    ) = _serialize_line_schema(raw_line_schema, organization)

    header_udf_defs, line_udf_defs = _collect_udf_definitions(config)

    metadata: Dict[str, Any] = {
        "configId": config.config_id if config else None,
        "configCode": config.code if config else None,
        "configName": config.name if config else "Default",
        "journalTypeId": config.journal_type.pk if config and config.journal_type else None,
        "journalTypeCode": (
            config.journal_type.code
            if config and config.journal_type
            else journal_entry_settings.ui_settings.get("default_entry_type") or "JN"
        ),
        "defaultCurrency": (
            config.default_currency
            if config and config.default_currency
            else (
                org_currency_code
                or (journal_entry_settings.supported_currencies[0] if journal_entry_settings.supported_currencies else None)
            )
        ),
        "headerRequired": sorted([key for key, value in header_required.items() if value]),
        "lineRequired": sorted([key for key, value in line_required.items() if value]),
        "headerAllowedValues": {key: sorted(values) for key, values in header_allowed.items()},
        "lineAllowedValues": {key: sorted(values) for key, values in line_allowed.items()},
        "headerDefaults": header_defaults,
        "lineDefaults": line_defaults,
        "supportedCurrencies": _supported_currencies(organization),
        "headerLabels": header_labels,
        "lineLabels": line_labels,
    }
    # Ensure a seeded date default is always available for the UI
    metadata["headerDefaults"].setdefault("date", _seed_default_date(organization))

    numbering_meta = _build_numbering_metadata(config)
    if numbering_meta:
        metadata["numbering"] = numbering_meta

    allowable_types = journal_entry_settings.allowable_journal_entry_types or []
    voucher_type_labels = [entry.get("name") or entry.get("value") for entry in allowable_types] or ["Journal"]
    metadata["availableVoucherTypes"] = voucher_type_labels

    config_options = (
        VoucherModeConfig.objects.filter(organization=organization, is_active=True)
        .order_by("name")
        .values("config_id", "code", "name")
    )
    metadata["availableConfigs"] = [
        {"id": option["config_id"], "code": option["code"], "name": option["name"]}
        for option in config_options
    ]

    payload = {
        "id": config.config_id if config else None,
        "code": config.code if config else None,
        "name": config.name if config else "Default",
        "uiSchema": {
            "header": header_schema,
            "lines": line_schema,
        },
        "udf": {
            "header": header_udf_defs,
            "line": line_udf_defs,
        },
        "metadata": metadata,
    }

    return JsonResponse({"ok": True, "config": payload})


@login_required
@ensure_csrf_cookie
def journal_entry(request):
    """Render the Excel-like Journal Entry UI."""
    # Support both journal_id and voucher_id parameters (for legacy and new URLs)
    journal_id_param = request.GET.get("journal_id") or request.GET.get("voucher_id") or ""
    if journal_id_param and not journal_id_param.isdigit():
        journal_id_param = ""
    
    # Check if config_id is provided
    config_id_param = request.GET.get("config_id") or ""
    show_config_selector = not config_id_param and not journal_id_param

    organization = _active_organization(request.user)
    supported_currencies = _supported_currencies(organization)
    default_currency = supported_currencies[0] if supported_currencies else ""
    default_date = _seed_default_date(organization)
    base_currency = _base_currency_code(organization)
    
    # If no config was chosen and no journal is being edited, route to a dedicated
    # full-screen configuration selection page instead of an in-page modal.
    if show_config_selector:
        return journal_select_config(request)
    
    journal_type_token = _journal_type_param_from_request(request)
    config = _resolve_voucher_config(organization, journal_type_token)
    auto_balance_settings = _ui_settings_from_config(config).get("auto_balance", {})
    auto_balance_enabled = auto_balance_settings.get("enabled", True)

    permission_flags = {
        "can_submit": bool(request.user.has_perm('accounting.can_submit_for_approval') or (organization and PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'submit_journal'))),
        "can_approve": bool(request.user.has_perm('accounting.can_approve_journal') or (organization and PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'approve_journal'))),
        "can_reject": bool(request.user.has_perm('accounting.can_reject_journal') or (organization and PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'reject_journal'))),
        "can_post": bool(request.user.has_perm('accounting.can_post_journal') or (organization and PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'post_journal'))),
    }

    lookup_urls = {
        "account": reverse('accounting:journal_account_lookup'),
        "costCenter": reverse('accounting:journal_cost_center_lookup'),
    }

    # Compute config endpoint here (wrap reverse in try/except so template rendering
    # doesn't fail if the named URL is not available at template-evaluation time).
    preferences = _voucher_ui_preferences_for_user(request.user, organization)
    line_density = preferences.get("lineDensity") or preferences.get("density") or "comfortable"

    try:
        config_endpoint = reverse('accounting:journal_config')
    except Exception:
        # Fallback to the hard-coded path used by this app. This avoids template
        # level NoReverseMatch while we investigate why the named URL may not
        # be present at runtime (possible duplicate modules / import mismatch).
        config_endpoint = '/accounting/journal-entry/config/'
    try:
        prefs_endpoint = reverse('accounting:journal_ui_preferences')
        prefs_save_endpoint = reverse('accounting:journal_ui_preferences_save')
    except Exception:
        prefs_endpoint = '/accounting/journal-entry/prefs/'
        prefs_save_endpoint = '/accounting/journal-entry/prefs/'
    try:
        attachment_upload_endpoint = reverse('accounting:journal_attachment_upload')
        attachment_delete_endpoint = reverse('accounting:journal_attachment_delete')
    except Exception:
        attachment_upload_endpoint = '/accounting/journal-entry/attachments/upload/'
        attachment_delete_endpoint = '/accounting/journal-entry/attachments/delete/'
    try:
        payment_terms_endpoint = reverse('accounting:journal_payment_terms')
    except Exception:
        payment_terms_endpoint = '/accounting/journal-entry/payment-terms/'

    try:
        row_endpoint = reverse('accounting:journal_entry_row')
    except Exception:
        row_endpoint = '/accounting/journal-entry/row/'
    try:
        add_row_endpoint = reverse('accounting:journal_entry_add_row')
    except Exception:
        add_row_endpoint = '/accounting/journal-entry/add-row/'
    try:
        header_partial_endpoint = reverse('accounting:journal_entry_header_partial')
    except Exception:
        header_partial_endpoint = '/accounting/journal-entry/header-partial/'
    try:
        lines_partial_endpoint = reverse('accounting:journal_entry_lines_partial')
    except Exception:
        lines_partial_endpoint = '/accounting/journal-entry/lines-partial/'
    try:
        side_panel_endpoint = reverse('accounting:journal_entry_side_panel')
    except Exception:
        side_panel_endpoint = '/accounting/journal-entry/side-panel/'
    try:
        imbalance_bar_endpoint = reverse('accounting:journal_entry_imbalance_bar')
    except Exception:
        imbalance_bar_endpoint = '/accounting/journal-entry/imbalance-bar/'
    try:
        duplicate_row_endpoint = reverse('accounting:journal_entry_row_duplicate')
    except Exception:
        duplicate_row_endpoint = '/accounting/journal-entry/duplicate-row/'
    try:
        bulk_add_rows_endpoint = reverse('accounting:journal_entry_bulk_add')
    except Exception:
        bulk_add_rows_endpoint = '/accounting/journal-entry/bulk-add/'
    try:
        auto_balance_endpoint = reverse('accounting:journal_entry_auto_balance')
    except Exception:
        auto_balance_endpoint = '/accounting/journal-entry/auto-balance/'

    context = {
        "voucher_entry_page": True,
        "journal_default_type": journal_entry_settings.ui_settings.get("default_entry_type") or "JN",
        "initial_journal_id": journal_id_param,
        "detail_url_template": reverse("accounting:journal_entry_data", kwargs={"pk": 0}),
        "supported_currencies": supported_currencies,
        "default_currency": default_currency,
        "default_date": default_date,
        "base_currency": base_currency,
        "permission_flags": permission_flags,
        "lookup_urls": lookup_urls,
        "active_organization": organization,
        "config_endpoint": config_endpoint,
        "prefs_endpoint": prefs_endpoint,
        "prefs_save_endpoint": prefs_save_endpoint,
        "attachment_upload_endpoint": attachment_upload_endpoint,
        "attachment_delete_endpoint": attachment_delete_endpoint,
        "payment_terms_endpoint": payment_terms_endpoint,
        "show_config_selector": False,
        "journal_debug_enabled": _is_journal_debug_enabled(organization),
        "row_endpoint": row_endpoint,
        "header_partial_endpoint": header_partial_endpoint,
        "lines_partial_endpoint": lines_partial_endpoint,
        "side_panel_endpoint": side_panel_endpoint,
        "add_row_endpoint": add_row_endpoint,
        "imbalance_bar_endpoint": imbalance_bar_endpoint,
        "duplicate_row_endpoint": duplicate_row_endpoint,
        "bulk_add_rows_endpoint": bulk_add_rows_endpoint,
        "auto_balance_endpoint": auto_balance_endpoint,
        "ui_preferences": preferences,
        "ui_preferences_json": json.dumps(preferences),
        "line_density": line_density,
        "auto_balance_enabled": auto_balance_enabled,
    }
    return render(request, "accounting/journal_entry.html", context)


@login_required
@require_GET
def journal_entry_row(request):
    """Return a single journal line row as HTML for HTMX calls."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    try:
        row_index = max(0, int(request.GET.get("index", 0)))
    except (ValueError, TypeError):
        row_index = 0

    journal_type_param = _journal_type_param_from_request(request)
    _, _, _, _, line_defaults, line_labels = _line_schema_context(organization, journal_type_param)
    line_layout = _line_layout_for_request(request, line_labels)

    row_data = {}
    row_payload = request.GET.get("row")
    if row_payload:
        try:
            parsed = json.loads(row_payload)
            if isinstance(parsed, dict):
                row_data = parsed
        except json.JSONDecodeError:
            return _json_error("Invalid row payload.", status=400)

    html = _render_line_row_html(request, row_index, line_defaults, line_labels, line_layout["visible"], row_data)
    return JsonResponse({"ok": True, "html": html})


@login_required
@require_GET
def journal_entry_add_row(request):
    """Return a fresh empty journal line row via HTMX."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    try:
        row_index = max(0, int(request.GET.get("index", 0)))
    except (ValueError, TypeError):
        row_index = 0

    journal_type_param = _journal_type_param_from_request(request)
    _, _, _, _, line_defaults, line_labels = _line_schema_context(organization, journal_type_param)
    line_layout = _line_layout_for_request(request, line_labels)

    html = _render_line_row_html(request, row_index, line_defaults, line_labels, line_layout["visible"])
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({"refreshSidePanel": True})
    return response


@login_required
@require_GET
def journal_entry_lines_partial(request):
    """Render the full journal lines grid as an HTMX fragment."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    journal_type_param = _journal_type_param_from_request(request)
    _, _, _, _, line_defaults, line_labels = _line_schema_context(organization, journal_type_param)

    payload = _get_json_query_param(request, "payload")
    lines_data: List[Dict[str, Any]] = []
    if payload and isinstance(payload, dict):
        candidate = payload.get("lines") or payload.get("rows")
        if isinstance(candidate, list):
            lines_data = candidate
    if not lines_data:
        explicit_lines = _get_json_query_param(request, "lines") or _get_json_query_param(request, "rows")
        if isinstance(explicit_lines, list):
            lines_data = explicit_lines

    journal_id = request.GET.get("journalId") or request.GET.get("journal_id")
    if not lines_data and journal_id and journal_id.isdigit():
        try:
            journal = _get_user_journal(request.user, int(journal_id))
            journal_payload = _serialize_journal(journal)
            lines_data = journal_payload.get("rows", [])
        except ValueError:
            pass

    if not isinstance(lines_data, list):
        lines_data = []

    if not lines_data:
        lines_data = [{}]

    normalized_rows = [
        _merge_line_row_data(row, line_defaults)
        for row in lines_data
    ]

    html = _render_lines_fragment(request, normalized_rows, line_labels)
    return HttpResponse(html)


@login_required
@require_POST
def journal_auto_balance(request):
    """Adjust rows so total debits equal credits."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    payload = _parse_request_json(request) or {}
    header_data = payload.get("header") or {}
    journal_type_token = (
        header_data.get("journalType")
        or header_data.get("journal_type")
        or payload.get("journalType")
        or payload.get("journal_type")
        or ""
    )

    (
        _,
        _,
        _,
        _,
        line_defaults,
        line_labels,
    ) = _line_schema_context(organization, journal_type_token)

    raw_lines = payload.get("lines") or payload.get("rows") or []
    if not isinstance(raw_lines, list):
        raw_lines = []
    normalized_rows = [_merge_line_row_data(row, line_defaults) for row in raw_lines]
    if not normalized_rows:
        normalized_rows = [{}]

    totals = _sum_totals_from_rows(normalized_rows)
    diff = Decimal(str(totals.get("diff", 0.0)))
    config = _resolve_voucher_config(organization, journal_type_token)
    if abs(diff) >= Decimal("0.01"):
        target_field = "cr" if diff > 0 else "dr"
        amount = abs(diff)
        last_row = normalized_rows[-1]
        existing = Decimal(str(last_row.get(target_field) or 0))
        if last_row.get("account") and existing == 0:
            last_row[target_field] = _format_decimal(amount)
        else:
            balancing_row = _merge_line_row_data({}, line_defaults)
            balancing_row["account"] = _suspense_account_for_config(config)
            balancing_row[target_field] = _format_decimal(amount)
            balancing_row["narr"] = "Auto Balance"
            opposing_field = "cr" if target_field == "dr" else "dr"
            balancing_row[opposing_field] = ""
            normalized_rows.append(balancing_row)

    header_payload = payload.get("header") if payload else {}
    service = JournalEntryService(request.user, organization)
    validation_rows = _rows_for_validation(normalized_rows)
    service_header = _header_for_validation(header_payload)
    try:
        validation_errors = service._validate_journal_entry(service_header, validation_rows, config)
    except Exception:
        validation_errors = []

    trigger_payload = {
        "refreshSidePanel": True,
        "validationErrors": validation_errors,
    }
    if abs(diff) >= Decimal("0.01"):
        trigger_payload["alert"] = "Journal auto-balanced."
        trigger_payload["alertType"] = "success"

    html = _render_lines_fragment(request, normalized_rows, line_labels)
    response = HttpResponse(html)
    response["HX-Trigger"] = json.dumps(trigger_payload)
    return response


@login_required
@require_POST
def journal_entry_row_duplicate(request):
    """Duplicate an existing row via HTMX and return the cloned markup."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    journal_type_param = _journal_type_param_from_request(request)
    _, _, _, _, line_defaults, line_labels = _line_schema_context(organization, journal_type_param)
    line_layout = _line_layout_for_request(request, line_labels)
    row_data = _parse_row_payload(request)
    try:
        row_index = max(0, int(request.POST.get("index") or 0))
    except (ValueError, TypeError):
        row_index = 0

    html = _render_line_row_html(request, row_index, line_defaults, line_labels, line_layout["visible"], row_data)
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({"refreshSidePanel": True})
    return response


@login_required
@require_POST
def journal_entry_bulk_add(request):
    """Add multiple lines parsed from clipboard data."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    clipboard = request.POST.get("clipboard")
    if not clipboard:
        return HttpResponse("", status=204)

    journal_type_param = _journal_type_param_from_request(request)
    _, _, _, _, line_defaults, line_labels = _line_schema_context(organization, journal_type_param)
    line_layout = _line_layout_for_request(request, line_labels)

    rows: List[Dict[str, Any]] = []
    for line in clipboard.splitlines():
        values = [cell.strip() for cell in line.split("\t")]
        if not any(values):
            continue
        row: Dict[str, Any] = {}
        if values:
            row["account"] = values[0]
        if len(values) > 1:
            row["narr"] = values[1]
        if len(values) > 2:
            row["dr"] = values[2]
        if len(values) > 3:
            row["cr"] = values[3]
        if len(values) > 4:
            row["costCenter"] = values[4]
        if len(values) > 5:
            row["project"] = values[5]
        if len(values) > 6:
            row["department"] = values[6]
        if len(values) > 7:
            row["taxCode"] = values[7]
        rows.append(row)

    if not rows:
        return HttpResponse("", status=204)

    html_fragments = []
    for row_data in rows:
        html_fragments.append(
            _render_line_row_html(
                request,
                0,
                line_defaults,
                line_labels,
                line_layout["visible"],
                row_data,
            )
        )

    response = HttpResponse("".join(html_fragments))
    response['HX-Trigger'] = json.dumps({"refreshSidePanel": True})
    return response

@login_required
@require_GET
def journal_entry_header_partial(request):
    """Render the journal header form fragment."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    preferences = _voucher_ui_preferences_for_user(request.user, organization)
    header_density = preferences.get("headerDensity") or preferences.get("density") or "comfortable"

    journal_type_param = _journal_type_param_from_request(request)
    (
        _,
        header_schema,
        header_allowed,
        header_required,
        header_defaults,
        header_labels,
    ) = _header_schema_context(organization, journal_type_param)

    payload = _get_json_query_param(request, "payload")
    header_values = dict(header_defaults)
    header_samples = _get_json_query_param(request, "header")
    if isinstance(header_samples, dict):
        header_values.update({k: v for k, v in header_samples.items() if v is not None})
    elif payload and isinstance(payload, dict):
        nested = payload.get("header")
        if isinstance(nested, dict):
            header_values.update({k: v for k, v in nested.items() if v is not None})

    header_fields = []
    for raw_key, definition in header_schema.items():
        state_key = _state_key_for_header(raw_key)
        label = header_labels.get(state_key) or definition.get("label") or raw_key.replace("_", " ").title()
        header_fields.append(
            {
                "name": state_key,
                "label": label,
                "type": definition.get("type") or "text",
                "choices": definition.get("choices") or [],
                "required": bool(header_required.get(state_key)),
                "value": header_values.get(state_key) or header_defaults.get(state_key, ""),
            }
        )
    try:
        side_panel_endpoint = reverse('accounting:journal_entry_side_panel')
    except Exception:
        side_panel_endpoint = '/accounting/journal-entry/side-panel/'

    html = render_to_string(
        "accounting/partials/journal_entry_header_partial.html",
        {
            "header_fields": header_fields,
            "side_panel_endpoint": side_panel_endpoint,
            "header_defaults": header_defaults,
            "header_density": header_density,
        },
        request=request,
    )
    return HttpResponse(html)


@login_required
@require_GET
def journal_entry_side_panel(request):
    """Return summary/validation details for the current journal entry."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    journal_id = request.GET.get("journalId") or request.GET.get("journal_id")
    journal_data: Optional[Dict[str, Any]] = None
    rows: List[Dict[str, Any]] = []
    totals: Dict[str, float] = {}
    header_values: Dict[str, Any] = {}
    attachments: List[Dict[str, Any]] = []
    if journal_id and journal_id.isdigit():
        try:
            journal = _get_user_journal(request.user, int(journal_id))
            journal_data = _serialize_journal(journal)
        except ValueError as exc:
            return _json_error(str(exc), status=404)
    else:
        payload = _get_json_query_param(request, "payload")
        if payload and isinstance(payload, dict):
            journal_data = payload

    if journal_data:
        rows = journal_data.get("rows", []) or []
        totals = journal_data.get("totals", {}) or {}
        header_values = journal_data.get("header") or {}
        attachments = journal_data.get("attachments", []) or []

    if not rows:
        fallback_lines = _get_json_query_param(request, "lines") or _get_json_query_param(request, "rows")
        if isinstance(fallback_lines, list):
            rows = fallback_lines

    if not totals:
        totals = _sum_totals_from_rows(rows)

    payload_header = {}
    payload = _get_json_query_param(request, "payload")
    if payload and isinstance(payload, dict):
        payload_header = payload.get("header") or {}
        if not header_values:
            header_values = payload_header
        if not rows:
            rows = payload.get("rows") or payload.get("lines") or rows
        attachments = attachments or payload.get("attachments") or []

    try:
        selected_index = int(request.GET.get("rowIndex") or request.GET.get("index") or 0)
    except (ValueError, TypeError):
        selected_index = 0
    selected_index = max(0, min(selected_index, len(rows) - 1)) if rows else 0
    selected_line = rows[selected_index] if rows else {}

    selected_account_info: Dict[str, Any] = {}
    if selected_line:
        account_obj = None
        account_id = selected_line.get("accountId")
        if account_id:
            account_obj = ChartOfAccount.active_accounts.filter(pk=account_id, organization=organization).first()
        if not account_obj:
            account_token = selected_line.get("accountCode") or ""
            if not account_token and selected_line.get("account"):
                account_token = str(selected_line.get("account")).split(" - ", 1)[0].strip()
            if account_token:
                account_obj = ChartOfAccount.active_accounts.filter(organization=organization, account_code=account_token).first()
        if account_obj:
            selected_account_info = {
                "code": account_obj.account_code,
                "name": account_obj.account_name,
                "type": getattr(account_obj.account_type, "name", ""),
                "balance": float(account_obj.balance()),
                "is_bank_account": account_obj.is_bank_account,
            }

    validation_errors: List[str] = []
    raw_messages = request.GET.get("validationMessages") or request.GET.get("validation_messages")
    if raw_messages:
        try:
            parsed = json.loads(raw_messages)
            if isinstance(parsed, list):
                validation_errors = parsed
        except json.JSONDecodeError:
            validation_errors = [raw_messages]

    header_for_validation = _header_for_validation(header_values)
    service_rows = _rows_for_validation(rows)
    config = _resolve_voucher_config(organization, _journal_type_token_from_header(header_values))
    service = JournalEntryService(request.user, organization)
    try:
        service_errors = service._validate_journal_entry(header_for_validation, service_rows, config)
    except Exception:
        service_errors = []

    combined_errors: List[str] = []
    for err in service_errors + validation_errors:
        if err and err not in combined_errors:
            combined_errors.append(err)

    ai_insights = _ai_insights_for_line(selected_line)

    if journal_id and journal_id.isdigit() and not attachments:
        try:
            journal = _get_user_journal(request.user, int(journal_id))
            attachments = [
                {
                    "id": att.pk,
                    "name": os.path.basename(att.file.name),
                    "uploadedAt": att.uploaded_at.isoformat() if att.uploaded_at else None,
                    "uploadedBy": att.uploaded_by_id,
                }
                for att in journal.attachments.all()
            ]
        except ValueError:
            attachments = []

    try:
        attachment_upload_endpoint = reverse('accounting:journal_attachment_upload')
    except Exception:
        attachment_upload_endpoint = '/accounting/journal-entry/attachments/upload/'

    _, _, _, _, _, line_labels = _line_schema_context(organization, _journal_type_token_from_header(header_values) or _journal_type_param_from_request(request))

    context = {
        "line_labels": line_labels,
        "totals": totals,
        "balanced": abs(totals.get("diff", 0)) < 0.01,
        "selected_index": selected_index,
        "selected_line": selected_line,
        "selected_account_info": selected_account_info,
        "validation_errors": combined_errors,
        "attachments": attachments,
        "attachment_upload_endpoint": attachment_upload_endpoint,
        "journal_id": journal_id,
        "ai_insights": ai_insights,
    }
    html = render_to_string(
        "accounting/partials/journal_entry_side_panel.html",
        context,
        request=request,
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({"validationErrors": combined_errors})
    return response


@login_required
@require_GET
def journal_entry_imbalance_bar(request):
    """Return an HTMX fragment showing the imbalance indicator."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    totals_payload = _get_json_query_param(request, "totals")
    rows_param = _get_json_query_param(request, "lines") or _get_json_query_param(request, "rows")
    if not totals_payload and isinstance(rows_param, list):
        totals_payload = _sum_totals_from_rows(rows_param)

    totals_payload = totals_payload or {}
    dr = _float_or_zero(totals_payload.get("dr"))
    cr = _float_or_zero(totals_payload.get("cr"))
    diff = dr - cr
    max_bal = max(abs(dr), abs(cr), 1.0)
    percent = min(100.0, (abs(diff) / max_bal) * 100)

    html = render_to_string(
        "accounting/partials/journal_entry_imbalance_bar.html",
        {
            "dr": dr,
            "cr": cr,
            "diff": diff,
            "balanced": abs(diff) < 0.01,
            "percent": percent,
        },
        request=request,
    )
    return HttpResponse(html)


@login_required
@ensure_csrf_cookie
def journal_select_config(request):
    """Render a dedicated configuration selection screen before voucher entry."""
    organization = _active_organization(request.user)
    if organization:
        configs = (
            VoucherModeConfig.objects.filter(
                organization=organization,
                is_active=True,
                archived_at__isnull=True,
            )
            .select_related('journal_type')
            .order_by('name')
        )
    else:
        configs = VoucherModeConfig.objects.none()
    context = {
        "voucher_entry_page": True,
        "voucher_configs": configs,
        "active_organization": organization,
    }
    return render(request, "accounting/journal_select_config.html", context)


@login_required
@require_GET
def journal_period_validate(request):
    """Validate whether a date falls within an open accounting period.

    Returns JSON: { ok: bool, error?: str, period?: { id, label } }
    """
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    date_str = request.GET.get("date")
    if not date_str:
        return _json_error("Missing 'date' parameter.", status=400)
    try:
        journal_date = parse_date(date_str)
        if not journal_date:
            raise ValueError
    except Exception:
        return _json_error("Invalid date format. Use YYYY-MM-DD.", status=400)
    try:
        period = _resolve_period(organization, journal_date)
        label = f"{period.fiscal_year.name if getattr(period, 'fiscal_year', None) else ''} {period.start_date}–{period.end_date}"
        return JsonResponse({
            "ok": True,
            "period": {"id": period.pk, "label": label}
        })
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)


@login_required
@require_POST
def journal_save_draft(request):
    organization = _active_organization(request.user)
    debug_token = _issue_debug_token("journal_save_draft", request.user, organization)
    try:
        payload = _parse_request_json(request)
        logger.debug("Journal draft save payload: %s", payload)
        journal, created = _persist_journal_draft(request.user, payload)
        message = "Journal draft created." if created else "Journal draft updated."
        response = {"ok": True, "journal": _serialize_journal(journal), "message": message}
        if debug_token:
            response["debugToken"] = debug_token
        return JsonResponse(response)
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details, debug_token=debug_token)
    except PermissionError as exc:
        return _json_error(str(exc), status=403, debug_token=debug_token)
    except Exception as exc:
        import traceback
        from django.conf import settings
        logger.exception("Unexpected error while saving journal draft.")
        error_msg = "Unexpected error while saving journal draft."
        details = None
        if settings.DEBUG:
            details = {"exception": str(exc), "traceback": traceback.format_exc()}
        return _json_error(error_msg, status=500, debug_token=debug_token, details=details)


@login_required
@require_POST
def journal_submit(request):
    organization = _active_organization(request.user)
    debug_token = _issue_debug_token("journal_submit", request.user, organization)
    try:
        payload = _parse_request_json(request)
        logger.debug("Journal submit payload: %s", payload)
        if not organization:
            return _json_error("Active organization required.", status=400, debug_token=debug_token)
        if not _user_can_workflow(request.user, organization, "submit"):
            return _json_error("You do not have permission to submit journals.", status=403, debug_token=debug_token)
        journal, _ = _persist_journal_draft(request.user, payload)
        service = JournalEntryService(request.user, organization)
        service.submit(journal)
        journal.refresh_from_db()
        response = {
            "ok": True,
            "journal": _serialize_journal(journal),
            "message": "Journal submitted for approval.",
        }
        if debug_token:
            response["debugToken"] = debug_token
        return JsonResponse(response)
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details, debug_token=debug_token)
    except PermissionError as exc:
        return _json_error(str(exc), status=403, debug_token=debug_token)
    except Exception:
        logger.exception("Unexpected error while submitting journal.")
        return _json_error("Unexpected error while submitting journal.", status=500, debug_token=debug_token)


@login_required
@require_POST
def journal_approve(request):
    organization = _active_organization(request.user)
    debug_token = _issue_debug_token("journal_approve", request.user, organization)
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to approve a journal.")
        if not organization:
            return _json_error("Active organization required.", status=400, debug_token=debug_token)
        if not _user_can_workflow(request.user, organization, "approve"):
            return _json_error("You do not have permission to approve journals.", status=403, debug_token=debug_token)
        journal = _get_user_journal(request.user, int(journal_id))
        service = JournalEntryService(request.user, organization)
        service.approve(journal)
        journal.refresh_from_db()
        response = {
            "ok": True,
            "journal": _serialize_journal(journal),
            "message": "Journal approved.",
        }
        if debug_token:
            response["debugToken"] = debug_token
        return JsonResponse(response)
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details, debug_token=debug_token)
    except PermissionError as exc:
        return _json_error(str(exc), status=403, debug_token=debug_token)
    except Exception:
        logger.exception("Unexpected error while approving journal.")
        return _json_error("Unexpected error while approving journal.", status=500, debug_token=debug_token)


@login_required
@require_POST
def journal_reject(request):
    organization = _active_organization(request.user)
    debug_token = _issue_debug_token("journal_reject", request.user, organization)
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to reject a journal.")
        if not organization:
            return _json_error("Active organization required.", status=400, debug_token=debug_token)
        if not _user_can_workflow(request.user, organization, "reject"):
            return _json_error("You do not have permission to reject journals.", status=403, debug_token=debug_token)
        journal = _get_user_journal(request.user, int(journal_id))
        service = JournalEntryService(request.user, organization)
        service.reject(journal)
        journal.refresh_from_db()
        response = {
            "ok": True,
            "journal": _serialize_journal(journal),
            "message": "Journal rejected.",
        }
        if debug_token:
            response["debugToken"] = debug_token
        return JsonResponse(response)
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details, debug_token=debug_token)
    except PermissionError as exc:
        return _json_error(str(exc), status=403, debug_token=debug_token)
    except Exception:
        logger.exception("Unexpected error while rejecting journal.")
        return _json_error("Unexpected error while rejecting journal.", status=500, debug_token=debug_token)


@login_required
@require_POST
def journal_post(request):
    organization = _active_organization(request.user)
    debug_token = _issue_debug_token("journal_post", request.user, organization)
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to post a journal.")
        if not organization:
            return _json_error("Active organization required.", status=400, debug_token=debug_token)
        if not _user_can_workflow(request.user, organization, "post"):
            return _json_error("You do not have permission to post journals.", status=403, debug_token=debug_token)
        journal = _get_user_journal(request.user, int(journal_id))
        service = JournalEntryService(request.user, organization)
        service.post(journal)
        journal.refresh_from_db()
        response = {
            "ok": True,
            "journal": _serialize_journal(journal),
            "message": "Journal posted.",
        }
        if debug_token:
            response["debugToken"] = debug_token
        return JsonResponse(response)
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details, debug_token=debug_token)
    except PermissionError as exc:
        return _json_error(str(exc), status=403, debug_token=debug_token)
    except Exception:
        logger.exception("Unexpected error while posting journal.")
        return _json_error("Unexpected error while posting journal.", status=500, debug_token=debug_token)


@login_required
@require_GET
def journal_entry_data(request, pk: int):
    try:
        journal = _get_user_journal(request.user, pk)
    except ValueError as exc:
        return _json_error(str(exc), status=404)
    return JsonResponse({"ok": True, "journal": _serialize_journal(journal)})


@login_required
@require_GET
def journal_account_lookup(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    query = (request.GET.get("q") or "").strip()
    qs = ChartOfAccount.active_accounts.filter(organization=organization)
    if query:
        qs = qs.filter(Q(account_code__icontains=query) | Q(account_name__icontains=query))
    qs = qs.order_by("account_code")[:20]
    results = [
        {"id": acc.pk, "code": acc.account_code, "name": acc.account_name}
        for acc in qs
    ]
    return JsonResponse({"ok": True, "results": results})


@login_required
@require_GET
def journal_cost_center_lookup(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    query = (request.GET.get("q") or "").strip()
    qs = CostCenter.objects.filter(organization=organization, is_active=True)
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query))
    qs = qs.order_by("code")[:20]
    results = [
        {"id": cc.pk, "code": cc.code, "name": cc.name}
        for cc in qs
    ]
    return JsonResponse({"ok": True, "results": results})


@login_required
@require_GET
def journal_payment_terms(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    ref_date = None
    if request.GET.get("date"):
        ref_date = parse_date(request.GET.get("date"))
    qs = PaymentTerm.objects.filter(organization=organization, is_active=True).order_by("name")
    results = []
    for term in qs:
        entry = {
            "id": term.pk,
            "code": term.code,
            "name": term.name,
            "netDueDays": term.net_due_days,
            "discountPercent": float(term.discount_percent or 0),
            "discountDays": term.discount_days,
            "description": term.description or "",
        }
        if ref_date:
            try:
                entry["dueDate"] = term.calculate_due_date(ref_date).isoformat()
                discount_due = term.calculate_discount_due_date(ref_date)
                if discount_due:
                    entry["discountDueDate"] = discount_due.isoformat()
            except Exception:
                entry["dueDate"] = None
        results.append(entry)
    return JsonResponse({"ok": True, "results": results})


@login_required
@require_GET
def journal_ui_preferences(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    prefs = VoucherUIPreference.objects.filter(
        user=request.user,
        organization=organization,
        scope="voucher_entry",
    ).first()
    data = prefs.data if prefs else {}
    updated_at = prefs.updated_at.isoformat() if prefs and prefs.updated_at else None
    return JsonResponse({"ok": True, "preferences": data, "updatedAt": updated_at})


@login_required
@require_POST
def journal_ui_preferences_save(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    raw_preferences = None
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = _parse_request_json(request)
            raw_preferences = payload.get("preferences")
        except ValueError as exc:
            return _json_error(str(exc), status=400)
    else:
        raw_preferences = request.POST.get("preferences")
    preferences: Dict[str, Any] = {}
    if isinstance(raw_preferences, str):
        try:
            parsed = json.loads(raw_preferences)
            if isinstance(parsed, dict):
                preferences = parsed
        except json.JSONDecodeError:
            preferences = {}
    elif isinstance(raw_preferences, dict):
        preferences = raw_preferences
    prefs, _ = VoucherUIPreference.objects.get_or_create(
        user=request.user,
        organization=organization,
        scope="voucher_entry",
    )
    prefs.data = preferences
    prefs.save(update_fields=["data", "updated_at"])
    response = JsonResponse({"ok": True, "message": "Preferences saved."})
    response["HX-Trigger"] = json.dumps({
        "alert": "Column preferences saved.",
        "alertType": "success",
        "refreshLines": True,
        "refreshSidePanel": True,
    })
    return response


@login_required
@require_POST
def journal_attachment_upload(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    journal_id = request.POST.get("journal_id") or request.POST.get("journalId")
    if not journal_id:
        return _json_error("journal_id is required to upload attachments.", status=400)
    try:
        journal = Journal.objects.get(pk=int(journal_id), organization=organization)
    except (Journal.DoesNotExist, ValueError, TypeError):
        return _json_error("Journal not found.", status=404)

    files = request.FILES.getlist("files") or request.FILES.getlist("attachments") or []
    single = request.FILES.get("file")
    if single and not files:
        files = [single]
    if not files:
        return _json_error("No files uploaded.", status=400)

    created = []
    for uploaded in files:
        try:
            extracted_files = list(
                iter_validated_files(
                    uploaded,
                    allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS,
                    max_bytes=MAX_ATTACHMENT_UPLOAD_BYTES,
                    allow_archive=True,
                    label="Attachment",
                )
            )
        except ValidationError as exc:
            return _json_error(str(exc), status=400)

        for filename, content in extracted_files:
            content.seek(0)
            att = Attachment(journal=journal, uploaded_by=request.user)
            att.file.save(filename, content, save=True)
            created.append(
                {
                    "id": att.pk,
                    "name": filename,
                    "uploadedAt": att.uploaded_at.isoformat() if att.uploaded_at else None,
                    "uploadedBy": att.uploaded_by_id,
                }
            )

    response = JsonResponse({"ok": True, "attachments": created, "message": "Attachment(s) uploaded."})
    response["HX-Trigger"] = json.dumps({"refreshSidePanel": True, "alert": "Attachment(s) uploaded.", "alertType": "success"})
    return response


@login_required
@require_GET
def resolve_exchange_rate(request):
    """HTMX endpoint to resolve exchange rate for given currency and date."""
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)

    from_currency = request.GET.get('currency_code', '').strip().upper()
    to_currency = request.GET.get('to_currency', '').strip().upper()
    rate_date_str = request.GET.get('journal_date', '').strip()

    if not from_currency or not to_currency or not rate_date_str:
        return _json_error("currency_code, to_currency, and journal_date are required.", status=400)

    try:
        rate_date = parse_date(rate_date_str)
        if not rate_date:
            raise ValueError("Invalid date format")
    except (ValueError, TypeError):
        return _json_error("Invalid journal_date format. Use YYYY-MM-DD.", status=400)

    from accounting.services.currency_service import resolvecurrency
    try:
        rate = resolvecurrency(organization, from_currency, to_currency, rate_date)
        # Additional validation for client-side safety
        if rate <= 0:
            rate = Decimal('1.000000')
        return HttpResponse(str(rate))
    except Exception as exc:
        logger.exception("Error resolving exchange rate: %s", exc)
        return HttpResponse("1.000000")  # Default fallback


@login_required
@require_POST
def journal_attachment_delete(request):
    organization = _active_organization(request.user)
    if not organization:
        return _json_error("Active organization required.", status=400)
    att_id = request.POST.get("attachment_id") or request.POST.get("id")
    if not att_id:
        return _json_error("attachment_id is required.", status=400)
    try:
        attachment = Attachment.objects.select_related("journal").get(
            pk=int(att_id),
            journal__organization=organization,
        )
    except (Attachment.DoesNotExist, ValueError, TypeError):
        return _json_error("Attachment not found.", status=404)
    attachment.delete()
    return JsonResponse({"ok": True})
def _ai_insights_for_line(line: Dict[str, Any]) -> List[str]:
    insights: List[str] = []
    if not line:
        return insights
    debit = _float_or_zero(line.get("dr") or line.get("debit") or line.get("debit_amount"))
    credit = _float_or_zero(line.get("cr") or line.get("credit") or line.get("credit_amount"))
    if debit or credit:
        has_tax = bool(line.get("taxCode") or line.get("tax_code") or line.get("taxCodeId"))
        account_code = line.get("accountCode") or line.get("chartOfAccount") or line.get("account")
        if not has_tax and account_code and account_code[:1] in ("4", "5"):
            insights.append("Consider assigning a tax code for this revenue/expense line.")
    return insights
