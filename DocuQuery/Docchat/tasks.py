from celery import shared_task
from .models import Documents
from .services.parser import extract_text
from .services.chunker import create
from .services.embeddings import get_vector_db
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True,max_retries=3)
def process_document_task(self, document_id):
    vector_db = get_vector_db()
    try:
        document = Documents.objects.get(id=document_id)
    except Documents.DoesNotExist:
        logger.error(f"Document {document_id} not found.")
        return
    
    Documents.objects.filter(pk=document_id).update(status=Documents.Status.PROCESSING)
    logger.info(f"[Tasks] Document {document_id} → PROCESSING")
    # document.status = Documents.Status.PROCESSING
    # document.save(update_fields=["status"])

    try:
        if not document.file or not document.file.name:
            raise ValueError(f"Document {document_id} has no file associated.")
        old = vector_db.get(where={'document_id':document.id})
        if old and old.get('ids'):
            vector_db.delete(ids=old['ids'])
        # logger.info(f"[{document_id}] Starting: {document.file.name}")

        pages = extract_text(document.file.path)
        # logger.info(f"[{document_id}] Extracted {len(pages)} pages")

        all_chunks, all_metadatas = [], []

        for page in pages:
            chunks = create(page["text"])
            for idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    'document_id': document.id,
                    'source': document.file.name,
                    'page': page['page'],
                    'chunk_id': idx,
                })
        if not all_chunks:
            raise ValueError("No text chunks extracted from document.")
        # logger.info(f"[{document_id}] Total chunks created: {len(all_chunks)}")

        vector_db.add_texts(texts=all_chunks, metadatas=all_metadatas)
        logger.info(f"[Task] Document {document_id} → {len(all_chunks)} chunks stored")

        #use update() to avoid re-firing post save signal
        Documents.objects.filter(pk=document_id).update(
            processed = True,
            status = Documents.Status.DONE
        )
 
        # document.save(update_fields = ['processed','status'])
        logger.info(f"[Task] Document {document_id} → DONE ✅")

    except Exception as exc:
        logger.exception(f"[Task] Document {document_id} failed: {exc}")
        if self.request.retries >= self.max_retries:
            Documents.objects.filter(pk=document_id).update(status=Documents.Status.FAILED)
            logger.error(f"[Task] Document {document_id} → FAILED ❌ ")
            # document.status = Documents.Status.FAILED
            # document.save(update_fields=['status'])
        raise self.retry(exc=exc, countdown=60)

@shared_task
def reindex_all_documents():
    docs = Documents.objects.filter(processed=True)
    logger.info(f"[Beat] Reindexing {docs.count()} documents")
    for doc in docs:
        process_document_task.delay(doc.id)
    # for doc in Documents.objects.filter(processed=True):
    #     process_document_task.delay(doc.id)