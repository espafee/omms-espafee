from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.training.documents import TRAINING_DOCUMENTS, user_can_view_document, visible_documents_for_user


class TrainingDocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        documents = visible_documents_for_user(request.user)
        return Response(
            [
                {
                    "slug": document.slug,
                    "title": document.title,
                    "audience": document.audience,
                    "download_url": f"/api/v1/training/documents/{document.slug}/download/",
                }
                for document in documents
            ]
        )


class TrainingDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        document = TRAINING_DOCUMENTS.get(slug)
        if not document:
            raise Http404
        if not user_can_view_document(request.user, document):
            return Response({"detail": "You do not have permission to access this training document."}, status=403)
        if not document.path.exists():
            raise Http404

        return FileResponse(
            document.path.open("rb"),
            as_attachment=False,
            filename=document.filename,
            content_type="application/pdf",
        )
