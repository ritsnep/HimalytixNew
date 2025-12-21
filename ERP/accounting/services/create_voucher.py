from decimal import Decimal
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    VoucherModeConfig,
    Journal,
    JournalLine,
    AccountingPeriod,
    ChartOfAccount,
    CostCenter,
    Department,
    Project,
)
from accounting.extensions.hooks import HookRunner
from accounting.services.voucher_errors import VoucherProcessError

logger = logging.getLogger(__name__)


def _coerce_pk(value):
    if value is None:
        return None
    if hasattr(value, "pk"):
        return value.pk
    return value


def _parse_display_value(value):
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if " - " in text:
        code, name = text.split(" - ", 1)
        return code.strip() or None, name.strip() or None
    return text, text


def _resolve_by_code_or_name(model, organization, raw_value, *, code_field="code", name_field="name"):
    if raw_value is None:
        return None
    if hasattr(raw_value, "pk"):
        return raw_value.pk
    value = str(raw_value).strip()
    if not value:
        return None
    code, name = _parse_display_value(value)
    qs = model.objects.all()
    if organization is not None and hasattr(model, "organization"):
        qs = qs.filter(organization=organization)
    if hasattr(model, "is_active"):
        try:
            qs = qs.filter(is_active=True)
        except Exception:
            pass
    # Try exact code match first, then name match.
    if code:
        matched = qs.filter(**{code_field: code}).first()
        if matched:
            return matched.pk
    if name:
        matched = qs.filter(**{name_field: name}).first()
        if matched:
            return matched.pk
    return None


def _resolve_fk_with_display(line_data, key, model, organization, *, code_field="code", name_field="name"):
    direct = _coerce_pk(line_data.get(key))
    if direct:
        return direct
    display = line_data.get(f"{key}_display")
    if display:
        return _resolve_by_code_or_name(model, organization, display, code_field=code_field, name_field=name_field)
    code = line_data.get(f"{key}_code")
    name = line_data.get(f"{key}_name")
    if code:
        return _resolve_by_code_or_name(model, organization, code, code_field=code_field, name_field=name_field)
    if name:
        return _resolve_by_code_or_name(model, organization, name, code_field=code_field, name_field=name_field)
    return None


def _is_zero_like(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        try:
            return Decimal(stripped) == 0
        except Exception:
            return False
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)) == 0
    return False


def _line_has_values(line_data):
    if not isinstance(line_data, dict):
        return False
    for key, value in line_data.items():
        if key == "DELETE":
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        if _is_zero_like(value):
            continue
        return True
    return False


def _resolve_user_org(user):
    if hasattr(user, "get_active_organization"):
        try:
            org = user.get_active_organization()
            if org:
                return org
        except Exception:
            pass
    return getattr(user, "organization", None)


def create_voucher_transaction(
    user,
    config_id: int,
    header_data: dict,
    lines_data: list,
    commit_type: str = "save",
    udf_header=None,
    udf_lines=None,
    idempotency_key: str | None = None,
):
    """
    Orchestrates voucher creation with full rollback guarantees.

    commit_type: 'save' (Draft), 'submit' (Approval), or 'post' (Finalize)
    """
    user_org = _resolve_user_org(user)
    try:
        if user_org is not None:
            config = VoucherModeConfig.objects.get(pk=config_id, organization=user_org)
        else:
            config = VoucherModeConfig.objects.get(pk=config_id)
    except VoucherModeConfig.DoesNotExist as exc:
        logger.error(
            "VoucherModeConfig %s not found for user %s org %s",
            config_id,
            getattr(user, "pk", None),
            getattr(user_org, "pk", None),
        )
        raise VoucherProcessError("VCH-001", "Invalid Voucher Configuration.") from exc

    hook_runner = HookRunner(user_org)
    hook_runner.run(
        "before_voucher_save",
        {"header": header_data, "lines": lines_data},
        raise_on_error=True,
    )

    journal_date = (
        header_data.get("journal_date")
        or header_data.get("voucher_date")
        or header_data.get("transaction_date")
        or header_data.get("receipt_date")
        or timezone.now().date()
    )
    if isinstance(journal_date, str):
        try:
            from datetime import datetime
            journal_date = datetime.strptime(journal_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise VoucherProcessError("VCH-003", f"Invalid journal date format: {journal_date}.") from exc

    period = AccountingPeriod.get_for_date(user_org, journal_date)
    if not period:
        raise VoucherProcessError("VCH-002", f"No open accounting period found for {journal_date}")

    currency_code = (
        header_data.get("currency_code")
        or header_data.get("currency")
        or getattr(getattr(user_org, "base_currency_code", None), "currency_code", None)
        or getattr(user_org, "base_currency_code", None)
        or "USD"
    )
    if hasattr(currency_code, "currency_code"):
        currency_code = currency_code.currency_code
    exchange_rate = header_data.get("exchange_rate", 1.0)

    with transaction.atomic():
        voucher = None
        if idempotency_key:
            voucher = Journal.objects.filter(
                organization=user_org,
                idempotency_key=idempotency_key,
            ).select_for_update().first()
            if voucher and voucher.journal_type_id != config.journal_type_id:
                raise VoucherProcessError("VCH-409", "Idempotency key already used for a different voucher type.")
            if voucher and voucher.status == "posted":
                return voucher
            if voucher is None:
                voucher = Journal(
                    organization=user_org,
                    journal_type=config.journal_type,
                    period=period,
                    journal_date=journal_date,
                    created_by=user,
                    status="draft",
                    currency_code=currency_code,
                    exchange_rate=exchange_rate,
                    description=header_data.get("description", ""),
                    reference=header_data.get("reference", ""),
                    idempotency_key=idempotency_key,
                )
            else:
                voucher.journal_type = config.journal_type
                voucher.period = period
                voucher.journal_date = journal_date
                voucher.currency_code = currency_code
                voucher.exchange_rate = exchange_rate
                voucher.description = header_data.get("description", "")
                voucher.reference = header_data.get("reference", "")
        else:
            voucher = Journal(
                organization=user_org,
                journal_type=config.journal_type,
                period=period,
                journal_date=journal_date,
                created_by=user,
                status="draft",
                currency_code=currency_code,
                exchange_rate=exchange_rate,
                description=header_data.get("description", ""),
                reference=header_data.get("reference", ""),
            )
        # Apply any remaining header fields that exist on the Journal model.
        reserved_keys = {
            "journal_date",
            "description",
            "reference",
            "currency_code",
            "currency",
            "exchange_rate",
        }
        for key, value in (header_data or {}).items():
            if key in reserved_keys:
                continue
            if hasattr(voucher, key):
                setattr(voucher, key, value)

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        journal_lines = []

        valid_lines = 0
        for idx, line_data in enumerate(lines_data or [], start=1):
            if line_data.get("DELETE"):
                continue
            if not _line_has_values(line_data):
                continue

            account_value = line_data.get("account") or line_data.get("account_id")
            account_value = _coerce_pk(account_value)
            if not account_value:
                account_value = _resolve_by_code_or_name(
                    ChartOfAccount,
                    user_org,
                    line_data.get("account_display")
                    or line_data.get("account_code")
                    or line_data.get("account_name"),
                    code_field="account_code",
                    name_field="account_name",
                )
            if not account_value:
                raise VoucherProcessError("VCH-004", f"Line {idx} requires an account.")

            debit = Decimal(str(line_data.get("debit_amount", 0) or 0))
            credit = Decimal(str(line_data.get("credit_amount", 0) or 0))
            if debit < 0 or credit < 0:
                raise VoucherProcessError("VCH-006", f"Line {idx} amounts must be positive.")
            if debit > 0 and credit > 0:
                raise VoucherProcessError("VCH-006", f"Line {idx} cannot have both debit and credit.")
            if debit == 0 and credit == 0:
                raise VoucherProcessError("VCH-006", f"Line {idx} requires a debit or credit amount.")
            total_debit += debit
            total_credit += credit
            valid_lines += 1

            line_udf = {}
            if udf_lines and len(udf_lines) > idx - 1:
                line_udf = udf_lines[idx - 1]

            cost_center_id = _resolve_fk_with_display(
                line_data, "cost_center", CostCenter, user_org, code_field="code", name_field="name"
            )
            department_id = _resolve_fk_with_display(
                line_data, "department", Department, user_org, code_field="code", name_field="name"
            )
            project_id = _resolve_fk_with_display(
                line_data, "project", Project, user_org, code_field="code", name_field="name"
            )

            line_kwargs = {
                "journal": voucher,
                "line_number": idx,
                "account_id": account_value,
                "description": line_data.get("description", ""),
                "debit_amount": debit,
                "credit_amount": credit,
                "cost_center_id": cost_center_id,
                "project_id": project_id,
                "department_id": department_id,
                "udf_data": line_udf,
            }
            # Only include optional fields if the model supports them.
            for optional_key in ("reference_id",):
                if optional_key in JournalLine._meta.fields_map:
                    line_kwargs[optional_key] = line_data.get(optional_key)
                else:
                    try:
                        JournalLine._meta.get_field(optional_key)
                        line_kwargs[optional_key] = line_data.get(optional_key)
                    except Exception:
                        pass

            journal_lines.append(JournalLine(**line_kwargs))

        if valid_lines == 0:
            raise VoucherProcessError("VCH-005", "At least one voucher line is required.")

        if hasattr(voucher, "total_debit"):
            voucher.total_debit = total_debit
        if hasattr(voucher, "total_credit"):
            voucher.total_credit = total_credit

        inventory_txns = []
        inventory_policy = {}
        # Prepare inventory metadata if configured.
        if config.affects_inventory:
            from inventory.models import Product, Warehouse, Location, Batch
            from accounting.models import ChartOfAccount

            try:
                settings = (config.schema_definition or {}).get("settings", {})
                inventory_policy = settings.get("inventory") if isinstance(settings, dict) else {}
            except Exception:
                inventory_policy = {}

            txn_type = None
            if isinstance(inventory_policy, dict):
                txn_type = inventory_policy.get("txn_type")
            txn_type = (txn_type or "issue").lower()

            default_grir = header_data.get("grir_account") or header_data.get("grir_account_id")
            default_cogs = header_data.get("cogs_account") or header_data.get("cogs_account_id")
            if default_grir and not isinstance(default_grir, (int,)):
                default_grir = _resolve_by_code_or_name(
                    ChartOfAccount,
                    user_org,
                    default_grir,
                    code_field="account_code",
                    name_field="account_name",
                )
            if default_cogs and not isinstance(default_cogs, (int,)):
                default_cogs = _resolve_by_code_or_name(
                    ChartOfAccount,
                    user_org,
                    default_cogs,
                    code_field="account_code",
                    name_field="account_name",
                )
            default_warehouse = header_data.get("warehouse") or header_data.get("warehouse_id")
            default_location = header_data.get("location") or header_data.get("location_id")

            for idx, line_data in enumerate(lines_data or [], start=1):
                if line_data.get("DELETE"):
                    continue
                if not _line_has_values(line_data):
                    continue

                product_id = _coerce_pk(line_data.get("product") or line_data.get("product_id"))
                product_code = line_data.get("product_code") or line_data.get("item_code")
                if not product_id and not product_code:
                    product_id = _resolve_by_code_or_name(
                        Product,
                        user_org,
                        line_data.get("product_display") or line_data.get("product_name"),
                        code_field="code",
                        name_field="name",
                    )
                warehouse_id = line_data.get("warehouse") or line_data.get("warehouse_id") or default_warehouse
                warehouse_code = line_data.get("warehouse_code")
                quantity_raw = line_data.get("quantity") or line_data.get("qty")
                unit_cost_raw = (
                    line_data.get("unit_cost")
                    or line_data.get("rate")
                    or line_data.get("unit_price")
                    or line_data.get("price")
                )
                location_id = line_data.get("location") or line_data.get("location_id") or default_location
                batch_id = line_data.get("batch") or line_data.get("batch_id")

                if not (product_id or product_code):
                    continue

                product = None
                if product_id:
                    product = Product.objects.filter(pk=product_id).first()
                elif product_code:
                    product = Product.objects.filter(
                        organization=user_org,
                        code=product_code,
                    ).first()
                if not product:
                    raise VoucherProcessError("INV-002", f"Inventory line {idx} has invalid product.")
                if product.organization_id != user_org.id:
                    raise VoucherProcessError("INV-002", "Inventory product must belong to the same organization.")
                if not getattr(product, "is_inventory_item", False):
                    raise VoucherProcessError("INV-003", f"Product {product.code} is not inventory-tracked.")

                uom_id = _coerce_pk(line_data.get("uom") or line_data.get("uom_id") or getattr(product, "base_unit_id", None))

                warehouse = None
                warehouse_id = _coerce_pk(warehouse_id)
                if not warehouse_id and line_data.get("warehouse_display"):
                    warehouse_id = _resolve_by_code_or_name(
                        Warehouse,
                        user_org,
                        line_data.get("warehouse_display"),
                        code_field="code",
                        name_field="name",
                    )
                if warehouse_id:
                    warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
                elif warehouse_code:
                    warehouse = Warehouse.objects.filter(
                        organization=user_org,
                        code=warehouse_code,
                    ).first()
                if not warehouse:
                    raise VoucherProcessError("INV-004", f"Inventory line {idx} requires a valid warehouse.")
                if warehouse.organization_id != user_org.id:
                    raise VoucherProcessError("INV-004", "Warehouse must belong to the same organization.")

                try:
                    quantity = Decimal(str(quantity_raw))
                except Exception as exc:
                    raise VoucherProcessError("INV-005", f"Inventory line {idx} has invalid quantity.") from exc
                if quantity <= 0:
                    raise VoucherProcessError("INV-005", f"Inventory line {idx} quantity must be greater than zero.")

                unit_cost = None
                if unit_cost_raw not in (None, ""):
                    try:
                        unit_cost = Decimal(str(unit_cost_raw))
                    except Exception as exc:
                        raise VoucherProcessError("INV-006", f"Inventory line {idx} has invalid unit cost.") from exc

                grir_account_id = _coerce_pk(line_data.get("grir_account") or line_data.get("grir_account_id") or default_grir)
                cogs_account_id = _coerce_pk(line_data.get("cogs_account") or line_data.get("cogs_account_id") or default_cogs)

                if txn_type == "receipt":
                    if unit_cost is None or unit_cost <= 0:
                        raise VoucherProcessError("INV-006", f"Inventory line {idx} requires a unit cost.")
                    if not grir_account_id:
                        raise VoucherProcessError("INV-007", "GR/IR account is required for inventory receipts.")
                    grir_account = ChartOfAccount.objects.filter(
                        pk=grir_account_id,
                        organization=user_org,
                    ).first()
                    if not grir_account:
                        raise VoucherProcessError("INV-007", "Invalid GR/IR account for inventory receipt.")
                else:
                    if not cogs_account_id:
                        cogs_account_id = getattr(product, "expense_account_id", None)
                    if not cogs_account_id:
                        raise VoucherProcessError("INV-008", "COGS account is required for inventory issues.")
                    cogs_account = ChartOfAccount.objects.filter(
                        pk=cogs_account_id,
                        organization=user_org,
                    ).first()
                    if not cogs_account:
                        raise VoucherProcessError("INV-008", "Invalid COGS account for inventory issue.")

                location_id = _coerce_pk(location_id) or None
                if location_id:
                    location = Location.objects.filter(pk=location_id).first()
                    if not location or location.warehouse_id != warehouse.id:
                        raise VoucherProcessError("INV-009", "Invalid location for selected warehouse.")

                batch_id = _coerce_pk(batch_id) or None
                if batch_id:
                    batch = Batch.objects.filter(pk=batch_id).first()
                    if not batch:
                        raise VoucherProcessError("INV-010", "Invalid batch/lot specified.")

                if not uom_id:
                    raise VoucherProcessError("INV-011", "Unit of measure is required for inventory lines.")

                inventory_txns.append({
                    "txn_type": txn_type,
                    "org_id": user_org.pk if user_org else None,
                    "product_id": product.pk,
                    "product_code": getattr(product, "code", None),
                    "warehouse_id": warehouse.pk,
                    "warehouse_code": getattr(warehouse, "code", None),
                    "uom_id": uom_id,
                    "quantity": str(quantity),
                    "unit_cost": str(unit_cost) if unit_cost is not None else None,
                    "location_id": location_id,
                    "batch_id": batch_id,
                    "grir_account_id": grir_account_id if txn_type == "receipt" else None,
                    "cogs_account_id": cogs_account_id if txn_type == "issue" else None,
                    "txn_date": str(journal_date),
                    "line_number": idx,
                })

            if inventory_txns:
                voucher.metadata = {
                    **(voucher.metadata or {}),
                    "inventory_transactions": inventory_txns,
                    "inventory_policy": inventory_policy or {},
                }

        voucher.save()
        # Replace lines on re-save to avoid duplicates.
        JournalLine.objects.filter(journal=voucher).delete()
        if journal_lines:
            JournalLine.objects.bulk_create(journal_lines)

        if inventory_txns:
            line_id_map = dict(
                JournalLine.objects.filter(journal=voucher).values_list("line_number", "journal_line_id")
            )
            for txn in inventory_txns:
                txn["voucher_id"] = voucher.pk
                txn["journal_id"] = voucher.pk
                txn["journal_number"] = voucher.journal_number
                line_id = line_id_map.get(txn.get("line_number"))
                if line_id:
                    txn["journal_line_id"] = line_id
                    txn["voucher_line_id"] = line_id
            voucher.metadata = {
                **(voucher.metadata or {}),
                "inventory_transactions": inventory_txns,
                "inventory_policy": inventory_policy or {},
            }
            voucher.save(update_fields=["metadata"])

        if commit_type == "submit":
            voucher.status = "awaiting_approval"
            voucher.save(update_fields=["status"])

        hook_runner.run(
            "after_voucher_save",
            {"journal_id": voucher.pk},
            raise_on_error=True,
        )

    if commit_type == "post":
        if total_debit != total_credit:
            raise VoucherProcessError(
                "GL-001",
                f"Voucher is imbalanced: Debit {total_debit} != Credit {total_credit}",
            )
        from accounting.services.voucher_orchestrator import VoucherOrchestrator
        try:
            voucher = VoucherOrchestrator(user).process(
                voucher_id=voucher.pk,
                commit_type="post",
                actor=user,
                idempotency_key=idempotency_key,
                config=config,
            )
        except VoucherProcessError:
            Journal.objects.filter(pk=voucher.pk).delete()
            raise
    return voucher


def create_voucher(user, config_id: int, header_data: dict, lines_data: list, udf_header=None, udf_lines=None):
    """
    Backwards-compatible wrapper for draft save.
    """
    return create_voucher_transaction(
        user=user,
        config_id=config_id,
        header_data=header_data,
        lines_data=lines_data,
        commit_type="save",
        udf_header=udf_header,
        udf_lines=udf_lines,
    )
