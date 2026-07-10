import logging
from django.db.models.signals import post_save
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
        # instance.task_id = task.id
        # instance.save(update_fields=['task_id'])