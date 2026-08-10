import re
import json
import os
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from .models import Documents, ChatSession, ChatMessage
from .serializers import DocumentUploadSerializer
from .tasks import process_document_task
from .services.rag_service import RAGService
from django.http import FileResponse, Http404

class UploadDocumentView(generics.CreateAPIView):
    queryset = Documents.objects.all()
    serializer_class = DocumentUploadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProcessDocumentView(APIView):
    def post(self, request, document_id):
        try:
            document = Documents.objects.get(id=document_id, user=request.user)
        except Documents.DoesNotExist:
            return Response({'error': 'Document not found or access denied'}, status=404)

        document.status = Documents.Status.PROCESSING
        document.processed = False
        document.task_id = None
        document.save(update_fields=['status', 'processed', 'task_id'])

        task = process_document_task.delay(document.id)
        document.task_id = task.id
        document.save(update_fields=['task_id'])

        return Response({
            'message': 'Document reprocessing started.',
            'document_id': document.id,
            'task_id': task.id,
            'status': document.status,
        })


class CreateSessionView(APIView):
    def post(self, request):
        session = ChatSession.objects.create(title='New Chat', user=request.user)
        return Response({'session_id': session.id, 'title': session.title, 'user_id': request.user.id})


class DocumentStatusView(APIView):
    def get(self, request, document_id):
        try:
            doc = Documents.objects.get(id=document_id, user=request.user)
        except Documents.DoesNotExist:
            return Response({'error': 'Document not found'}, status=404)

        from celery.result import AsyncResult
        celery_status = AsyncResult(doc.task_id).status if doc.task_id else None

        return Response({
            'document_id': doc.id,
            'task_id': doc.task_id,
            'document_status': doc.status,
            'celery_status': celery_status,
            'processed': doc.processed,
        })

class MediaDownloadView(APIView):
    def get(self, request, file_path):
        doc = Documents.objects.filter(
            user = request.user,
            file = f"documents/{file_path}"
        ).first()

        if not doc:
            raise Http404("File not found or access denied.")

        full_path = doc.file.path
        if not os.path.exists(full_path):
            raise Http404
        
        return FileResponse(open(full_path, 'rb'), as_attachment=True)
