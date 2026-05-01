from rest_framework.permissions import BasePermission


ADMIN_MOBILE_ROLES = {"admin", "super_admin", "owner"}


def is_mobile_admin_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "role", None) in ADMIN_MOBILE_ROLES
    )


class IsMobileAdmin(BasePermission):
    message = "Only admin users can access the mobile operations dashboard."

    def has_permission(self, request, view):
        return is_mobile_admin_user(request.user)
