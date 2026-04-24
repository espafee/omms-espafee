from core.services import BaseService

from .repositories import UserRepository


class UserService(BaseService):
    repository_class = UserRepository

    def register_user(self, **validated_data):
        return self.repository.create_user(**validated_data)
