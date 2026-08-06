import os
from celery import shared_task
from .models import Documents
from .services.parser import extract_text
from .services.chunker import create
from .services.embeddings import get_vector_db
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_document_task(self, document_id):
    try:
        document = Documents.objects.get(id=document_id)
    except Documents.DoesNotExist:
        logger.error(f"Document {document_id} not found.")
        return

    Documents.objects.filter(pk=document_id).update(
        status=Documents.Status.PROCESSING, 
        processed=False
        )
    logger.info(f"[Task] Document {document_id} → PROCESSING")

    try:
        if not document.file or not document.file.name:
            raise ValueError(f"Document {document_id} has no file associated.")

        vector_db = get_vector_db()

        old = vector_db.get(where={'document_id': document.id})
        if old and old.get('ids'):
            vector_db.delete(ids=old['ids'])

        pages = extract_text(document.file.path)

        all_chunks, all_metadatas = [], []
        for page in pages:
            chunks = create(page["text"])
            for idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    'document_id': document.id,
                    'user_id':     document.user_id,
                    'source':      document.file.name,
                    'page':        page['page'],
                    'chunk_id':    idx,
                })

        if not all_chunks:
            raise ValueError("No text chunks extracted from document.")

        vector_db.add_texts(texts=all_chunks, metadatas=all_metadatas)
        logger.info(f"[Task] Document {document_id} → {len(all_chunks)} chunks stored")

        Documents.objects.filter(pk=document_id).update(
            processed=True,
            status=Documents.Status.DONE
        )
        logger.info(f"[Task] Document {document_id} → DONE ✅")

    except Exception as exc:
        logger.exception(f"[Task] Document {document_id} failed: {exc}")
        if self.request.retries >= self.max_retries:
            Documents.objects.filter(pk=document_id).update(status=Documents.Status.FAILED,processed=False)
            logger.error(f"[Task] Document {document_id} → FAILED ❌")
            return
        raise self.retry(exc=exc, countdown=60)
        return

    # Notify websocket clients — outside try/except so embedding failure does not affect notification
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        from .models import ChatSession
        channel_layer = get_channel_layer()
        notify_payload = {
            "type": "document_ready",
            "document_id": document_id,
            "message": "Document processing completed.",
        }
        # Broadcast to document group
        async_to_sync(channel_layer.group_send)(f"document_{document_id}", notify_payload)

        # Notify all active session groups
        session_ids = ChatSession.objects.values_list('id', flat=True)
        for sid in session_ids:
            async_to_sync(channel_layer.group_send)(f"session_{sid}", notify_payload)
    except Exception as e:
        logger.warning(f"[Task] Document {document_id} WebSocket notify failed (non-critical): {e}")


@shared_task
def generate_chat_title(session_id, first_question):
    """Generate session title from first 6 words of question — no LLM, no API cost."""
    from .models import ChatSession
    try:
        words = first_question.strip().split()
        title = ' '.join(words[:6])
        if len(words) > 6:
            title += '...'
        if not title:
            return

        ChatSession.objects.filter(id=session_id).update(title=title)
        logger.info(f"[Title] Session {session_id} → '{title}'")

        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            async_to_sync(get_channel_layer().group_send)(
                f"session_{session_id}",
                {"type": "title_update", "title": title},
            )
        except Exception as e:
            logger.warning(f"[Title] WebSocket notify failed: {e}")

    except Exception as e:
        logger.warning(f"[Title] Generation failed for session {session_id}: {e}")


@shared_task
def cleanup_missing_files():
    """
    Runs every 10 minutes.
    If a document's file has been deleted from disk:
    - Remove its vectors from ChromaDB
    - Delete the document record from DB
    """
    import os
    from .services.embeddings import get_vector_db

    docs = Documents.objects.all()
    deleted_count = 0

    for doc in docs:
        try:
            file_missing = not doc.file or not doc.file.name or not os.path.isfile(doc.file.path)
        except Exception:
            file_missing = True

        if file_missing:
            logger.warning(f"[Cleanup] Document {doc.id} ('{doc.title}') file missing → cleaning up")
            try:
                vector_db = get_vector_db()
                old = vector_db.get(where={'document_id': doc.id})
                if old and old.get('ids'):
                    vector_db.delete(ids=old['ids'])
                    logger.info(f"[Cleanup] Document {doc.id} → {len(old['ids'])} vectors deleted")
            except Exception as e:
                logger.warning(f"[Cleanup] Document {doc.id} vector cleanup failed: {e}")

            doc.delete()  # post_delete signal will attempt file deletion (already missing, no-op)
            deleted_count += 1
            logger.info(f"[Cleanup] Document {doc.id} removed from DB")

    logger.info(f"[Cleanup] Done — {deleted_count} orphaned documents removed")


@shared_task
def reindex_all_documents():
    docs = Documents.objects.filter(processed=True)
    count = docs.count()
    logger.info(f"[Beat] Reindexing {count} documents one by one")
    for idx, doc in enumerate(docs):
        # stagger tasks by 30s each to avoid concurrent ChromaDB writes
        process_document_task.apply_async(
            args=[doc.id],
            countdown=idx * 30
        )
    logger.info(f"[Beat] Queued {count} documents with 30s stagger")