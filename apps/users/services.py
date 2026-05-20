from core.services import BaseService
from apps.tenants.services import is_platform_super_admin

from .repositories import UserRepository


class UserService(BaseService):
    repository_class = UserRepository

    def create(self, actor=None, **validated_data):
        if actor is not None and not is_platform_super_admin(actor) and "tenant" not in validated_data:
            validated_data["tenant"] = getattr(actor, "tenant", None)
        return super().create(actor=actor, **validated_data)

    def register_user(self, **validated_data):
        return self.repository.create_user(**validated_data)
