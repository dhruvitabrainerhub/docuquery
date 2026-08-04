import re
import json
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Documents, ChatSession, ChatMessage
from .serializers import DocumentUploadSerializer
from .tasks import process_document_task
from .services.rag_service import RAGService


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


def _get_history(session):
    messages = ChatMessage.objects.filter(session=session).order_by('created_at')
    clean = []
    for msg in messages:
        content = re.sub(r'(PAGES_USED|SOURCES_USED)\s*:.*', '', msg.content, flags=re.IGNORECASE).strip()
        if content:
            clean.append(f"{msg.role}: {content}\n")
    return ''.join(clean)


# class ChatView(APIView):
#     """Non-streaming — returns full answer at once."""
#     def post(self, request, session_id):
#         question = request.data.get('question', '').strip()
#         if not question:
#             return Response({'error': 'question is required'}, status=400)
#
#         try:
#             session = ChatSession.objects.get(id=session_id, user=request.user)
#         except ChatSession.DoesNotExist:
#             return Response({'error': 'session not found'}, status=404)
#
#         history = _get_history(session)
#         res = RAGService.ask(question, history=history, user_id=str(request.user.id))
#
#         ChatMessage.objects.create(session=session, role='user', content=question)
#         ChatMessage.objects.create(session=session, role='assistant', content=res['answer'])
#
#         return Response({'answer': res['answer'], 'sources': res['sources']})


class ChatStreamView(APIView):
    """SSE streaming — tokens pushed as Server-Sent Events."""
    def post(self, request, session_id):
        question = request.data.get('question', '').strip()
        if not question:
            return Response({'error': 'question is required'}, status=400)

        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({'error': 'session not found'}, status=404)

        history  = _get_history(session)
        user_id  = str(request.user.id)

        def event_stream():
            full_answer = ''
            for event in RAGService.stream_answer(question, history=history, user_id=user_id):
                if event['type'] == 'token':
                    full_answer += event['content']
                    yield f"data: {json.dumps(event)}\n\n"
                elif event['type'] == 'retrieving_done':
                    yield f"data: {json.dumps(event)}\n\n"
                elif event['type'] == 'complete':
                    # Save messages once answer is complete
                    ChatMessage.objects.create(session=session, role='user', content=question)
                    ChatMessage.objects.create(session=session, role='assistant', content=full_answer.strip())
                    yield f"data: {json.dumps(event)}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


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


class ChromaDebugView(APIView):
    def get(self, request):
        try:
            from .services.embeddings import get_vector_db
            vector_db    = get_vector_db()
            user_id_str  = str(request.user.id)
            all_data     = vector_db.get(include=['metadatas', 'documents'])
            all_metadatas = all_data.get('metadatas') or []
            all_documents = all_data.get('documents') or []
            unique_user_ids = list({str(m.get('user_id', 'N/A')) for m in all_metadatas})
            user_chunks = [
                {'source': m.get('source'), 'page': m.get('page'), 'chunk_preview': d[:120]}
                for m, d in zip(all_metadatas, all_documents)
                if str(m.get('user_id', '')) == user_id_str
            ]
            return Response({
                'logged_in_user_id': user_id_str,
                'total_chunks_in_db': len(all_metadatas),
                'unique_user_ids_in_db': unique_user_ids,
                'your_chunks_count': len(user_chunks),
                'your_chunks_sample': user_chunks[:10],
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)