from rest_framework.viewsets import ModelViewSet


class ServiceModelViewSet(ModelViewSet):
    service_class = None

    def get_service(self):
        if self.service_class is None:
            raise ValueError("service_class must be set on ServiceModelViewSet subclasses.")
        return self.service_class()

    def get_queryset(self):
        if self.service_class is None:
            return super().get_queryset()
        return self.get_service().get_queryset(user=self.request.user)

    def perform_create(self, serializer):
        if self.service_class is None:
            serializer.save()
            return

        serializer.instance = self.get_service().create(
            actor=self.request.user,
            **serializer.validated_data,
        )

    def perform_update(self, serializer):
        if self.service_class is None:
            serializer.save()
            return

        serializer.instance = self.get_service().update(
            serializer.instance,
            actor=self.request.user,
            **serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if self.service_class is None:
            instance.delete()
            return

        self.get_service().delete(
            instance,
            actor=self.request.user,
        )
