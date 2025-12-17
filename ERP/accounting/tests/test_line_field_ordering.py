from accounting.forms_factory import VoucherFormFactory


def test_line_field_ordering_dict_schema():
    # Schema provided as dict in random order
    lines_schema = {
        'cost_center': {'label': 'Cost Center', 'type': 'char'},
        'amount': {'label': 'Amount', 'type': 'decimal'},
        'description': {'label': 'Description', 'type': 'char'},
        'account': {'label': 'Account', 'type': 'char'},
        'credit': {'label': 'Credit', 'type': 'decimal'},
        'debit': {'label': 'Debit', 'type': 'decimal'},
        'line_number': {'label': 'Line #', 'type': 'integer'},
    }

    config = {'lines': lines_schema}
    factory = VoucherFormFactory(config, organization=None)
    FormSet = factory.build_formset(extra=1)
    fs = FormSet()
    form = fs.forms[0]

    # Note: `visible_fields` is a method that returns an iterable of BoundField
    visible = [f.name for f in form.visible_fields()]

    # Expected start of ordering: line_number, account, description, debit, credit, amount, cost_center
    expected_prefix = ['line_number', 'account', 'description']
    assert visible[:3] == expected_prefix, f"Unexpected ordering: {visible[:6]}"


def test_line_field_ordering_list_schema():
    # Schema provided as a list in random order
    lines_schema = [
        {'name': 'cost_center', 'label': 'Cost Center', 'type': 'char'},
        {'name': 'amount', 'label': 'Amount', 'type': 'decimal'},
        {'name': 'description', 'label': 'Description', 'type': 'char'},
        {'name': 'account', 'label': 'Account', 'type': 'char'},
        {'name': 'credit', 'label': 'Credit', 'type': 'decimal'},
        {'name': 'debit', 'label': 'Debit', 'type': 'decimal'},
        {'name': 'line_number', 'label': 'Line #', 'type': 'integer'},
    ]

    config = {'lines': list(lines_schema)}
    factory = VoucherFormFactory(config, organization=None)
    FormSet = factory.build_formset(extra=1)
    fs = FormSet()
    form = fs.forms[0]

    visible = [f.name for f in form.visible_fields()]
    expected_prefix = ['line_number', 'account', 'description']
    assert visible[:3] == expected_prefix, f"Unexpected ordering for list schema: {visible[:6]}"
