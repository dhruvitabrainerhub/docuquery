import os
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Documents

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Documents)
def trigger_processing(sender, instance, created, **kwargs):
    if created:
        from .tasks import process_document_task
        task = process_document_task.delay(instance.id)
        Documents.objects.filter(pk=instance.pk).update(task_id=task.id)
        logger.info(f"[Signal] Document {instance.id} queued → task_id: {task.id}")


@receiver(post_delete, sender=Documents)
def cleanup_on_delete(sender, instance, **kwargs):
    """On document deletion: remove vectors from ChromaDB and delete file from disk."""
    # 1. Delete vectors from ChromaDB
    try:
        from .services.embeddings import get_vector_db
        vector_db = get_vector_db()
        old = vector_db.get(where={'document_id': instance.id})
        if old and old.get('ids'):
            vector_db.delete(ids=old['ids'])
            logger.info(f"[Signal] Document {instance.id} → {len(old['ids'])} vectors deleted from ChromaDB")
    except Exception as e:
        logger.warning(f"[Signal] Document {instance.id} vector cleanup failed: {e}")

    # 2. Delete file from disk
    try:
        if instance.file and instance.file.name:
            file_path = instance.file.path
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.info(f"[Signal] Document {instance.id} → file deleted: {file_path}")
    except Exception as e:
        logger.warning(f"[Signal] Document {instance.id} file deletion failed: {e}")