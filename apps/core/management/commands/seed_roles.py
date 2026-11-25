from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.constants import (
    LEGACY_ROLE_MAP,
    PERMISSION_DEFINITIONS,
    ROLE_DEFINITIONS,
    ROLE_PERMISSIONS,
)
from apps.core.models import Permission, Role, RolePermission, UserRole


class Command(BaseCommand):
    help = "Create the platform roles, permissions, and default role assignments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-user-assignment",
            action="store_true",
            help="Do not assign portal roles to existing users.",
        )

    def handle(self, *args, **options):
        roles = {}
        for code, name, level in ROLE_DEFINITIONS:
            role, _ = Role.objects.get_or_create(
                code=code,
                defaults={"name": name, "level": level, "is_system": True},
            )
            roles[code] = role

        permissions = {}
        for code, name, category in PERMISSION_DEFINITIONS:
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": name, "category": category, "is_active": True},
            )
            permissions[code] = permission

        role_links = 0
        for code, permission_codes in ROLE_PERMISSIONS.items():
            role = roles[code]
            for permission_code in permission_codes:
                permission = permissions[permission_code]
                _, created = RolePermission.objects.get_or_create(
                    role=role, permission=permission
                )
                role_links += int(created)

        assignments = 0
        if not options["skip_user_assignment"]:
            user_model = get_user_model()
            for user in user_model.objects.all().only("id", "email", "role", "is_superuser").iterator():
                if user.is_superuser:
                    role_code = "super_admin"
                else:
                    role_code = LEGACY_ROLE_MAP.get(getattr(user, "role", ""), "free_student")
                _, created = UserRole.objects.get_or_create(
                    user=user,
                    role=roles[role_code],
                    defaults={"is_primary": True},
                )
                assignments += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Roles: {len(roles)}, permissions: {len(permissions)}, "
                f"role links created: {role_links}, user assignments created: {assignments}"
            )
        )
