from django.db.models import Q
from django.utils import timezone

from .constants import ROLE_ALIASES
from .models import Permission, Role, UserPermissionOverride


def get_active_roles(user):
    if not getattr(user, "is_authenticated", False):
        return Role.objects.none()
    if getattr(user, "is_superuser", False):
        return Role.objects.filter(is_active=True)
    now = timezone.now()
    return (
        Role.objects.filter(is_active=True, user_links__user=user)
        .filter(Q(user_links__expires_at__isnull=True) | Q(user_links__expires_at__gt=now))
        .distinct()
    )


def user_has_role(user, code: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not code:
        return False

    aliases = set(ROLE_ALIASES.get(code, set()))
    aliases.add(code)
    legacy_role = getattr(user, "role", None)
    if legacy_role in aliases:
        return True
    return get_active_roles(user).filter(code__in=aliases).exists()


def get_user_permissions(user) -> set[str]:
    if not getattr(user, "is_authenticated", False):
        return set()

    cached = getattr(user, "_portal_permission_cache", None)
    if cached is not None:
        return set(cached)

    if getattr(user, "is_superuser", False):
        codes = set(Permission.objects.filter(is_active=True).values_list("code", flat=True))
    else:
        codes = set(
            Permission.objects.filter(
                is_active=True, role_links__role__in=get_active_roles(user)
            ).values_list("code", flat=True)
        )
        legacy_role = getattr(user, "role", None)
        if legacy_role:
            legacy_codes = set(ROLE_ALIASES.get(legacy_role, set())) | {legacy_role}
            codes.update(
                Permission.objects.filter(
                    is_active=True, role_links__role__code__in=legacy_codes
                ).values_list("code", flat=True)
            )
        overrides = UserPermissionOverride.objects.filter(
            user=user, permission__is_active=True
        ).select_related("permission")
        for override in overrides:
            if override.is_granted:
                codes.add(override.permission.code)
            else:
                codes.discard(override.permission.code)

    setattr(user, "_portal_permission_cache", codes)
    return codes


def user_has_permission(user, code: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not code:
        return False
    return code in get_user_permissions(user)


def user_has_any_permission(user, codes) -> bool:
    return any(user_has_permission(user, code) for code in codes)


def get_primary_role(user):
    return get_active_roles(user).order_by("-level").first()
