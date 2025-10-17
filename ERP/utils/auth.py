# ERP/utils/auth.py
def get_user_organization(user):
    if user.is_authenticated and hasattr(user, 'organization'):
        return user.organization
    return None