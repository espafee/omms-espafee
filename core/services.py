from django.db import transaction

from .repositories import BaseRepository


class BaseService:
    repository_class = BaseRepository

    def __init__(self, repository=None):
        self.repository = repository or self.repository_class()

    def get_queryset(self, user=None):
        return self.repository.get_queryset(user=user)

    def has_object_access(self, user, obj):
        return self.repository.has_access(user, obj)

    @transaction.atomic
    def create(self, actor=None, **validated_data):
        return self.repository.create(**validated_data)

    @transaction.atomic
    def update(self, instance, actor=None, **validated_data):
        return self.repository.update(instance, **validated_data)

    @transaction.atomic
    def delete(self, instance, actor=None):
        self.repository.delete(instance)
