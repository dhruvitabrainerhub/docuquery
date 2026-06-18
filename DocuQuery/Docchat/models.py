from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
import uuid

# Create your models here.
class Documents(models.Model):
    title = models.CharField(max_length=255)

    file = models.FileField(upload_to='documents/')

    upload_at = models.DateTimeField(auto_now_add = True)                                       

    processed = models.BooleanField(default = False)

    def __str__(self):
        return self.title

#Chat session model
# class ChatSession(models.Model):
#     title = models.CharField(max_length=255)
#     created_at = models.DateTimeField(auto_now_add = True)

#     def __str__(self):
#         return f"Session{self.id}"

class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.id}"

#Chat Message Model
class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete = models.CASCADE,
        related_name = 'messages'
    )

    role = models.CharField(max_length = 20)    

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add = True)


@receiver(post_delete, sender=Documents)
def delete_document_vectors(sender, instance, **kwargs):
    from .services.embeddings import vector_db

    results = vector_db.get(where={'document_id': instance.id})

    if results and results.get('ids'):
        vector_db.delete(ids=results['ids'])

