import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.db.models import Q
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
    JournalLine,
    JournalType,
    Project,
    TaxCode,
    VoucherModeConfig,
    VoucherUDFConfig,
    default_ui_schema,
)
from accounting.services.journal_entry_service import JournalEntryService
from usermanagement.utils import PermissionUtils

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


def _parse_request_json(request) -> Dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON payload") from exc


def _json_error(message: str, status: int = 400, details: Optional[Dict[str, Any]] = None) -> JsonResponse:
    payload: Dict[str, Any] = {"ok": False, "error": message}
    if details:
        payload["details"] = details
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
            fiscal_year__organization=organization,
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

    for idx, row in enumerate(rows, start=1):
        debit = _safe_decimal(row.get("dr"))
        credit = _safe_decimal(row.get("cr"))
        account_fields = (row.get("account"), row.get("accountCode"), row.get("accountId"))

        if not any(account_fields) and debit == 0 and credit == 0:
            continue

        for key in required_map.keys():
            _ensure_required(row, key)
        for key in allowed_map.keys():
            _ensure_allowed(row, key)

        account = _resolve_account(organization, row)

        line_payload: Dict[str, Any] = {
            "line_number": idx,
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

    currency = (header.get("currency") or journal_entry_settings.supported_currencies[0]).upper()
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
    metadata_payload["supportedCurrencies"] = journal_entry_settings.supported_currencies
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
        journal = service.update_journal_entry(journal, journal_data, line_data, attachments)
    else:
        journal = service.create_journal_entry(journal_data, line_data, attachments)
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
            else (journal_entry_settings.supported_currencies[0] if journal_entry_settings.supported_currencies else None)
        ),
        "headerRequired": sorted([key for key, value in header_required.items() if value]),
        "lineRequired": sorted([key for key, value in line_required.items() if value]),
        "headerAllowedValues": {key: sorted(values) for key, values in header_allowed.items()},
        "lineAllowedValues": {key: sorted(values) for key, values in line_allowed.items()},
        "headerDefaults": header_defaults,
        "lineDefaults": line_defaults,
        "supportedCurrencies": journal_entry_settings.supported_currencies,
        "headerLabels": header_labels,
        "lineLabels": line_labels,
    }

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
def journal_entry(request):
    """Render the Excel-like Journal Entry UI."""
    journal_id_param = request.GET.get("journal_id") or ""
    if journal_id_param and not journal_id_param.isdigit():
        journal_id_param = ""

    organization = _active_organization(request.user)
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

    context = {
        "voucher_entry_page": True,
        "journal_default_type": journal_entry_settings.ui_settings.get("default_entry_type") or "JN",
        "initial_journal_id": journal_id_param,
        "detail_url_template": reverse("accounting:journal_entry_data", kwargs={"pk": 0}),
        "supported_currencies": journal_entry_settings.supported_currencies,
        "permission_flags": permission_flags,
        "lookup_urls": lookup_urls,
        "active_organization": organization,
    }
    return render(request, "accounting/journal_entry.html", context)


@login_required
@require_POST
def journal_save_draft(request):
    try:
        payload = _parse_request_json(request)
        logger.debug("Journal draft save payload: %s", payload)
        journal, created = _persist_journal_draft(request.user, payload)
        message = "Journal draft created." if created else "Journal draft updated."
        return JsonResponse({"ok": True, "journal": _serialize_journal(journal), "message": message})
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)
    except PermissionError as exc:
        return _json_error(str(exc), status=403)
    except Exception:
        logger.exception("Unexpected error while saving journal draft.")
        return _json_error("Unexpected error while saving journal draft.", status=500)


@login_required
@require_POST
def journal_submit(request):
    try:
        payload = _parse_request_json(request)
        logger.debug("Journal submit payload: %s", payload)
        journal, _ = _persist_journal_draft(request.user, payload)
        organization = _active_organization(request.user)
        service = JournalEntryService(request.user, organization)
        service.submit(journal)
        journal.refresh_from_db()
        return JsonResponse(
            {
                "ok": True,
                "journal": _serialize_journal(journal),
                "message": "Journal submitted for approval.",
            }
        )
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)
    except PermissionError as exc:
        return _json_error(str(exc), status=403)
    except Exception:
        logger.exception("Unexpected error while submitting journal.")
        return _json_error("Unexpected error while submitting journal.", status=500)


@login_required
@require_POST
def journal_approve(request):
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to approve a journal.")
        journal = _get_user_journal(request.user, int(journal_id))
        organization = _active_organization(request.user)
        service = JournalEntryService(request.user, organization)
        service.approve(journal)
        journal.refresh_from_db()
        return JsonResponse(
            {
                "ok": True,
                "journal": _serialize_journal(journal),
                "message": "Journal approved.",
            }
        )
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)
    except PermissionError as exc:
        return _json_error(str(exc), status=403)
    except Exception:
        logger.exception("Unexpected error while approving journal.")
        return _json_error("Unexpected error while approving journal.", status=500)


@login_required
@require_POST
def journal_reject(request):
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to reject a journal.")
        journal = _get_user_journal(request.user, int(journal_id))
        organization = _active_organization(request.user)
        service = JournalEntryService(request.user, organization)
        service.reject(journal)
        journal.refresh_from_db()
        return JsonResponse(
            {
                "ok": True,
                "journal": _serialize_journal(journal),
                "message": "Journal rejected.",
            }
        )
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)
    except PermissionError as exc:
        return _json_error(str(exc), status=403)
    except Exception:
        logger.exception("Unexpected error while rejecting journal.")
        return _json_error("Unexpected error while rejecting journal.", status=500)


@login_required
@require_POST
def journal_post(request):
    try:
        payload = _parse_request_json(request)
        journal_id = payload.get("journalId") or payload.get("journal_id")
        if not journal_id:
            raise ValueError("journalId is required to post a journal.")
        journal = _get_user_journal(request.user, int(journal_id))
        organization = _active_organization(request.user)
        service = JournalEntryService(request.user, organization)
        service.post(journal)
        journal.refresh_from_db()
        return JsonResponse(
            {
                "ok": True,
                "journal": _serialize_journal(journal),
                "message": "Journal posted.",
            }
        )
    except ValueError as exc:
        message, details = _format_value_error(exc)
        return _json_error(message, status=400, details=details)
    except PermissionError as exc:
        return _json_error(str(exc), status=403)
    except Exception:
        logger.exception("Unexpected error while posting journal.")
        return _json_error("Unexpected error while posting journal.", status=500)


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
