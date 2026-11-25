from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.core.services import user_has_permission, user_has_role


def is_admin(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "role", None) in {"admin", "super_admin"}
            or user_has_role(user, "super_admin")
        )
    )


def is_university_admin(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            getattr(user, "role", None) == "university_admin"
            or user_has_role(user, "university_admin")
        )
    )


def is_teacher(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            getattr(user, "role", None) in {"teacher", "lecturer"}
            or user_has_role(user, "lecturer")
        )
    )


def is_student(user) -> bool:
    return bool(
        user.is_authenticated
        and (
            getattr(user, "role", None)
            in {"student", "free_student", "student_pro", "student_premium"}
            or user_has_role(user, "student")
            or user_has_role(user, "free_student")
            or user_has_role(user, "student_pro")
            or user_has_role(user, "student_premium")
        )
    )


def is_instructor(user) -> bool:
    return bool(user.is_authenticated and user_has_role(user, "instructor"))


def is_company(user) -> bool:
    return bool(
        user.is_authenticated
        and (getattr(user, "role", None) == "company" or user_has_role(user, "company"))
    )


def has_portal_permission(user, code: str) -> bool:
    return bool(user.is_authenticated and user_has_permission(user, code))


def can_manage_course(user, course) -> bool:
    if not user.is_authenticated:
        return False
    return is_admin(user) or course.teacher_id == user.id


def can_access_course(user, course) -> bool:
    if not user.is_authenticated:
        return False
    if is_admin(user) or course.teacher_id == user.id:
        return True
    if is_student(user):
        return course.enrollments.filter(student=user).exists()
    return False


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request)
        if is_admin(request.user) or any(
            user_has_role(request.user, role) for role in self.allowed_roles
        ):
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied("You do not have permission to access this page.")


def redirect_to_login(request):
    from django.contrib.auth.views import redirect_to_login as auth_redirect

    return auth_redirect(request.get_full_path())


def role_required(*roles):
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request)
            if is_admin(request.user) or any(
                user_has_role(request.user, role) for role in roles
            ):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")

        return wrapped

    return decorator
