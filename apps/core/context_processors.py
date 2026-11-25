from .services import get_active_roles, get_user_permissions, user_has_permission


def rbac(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "portal_roles": [],
            "portal_permissions": set(),
            "can_manage_platform": False,
        }

    permissions = get_user_permissions(user)
    return {
        "portal_roles": list(get_active_roles(user).values_list("code", flat=True)),
        "portal_permissions": permissions,
        "can_manage_platform": user_has_permission(user, "settings.manage")
        or user_has_permission(user, "payment.verify"),
    }
