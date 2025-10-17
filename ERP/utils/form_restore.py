def get_pending_form_initial(request):
    pending = request.session.get('pending_forms', {})
    path = request.path
    data = pending.get(path)
    return data if data else None

def clear_pending_form(request):
    pending = request.session.get('pending_forms', {})
    path = request.path
    if path in pending:
        del pending[path]
        request.session['pending_forms'] = pending
