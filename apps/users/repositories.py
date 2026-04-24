from django.contrib.auth import get_user_model

from core.repositories import BaseRepository

User = get_user_model()


class UserRepository(BaseRepository):
    model = User

    def get_queryset(self, user=None):
        return super().get_queryset(user=user).order_by("-created_at")

    def create_user(self, **validated_data):
        password = validated_data.pop("password")
        return self.model.objects.create_user(password=password, **validated_data)
