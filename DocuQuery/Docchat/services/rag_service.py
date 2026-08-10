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

        search_kwargs = {'k': 20}
        if user_id and str(user_id) != 'default':
            search_kwargs['filter'] = {'user_id': int(user_id)}  # ChromaDB where clause
        # Retrieve candidate chunks (k=20 for rich context across multiple files)
        retriever = MultiQueryRetriever.from_llm(
            retriever=vector_db.as_retriever(search_kwargs=search_kwargs),
            llm=llm
        )
        docs = retriever.invoke(question)
        
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
6. At the end, list ONLY the sources you actually used to write the answer.
7. End your response with EXACTLY this line (no extra text after it):
SOURCES_USED:filename.pdf:page,filename.pdf:page

Example of correct final line:
SOURCES_USED:report.pdf:2,annual.pdf:10

If no answer found, end with:
SOURCES_USED:"""

    @staticmethod
    def _parse(raw_answer: str):
        match = re.search(r'SOURCES_USED\s*:\s*(.*)', raw_answer, re.IGNORECASE)
        answer_text = raw_answer[:match.start()].strip() if match else raw_answer.strip()

        source_map = defaultdict(set)
        if match:
            for token in re.findall(r'([\w\-. ]+\.pdf):(\d+)', match.group(1), re.IGNORECASE):
                filename, page = token[0].strip(), int(token[1])
                source_map[filename].add(page)

        sources = [{'file': f, 'pages': sorted(p)} for f, p in source_map.items()]
        return answer_text, sources

    @staticmethod
    def _build_context(unique_docs: list) -> str:
        lines = []
        for doc in unique_docs:
            src = os.path.basename(doc.metadata.get('source', 'Unknown'))
            pg  = doc.metadata.get('page', '?')
            lines.append(f"[Document: {src} | Page {pg}]\n{doc.page_content}")
        return '\n\n'.join(lines)


    @staticmethod
    def stream_answer(question: str, history: str = "", user_id: str = None):
        """Used by WebSocket (ChatConsumer)."""
        unique_docs = RAGService._retrieve(question, user_id=user_id)
        yield {"type": "retrieving_done"}

        context = RAGService._build_context(unique_docs)
        prompt  = RAGService._build_prompt(history, context, question)

        full_answer = ""
        for chunk in llm.stream(prompt):
            if chunk.content:
                full_answer += chunk.content

        answer_text, sources = RAGService._parse(full_answer)

        for word in answer_text.split(' '):
            yield {"type": "token", "content": word + ' '}

        yield {"type": "complete", "sources": sources, "answer": answer_text}

