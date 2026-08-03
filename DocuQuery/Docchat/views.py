import re
from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Documents, ChatSession, ChatMessage
from .serializers import DocumentUploadSerializer
from .services.parser import extract_text
from .services.chunker import create
from .services.embeddings import get_vector_db
from .services.rag_pipeline import llm
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics
from langchain.retrievers.multi_query import MultiQueryRetriever
from collections import defaultdict

from .tasks import process_document_task
from .services.rag_service import RAGService


class UploadDocumentView(generics.CreateAPIView):
    queryset = Documents.objects.all()
    serializer_class = DocumentUploadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# class ProcessDocumentView(APIView):
#     def post(self, request, document_id):
#         try:
#             document = Documents.objects.get(id=document_id, user=request.user)
#         except Documents.DoesNotExist:
#             return Response({'error': 'Document not found or access denied'}, status=404)
        
#         #change status to processing and processed to false in admin panel and save the document
#         document.status = Documents.Status.PROCESSING
#         document.processed = False
#         document.save(update_fields=['status', 'processed'])

#         task = process_document_task.delay(document.id)    

#         document.task_id = task.id
#         document.save(update_fields=['task_id'])
#         return Response({
#             'message': 'Document reprocessing started.',
#             'document_id': document.id,
#             'task_id': task.id,
#             'status': document.status,
#         })
    
#         vector_db = get_vector_db()
#         old = vector_db.get(where={'document_id': document.id})
#         if old and old.get('ids'):
#             vector_db.delete(ids = old['ids'])

#         pages = extract_text(document.file.path)
#         all_chunks = []
#         all_metadatas = []

#         for page_data in pages:
#             page_number = page_data['page']
#             text = page_data['text']
#             chunks = create(text)

#             if not chunks:
#                 continue

#             for idx, chunk in enumerate(chunks):
#                 all_chunks.append(chunk)
#                 all_metadatas.append({
#                     'document_id': document.id,
#                     'user_id': str(request.user.id),
#                     'source': document.file.name,
#                     'page': page_number,
#                     'chunk_id': idx
#                 })

#         if not all_chunks:
#             document.status = Documents.Status.FAILED
#             document.processed = False
#             document.save(update_fields = ['status','processed'])
#             return Response({'error': 'No text chunks created from document'}, status=400)

#         get_vector_db().add_texts(texts=all_chunks, metadatas=all_metadatas)
#         document.processed = True
#         document.status = Documents.Status.DONE
#         document.save(update_fields = ['status','processed'])
#         return Response({'messages': 'document processed'})

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
        session = ChatSession.objects.create(
            title='New Chat',
            user=request.user,
        )
        return Response({'session_id': session.id, 'title': session.title, 'user_id': request.user.id})


class ChatView(APIView):
    def post(self, request, session_id):
        question = request.data.get('question', '').strip()

        if not question:
            return Response({'error': 'question is required'}, status=400)

        try:
            session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return Response({'error': 'session not found or does not belong to this user'}, status=404)

        history_messages = ChatMessage.objects.filter(session=session).order_by('created_at')
        clean_history = []
        for msg in history_messages:
            content = msg.content
            # Strip both old PAGES_USED and new SOURCES_USED system tags from history
            content = re.sub(r'(PAGES_USED|SOURCES_USED)\s*:.*', '', content, flags=re.IGNORECASE).strip()
            if content:
                clean_history.append(f"{msg.role}: {content}\n")
        history = "".join(clean_history)

        res = RAGService.ask(question, history=history, user_id=str(request.user.id))

        ChatMessage.objects.create(session=session, role='user', content=question)
        ChatMessage.objects.create(session=session, role='assistant', content=res['answer'])

        return Response({
            'answer': res['answer'],
            'sources': res['sources']
        })


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
    """
    Debug endpoint — shows what is actually stored in ChromaDB for this user.
    GET /api/chroma-debug/
    """
    def get(self, request):
        try:
            vector_db = get_vector_db()
            user_id_str = str(request.user.id)

            # Fetch all entries from the collection
            all_data = vector_db.get(include=['metadatas', 'documents'])
            all_metadatas = all_data.get('metadatas') or []
            all_documents = all_data.get('documents') or []

            # Unique user_ids stored
            unique_user_ids = list({str(m.get('user_id', 'N/A')) for m in all_metadatas})

            # Filter only this user's chunks
            user_chunks = []
            for meta, doc_text in zip(all_metadatas, all_documents):
                if str(meta.get('user_id', '')) == user_id_str:
                    user_chunks.append({
                        'source': meta.get('source'),
                        'page': meta.get('page'),
                        'user_id': meta.get('user_id'),
                        'chunk_preview': doc_text[:120] if doc_text else '',
                    })

            return Response({
                'logged_in_user_id': user_id_str,
                'total_chunks_in_db': len(all_metadatas),
                'unique_user_ids_in_db': unique_user_ids,
                'your_chunks_count': len(user_chunks),
                'your_chunks_sample': user_chunks[:10],
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)