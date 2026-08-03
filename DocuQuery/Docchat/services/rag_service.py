import re
import os
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

        # Retrieve candidate chunks (k=50 for rich context across multiple files)
        retriever = MultiQueryRetriever.from_llm(
            retriever=vector_db.as_retriever(search_kwargs={'k': 20}),
            llm=llm
        )
        docs = retriever.invoke(question)

        # Robust user_id post-filtering matching both int and str representations
        if user_id and str(user_id) != 'default':
            user_id_str = str(user_id)
            user_id_int = int(user_id) if user_id_str.isdigit() else None

            filtered_docs = []
            for doc in docs:
                doc_uid = doc.metadata.get('user_id')
                if doc_uid is None:
                    filtered_docs.append(doc)
                elif str(doc_uid) == user_id_str or (user_id_int is not None and doc_uid == user_id_int):
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

        logger.info(f"[RAG] Retrieved {len(unique_docs)} docs for question: '{question[:40]}...' (user_id={user_id})")
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
1. Use ONLY the document context above to answer. Multiple documents may be present.
2. Use conversation history to resolve references (it, they, that event, etc.).
3. If the user asks about a different document or topic present in the context, answer using that document's chunks.
4. If the answer is NOT in the context, say exactly: "I couldn't find that information."
5. Do NOT mention document IDs or page numbers inside the answer text itself.
6. At the end, list ONLY the Doc IDs and pages you actually used to write the answer.
7. End your response with EXACTLY this line (no extra text after it):
SOURCES_USED:D<id>:<page>,D<id>:<page>

Example of correct final line:
SOURCES_USED:D1:2,D3:10

If no answer found, end with:
SOURCES_USED:"""

    @staticmethod
    def _parse(raw_answer: str, unique_docs: list, doc_id_map: dict):
        """
        doc_id_map: {"D1": (source, page), "D2": (source, page), ...}
        Parses SOURCES_USED:D1:2,D3:10 and returns only those exact (source, page) pairs.
        """
        match = re.search(r'SOURCES_USED\s*:\s*(.*)', raw_answer, re.IGNORECASE)
        answer_text = raw_answer[:match.start()].strip() if match else raw_answer.strip()

        source_map = defaultdict(set)
        if match:
            raw_refs = match.group(1).strip()
            # Parse each token like D1:2 or D12:10
            for token in re.findall(r'D(\d+):(\d+)', raw_refs, re.IGNORECASE):
                doc_idx, page_num = int(token[0]), int(token[1])
                key = f"D{doc_idx}"
                if key in doc_id_map:
                    src, _ = doc_id_map[key]
                    filename = os.path.basename(src)   # only file name, no path
                    source_map[filename].add(page_num)

        sources = [{'file': f, 'pages': sorted(p)} for f, p in source_map.items()]
        return answer_text, sources

    @staticmethod
    def _build_context_and_map(unique_docs: list):
        """Assign each chunk a unique Doc ID (D1, D2, ...) and build a lookup map."""
        lines = []
        doc_id_map = {}  # {"D1": (source, page), ...}
        for i, doc in enumerate(unique_docs, start=1):
            key = f"D{i}"
            src = doc.metadata.get('source', 'Unknown')
            pg  = doc.metadata.get('page', '?')
            doc_id_map[key] = (src, pg)
            lines.append(f"[{key} | Document: {src} | Page {pg}]\n{doc.page_content}")
        context = '\n\n'.join(lines)
        return context, doc_id_map

    @staticmethod
    def ask(question: str, history: str = "", user_id: str = None) -> dict:
        """Used by REST API (ChatView)."""
        unique_docs = RAGService._retrieve(question, user_id=user_id)
        context, doc_id_map = RAGService._build_context_and_map(unique_docs)
        prompt = RAGService._build_prompt(history, context, question)
        raw_answer = llm.invoke(prompt).content
        answer_text, sources = RAGService._parse(raw_answer, unique_docs, doc_id_map)
        return {'answer': answer_text, 'sources': sources, 'raw': raw_answer}

    @staticmethod
    def stream_answer(question: str, history: str = "", user_id: str = None):
        """Used by WebSocket (ChatConsumer)."""
        unique_docs = RAGService._retrieve(question, user_id=user_id)
        context, doc_id_map = RAGService._build_context_and_map(unique_docs)
        prompt = RAGService._build_prompt(history, context, question)

        full_answer = ""
        for chunk in llm.stream(prompt):
            if chunk.content:
                full_answer += chunk.content
                yield {"type": "token", "content": chunk.content}

        raw_answer = full_answer
        answer_text, sources = RAGService._parse(raw_answer, unique_docs, doc_id_map)
        yield {"type": "complete", "sources": sources, "raw": raw_answer}

