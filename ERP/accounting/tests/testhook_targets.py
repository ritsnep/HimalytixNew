"""Support module for hook runner tests."""

recorded_events = []


def reset():
    recorded_events.clear()


def _record(event_name, context):
    recorded_events.append((event_name, context))


def before_voucher_save_hook(context):
    _record("before_voucher_save", context)


def after_voucher_save_hook(context):
    _record("after_voucher_save", context)


def after_journal_post_hook(context):
    _record("after_journal_post", context)
