from rest_framework.permissions import BasePermission

from .services import user_has_permission


class HasPortalPermission(BasePermission):
    permission_code = None

    def has_permission(self, request, view):
        code = getattr(view, "permission_code", self.permission_code)
        if not code:
            return True
        return user_has_permission(request.user, code)
