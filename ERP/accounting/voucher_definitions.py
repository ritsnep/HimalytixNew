from __future__ import annotations

from typing import Dict, List


def _amount_field(key: str, label: str) -> Dict:
    return {
        "key": key,
        "label": label,
        "field_type": "decimal",
        "required": False,
        "validators": {"min": 0, "step": "0.01"},
    }


def _account_field(key: str = "account", label: str = "Account") -> Dict:
    return {
        "key": key,
        "label": label,
        "field_type": "typeahead",
        "required": True,
        "lookup": {"model": "ChartOfAccount", "kind": "account"},
    }


def _party_field(key: str, label: str, kind: str) -> Dict:
    return {
        "key": key,
        "label": label,
        "field_type": "typeahead",
        "required": False,
        "lookup": {"model": kind.title(), "kind": kind},
    }


def _inventory_fields(txn_type: str) -> List[Dict]:
    requires_unit_cost = txn_type == "receipt"
    return [
        {
            "key": "product",
            "label": "Product",
            "field_type": "typeahead",
            "required": True,
            "lookup": {"model": "Product", "kind": "product"},
        },
        {
            "key": "warehouse",
            "label": "Warehouse",
            "field_type": "typeahead",
            "required": True,
            "lookup": {"model": "Warehouse", "kind": "warehouse"},
        },
        {
            "key": "uom",
            "label": "UOM",
            "field_type": "char",
            "required": False,
        },
        {
            "key": "quantity",
            "label": "Quantity",
            "field_type": "decimal",
            "required": True,
            "validators": {"min": 0, "step": "0.01"},
        },
        {
            "key": "unit_cost",
            "label": "Unit Cost",
            "field_type": "decimal",
            "required": requires_unit_cost,
            "validators": {"min": 0, "step": "0.01"},
        },
    ]


def _gl_account_lookup_field(key: str, label: str, *, required: bool) -> Dict:
    return {
        "key": key,
        "label": label,
        "field_type": "typeahead",
        "required": required,
        "lookup": {"model": "ChartOfAccount", "kind": "account"},
    }


def _base_header_fields() -> List[Dict]:
    return [
        {
            "key": "journal_date",
            "label": "Date",
            "field_type": "date",
            "required": True,
            "ui": {"autofocus": True},
        },
        {
            "key": "reference",
            "label": "Reference",
            "field_type": "char",
            "required": False,
        },
        {
            "key": "description",
            "label": "Description",
            "field_type": "textarea",
            "required": False,
        },
        {
            "key": "currency_code",
            "label": "Currency",
            "field_type": "select",
            "required": False,
            "choices": "Currency",
        },
        {
            "key": "exchange_rate",
            "label": "Exchange Rate",
            "field_type": "decimal",
            "required": False,
            "validators": {"min": 0, "step": "0.0001"},
        },
    ]


def _base_line_fields() -> List[Dict]:
    return [
        _account_field(),
        {"key": "description", "label": "Description", "field_type": "char", "required": False},
        _amount_field("debit_amount", "Debit"),
        _amount_field("credit_amount", "Credit"),
        {
            "key": "cost_center",
            "label": "Cost Center",
            "field_type": "typeahead",
            "required": False,
            "lookup": {"model": "CostCenter", "kind": "costcenter"},
        },
        {
            "key": "department",
            "label": "Department",
            "field_type": "typeahead",
            "required": False,
            "lookup": {"model": "Department", "kind": "department"},
        },
        {
            "key": "project",
            "label": "Project",
            "field_type": "typeahead",
            "required": False,
            "lookup": {"model": "Project", "kind": "project"},
        },
    ]


DEFAULT_WORKFLOW = {
    "states": ["draft", "pending_approval", "posted", "failed"],
    "transitions": {
        "draft": ["pending_approval", "posted"],
        "pending_approval": ["posted", "failed"],
        "posted": [],
        "failed": ["draft"],
    },
}


VOUCHER_DEFINITIONS: List[Dict] = [
    {
        "code": "JOURNAL",
        "name": "General Journal",
        "module": "accounting",
        "journal_type_code": "GJ",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields(),
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "CASH-RECEIPT",
        "name": "Cash Receipt",
        "module": "cash",
        "journal_type_code": "CR",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("customer", "Customer", "customer")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "CASH-PAYMENT",
        "name": "Cash Payment",
        "module": "cash",
        "journal_type_code": "CP",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("vendor", "Vendor", "vendor")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "BANK-RECEIPT",
        "name": "Bank Receipt",
        "module": "banking",
        "journal_type_code": "BR",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("customer", "Customer", "customer")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "BANK-PAYMENT",
        "name": "Bank Payment",
        "module": "banking",
        "journal_type_code": "BP",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("vendor", "Vendor", "vendor")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "BANK-TRANSFER",
        "name": "Bank Transfer",
        "module": "banking",
        "journal_type_code": "BT",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields(),
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "CASH-TRANSFER",
        "name": "Cash Transfer",
        "module": "cash",
        "journal_type_code": "CT",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields(),
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "AR-RECEIPT",
        "name": "AR Receipt",
        "module": "accounting",
        "journal_type_code": "ARR",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("customer", "Customer", "customer")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "AP-PAYMENT",
        "name": "AP Payment",
        "module": "accounting",
        "journal_type_code": "APP",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [_party_field("vendor", "Vendor", "vendor")],
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "SALES-INVOICE",
        "name": "Sales Invoice",
        "module": "sales",
        "journal_type_code": "SI",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _party_field("customer", "Customer", "customer"),
                _gl_account_lookup_field("cogs_account", "COGS Account", required=False),
            ],
            "line_fields": _inventory_fields("issue") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "issue"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "SALES-RETURN",
        "name": "Sales Return",
        "module": "sales",
        "journal_type_code": "SR",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _party_field("customer", "Customer", "customer"),
                _gl_account_lookup_field("grir_account", "GR/IR Account", required=True),
            ],
            "line_fields": _inventory_fields("receipt") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "receipt"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "PURCHASE-INVOICE",
        "name": "Purchase Invoice",
        "module": "purchasing",
        "journal_type_code": "PI",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _party_field("vendor", "Vendor", "vendor"),
                _gl_account_lookup_field("grir_account", "GR/IR Account", required=True),
            ],
            "line_fields": _inventory_fields("receipt") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "receipt"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "PURCHASE-RETURN",
        "name": "Purchase Return",
        "module": "purchasing",
        "journal_type_code": "PR",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _party_field("vendor", "Vendor", "vendor"),
                _gl_account_lookup_field("cogs_account", "COGS Account", required=False),
            ],
            "line_fields": _inventory_fields("issue") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "issue"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "DEBIT-NOTE",
        "name": "Debit Note",
        "module": "accounting",
        "journal_type_code": "DN",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields(),
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "CREDIT-NOTE",
        "name": "Credit Note",
        "module": "accounting",
        "journal_type_code": "CN",
        "affects_gl": True,
        "affects_inventory": False,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields(),
            "line_fields": _base_line_fields(),
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "LANDED-COST",
        "name": "Landed Cost",
        "module": "inventory",
        "journal_type_code": "LC",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _gl_account_lookup_field("grir_account", "GR/IR Account", required=True),
            ],
            "line_fields": _inventory_fields("receipt") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "receipt"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
    {
        "code": "INVENTORY-ADJUSTMENT",
        "name": "Inventory Adjustment",
        "module": "inventory",
        "journal_type_code": "IA",
        "affects_gl": True,
        "affects_inventory": True,
        "requires_approval": False,
        "schema": {
            "header_fields": _base_header_fields() + [
                _gl_account_lookup_field("cogs_account", "COGS Account", required=False),
            ],
            "line_fields": _inventory_fields("issue") + _base_line_fields(),
            "settings": {"inventory": {"txn_type": "issue"}},
        },
        "workflow": DEFAULT_WORKFLOW,
    },
]


def journal_type_seed() -> Dict[str, str]:
    return {
        "GJ": "General Journal",
        "CR": "Cash Receipt",
        "CP": "Cash Payment",
        "BR": "Bank Receipt",
        "BP": "Bank Payment",
        "BT": "Bank Transfer",
        "CT": "Cash Transfer",
        "ARR": "AR Receipt",
        "APP": "AP Payment",
        "SI": "Sales Invoice",
        "SR": "Sales Return",
        "PI": "Purchase Invoice",
        "PR": "Purchase Return",
        "DN": "Debit Note",
        "CN": "Credit Note",
        "LC": "Landed Cost",
        "IA": "Inventory Adjustment",
    }
