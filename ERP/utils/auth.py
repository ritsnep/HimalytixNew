# ERP/utils/auth.py
def get_user_organization(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    if hasattr(user, 'get_active_organization'):
        organization = user.get_active_organization()
        if organization:
            return organization

    if hasattr(user, 'organization'):
        return user.organization
    return None
