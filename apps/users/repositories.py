from django.contrib.auth import get_user_model

from core.repositories import BaseRepository
from apps.tenants.services import scope_users_to_requesting_tenant

User = get_user_model()


class UserRepository(BaseRepository):
    model = User

    def scope_queryset(self, queryset, user=None):
        return scope_users_to_requesting_tenant(queryset, user)

    def get_queryset(self, user=None):
        return super().get_queryset(user=user).order_by("-created_at")

    def create_user(self, **validated_data):
        password = validated_data.pop("password")
        return self.model.objects.create_user(password=password, **validated_data)
