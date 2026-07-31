import re
import logging
from collections import defaultdict

from langchain.retrievers.multi_query import MultiQueryRetriever

from .embeddings import get_vector_db
from .rag_pipeline import llm

logger = logging.getLogger("Docchat")

class RAGService:
    @staticmethod
    def _retrieve(question: str, user_id: str = None):
        vector_db = get_vector_db()

        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)

        retriever = MultiQueryRetriever.from_llm(
            retriever=vector_db.as_retriever(search_kwargs={'k': 20}),
            llm=llm
        )
        docs = retriever.invoke(question)

        if user_id and user_id != 'default':
            filtered_docs = []
            for doc in docs:
                doc_uid = doc.metadata.get('user_id')
                if isinstance(doc_uid, str) and doc_uid.isdigit():
                    doc_uid = int(doc_uid)
                if doc_uid == user_id:
                    filtered_docs.append(doc)
            docs = filtered_docs

        seen_content, source_count, unique_docs = set(), defaultdict(int), []
        for doc in docs:
            source = doc.metadata.get('source')
            content = doc.page_content
            if content in seen_content or source_count[source] >= 5:
                continue
            seen_content.add(content)
            source_count[source] += 1
            unique_docs.append(doc)

        return unique_docs
        
    @staticmethod
    def _build_prompt(history: str, context: str, question: str) -> str:
        return f"""You are a helpful RAG assistant. You ONLY answer from the document context provided below.

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

Response format:
Write your answer here.
PAGES_USED:comma,separated,page,numbers

If no answer found:
I couldn't find that information.
PAGES_USED:"""

    @staticmethod
    def _parse(raw_answer: str, unique_docs: list):
        match = re.search(r'PAGES_USED\s*:\s*(.*)', raw_answer, re.IGNORECASE)
        answer_text = raw_answer[:match.start()].strip() if match else raw_answer.strip()
        used_pages = [int(p.strip()) for p in match.group(1).split(',') if p.strip().isdigit()] if match else []

        source_map = defaultdict(set)
        for doc in unique_docs:
            if doc.metadata.get('page') in used_pages:
                source_map[doc.metadata.get('source')].add(doc.metadata.get('page'))

        sources = [{'file': f, 'pages': sorted(p)} for f, p in source_map.items()]
        return answer_text, sources

    @staticmethod
    def ask(question: str, history: str = "", user_id: str = None) -> dict:
        """Used by REST API (ChatView)."""
        unique_docs = RAGService._retrieve(question, user_id=user_id)
        context = '\n\n'.join(
            f"[Page {doc.metadata.get('page')}]\n{doc.page_content}"
            for doc in unique_docs
        )
        prompt = RAGService._build_prompt(history, context, question)
        raw_answer = llm.invoke(prompt).content
        answer_text, sources = RAGService._parse(raw_answer, unique_docs)
        return {'answer': answer_text, 'sources': sources, 'raw': raw_answer}

    @staticmethod
    def stream_answer(question: str, history: str = "", user_id: str = None):
        """Used by WebSocket (ChatConsumer)."""
        unique_docs = RAGService._retrieve(question, user_id=user_id)
        context = '\n\n'.join(
            f"[Page {doc.metadata.get('page')}]\n{doc.page_content}"
            for doc in unique_docs
        )
        prompt = RAGService._build_prompt(history, context, question)

        full_answer = ""
        for chunk in llm.stream(prompt):
            if chunk.content:
                full_answer += chunk.content
                yield {"type": "token", "content": chunk.content}

        raw_answer = full_answer
        answer_text, sources = RAGService._parse(raw_answer, unique_docs)
        yield {"type": "complete", "sources": sources, "raw": raw_answer}
