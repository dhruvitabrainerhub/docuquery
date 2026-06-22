import re
import os
from collections import defaultdict

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Documents, ChatSession, ChatMessage
from .serializers import DocumentUploadSerializer
from .services.chunker import create
from .services.embeddings import vector_db
from .services.parser import extract_text
from .services.rag_pipeline import llm
from langchain.retrievers.multi_query import MultiQueryRetriever

class UploadDocumentView(generics.CreateAPIView): #DRF handle 
    queryset = Documents.objects.all()
    serializer_class = DocumentUploadSerializer
    parser_classes = [MultiPartParser, FormParser]


class ProcessDocumentView(APIView):
    def post(self, request, document_id):
        document = get_object_or_404(Documents, id=document_id)

        force = request.data.get('force', False)
        if document.processed and not force:
            return Response(
                {'error': 'Already processed. Send force=true to re-process.'},
                status=status.HTTP_400_BAD_REQUEST
            )    
        if not os.path.exists(document.file.path):
            return Response(
                {'error': 'File not found on disk. Please re-upload the document.'},
                status=status.HTTP_404_NOT_FOUND
            )         

        # delete old vectors for this document before re-embedding
        old = vector_db.get(where={'document_id': document.id})
        if old and old.get('ids'):
            vector_db.delete(ids=old['ids'])                     

        pages = extract_text(document.file.path)
        all_chunks, all_metadatas = [], []

        for page_data in pages:
            chunks = create(page_data['text'])
            if not chunks:
                continue
            for idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    'document_id': document.id,
                    'source': document.file.name,
                    'page': page_data['page'],
                    'chunk_id': idx
                })

        if not all_chunks:
            return Response({'error': 'No text chunks created from document.'}, status=status.HTTP_400_BAD_REQUEST)

        vector_db.add_texts(texts=all_chunks, metadatas=all_metadatas)

        document.processed = True
        document.save()

        return Response({'message': 'Document processed successfully.'})


class CreateSessionView(APIView):
    def post(self, request):
        session = ChatSession.objects.create(title='New Chat')
        return Response({'session_id': session.id, 'title': session.title})


class ChatView(APIView):
    def post(self, request, session_id):
        question = request.data.get('question', '').strip()
        if not question:
            return Response({'error': 'question is required.'}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(ChatSession, id=session_id)

        history = ''.join(
            f"{msg.role}: {msg.content}\n"
            for msg in session.messages.order_by('created_at')
        )

        #multiqueryretriever splits question into sub-queries
        #so multi-topic qestions all get relevant chunks
        base_retriever = vector_db.as_retriever(search_kwargs={'k':8})
        retriever = MultiQueryRetriever.from_llm(
            retriever = base_retriever,
            llm = llm
        )

        docs = retriever.invoke(question)


        # deduplicate: keep only 3 chunks per source file to prevent
        # one document from dominating all retrieval slots
        seen_content = set()
        source_count = defaultdict(int)
        unique_docs = []

        for doc in docs:
            source = doc.metadata.get('source')
            content = doc.page_content

            if content in seen_content:
                continue
            if source_count[source] >= 3:
                continue

            seen_content.add(content)
            source_count[source] += 1
            unique_docs.append(doc)
       
        context = '\n\n'.join(
            f"[Page {doc.metadata.get('page')}]\n{doc.page_content}"
            for doc in unique_docs
        )

        prompt = f"""You are a helpful RAG assistant. Answer only from the document context below.

Previous conversation:
{history}

Document context:
{context}

Question: {question}

Rules:
1. Use document context first.
2. Use conversation history to resolve references (it, they, that event, etc.).
3. If the answer is not in context, say: "I couldn't find that information."
4. Do not mention page numbers inside the answer text itself.
5. Only list pages in PAGES_USED that you actually relied on.
6. End your response with exactly:
PAGES_USED:comma,separated,page,numbers

Example:
The answer goes here.
PAGES_USED:3,7"""

        answer = llm.invoke(prompt)
        raw_answer = answer.content

        match = re.search(r'PAGES_USED\s*:\s*(.*)', raw_answer, re.IGNORECASE)
        if match:
            answer_text = raw_answer[:match.start()].strip()
            used_pages = [int(p.strip()) for p in match.group(1).split(',') if p.strip().isdigit()]
        else:
            answer_text = raw_answer.strip()
            used_pages = []

        ChatMessage.objects.create(session=session, role='user', content=question)
        ChatMessage.objects.create(session=session, role='assistant', content=raw_answer)

        source_map = defaultdict(set)
        for doc in unique_docs:
            if doc.metadata.get('page') in used_pages:
                source_map[doc.metadata.get('source')].add(doc.metadata.get('page'))

        sources = [{'file': f, 'pages': sorted(p)} for f, p in source_map.items()]

        return Response({'answer': answer_text, 'sources': sources})
