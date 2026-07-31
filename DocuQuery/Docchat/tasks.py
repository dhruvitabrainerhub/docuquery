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

    # notify websocket clients — outside try/except so embedding failure != notify failure
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
        # document_{id} group — legacy broadcast (koi bhi listener)
        async_to_sync(channel_layer.group_send)(f"document_{document_id}", notify_payload)

        # session groups — us document se linked sessions ko notify karo
        session_ids = ChatSession.objects.values_list('id', flat=True)
        for sid in session_ids:
            async_to_sync(channel_layer.group_send)(f"session_{sid}", notify_payload)
    except Exception as e:
        logger.warning(f"[Task] Document {document_id} WebSocket notify failed (non-critical): {e}")


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