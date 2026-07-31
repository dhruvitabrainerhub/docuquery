import uuid
from django.db import models
from django.contrib.auth.models import User


class Documents(models.Model):

    class Status(models.TextChoices):
        PENDING    = 'PENDING',    'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        DONE       = 'DONE',       'Done'
        FAILED     = 'FAILED',     'Failed'

    title     = models.CharField(max_length=255)
    file      = models.FileField(upload_to='documents/')
    upload_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    status    = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    task_id   = models.CharField(max_length=255, null=True, blank=True)
    user      = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')

    def __str__(self):
        return self.title

    @property
    def user_id(self):
        return str(self.user.id) if self.user else 'default'


class ChatSession(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title      = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_sessions')

    def __str__(self):
        return f"Session {self.id}"

    @property
    def user_id(self):
        return str(self.user.id) if self.user else 'default'



class ChatMessage(models.Model):
    session    = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role       = models.CharField(max_length=20)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} — {self.session_id}"