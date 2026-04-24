from rest_framework.permissions import SAFE_METHODS, BasePermission


class RoleBasedPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def _is_admin(self, user):
        return bool(user and (getattr(user, "is_superuser", False) or getattr(user, "role", None) == "admin"))

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if self._is_admin(user):
            return True

        allowed_roles = getattr(view, "allowed_roles", ())
        write_roles = getattr(view, "write_roles", allowed_roles)
        action = getattr(view, "action", None)
        action_write_roles = getattr(view, "write_roles_by_action", {})
        if request.method not in SAFE_METHODS and action and action in action_write_roles:
            write_roles = action_write_roles[action]

        if request.method in SAFE_METHODS:
            return not allowed_roles or getattr(user, "role", None) in allowed_roles
        return not write_roles or getattr(user, "role", None) in write_roles

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if self._is_admin(user):
            return True

        if not self.has_permission(request, view):
            return False

        if hasattr(view, "get_service"):
            return view.get_service().has_object_access(user, obj)
        return True
