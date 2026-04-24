class BaseRepository:
    model = None
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[str, ...] = ()

    def _build_base_queryset(self):
        if self.model is None:
            raise ValueError("BaseRepository requires a model.")

        queryset = self.model.objects.all()
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)
        return queryset

    def scope_queryset(self, queryset, user=None):
        return queryset

    def get_queryset(self, user=None):
        queryset = self._build_base_queryset()
        return self.scope_queryset(queryset, user=user)

    def has_access(self, user, obj):
        if self.model is None or obj is None:
            return False
        return self.get_queryset(user=user).filter(pk=obj.pk).exists()

    def create(self, **validated_data):
        if self.model is None:
            raise ValueError("BaseRepository requires a model.")
        return self.model.objects.create(**validated_data)

    def update(self, instance, **validated_data):
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()
        return instance

    def delete(self, instance):
        instance.delete()
