from django.db import models

# Create your models here.
class Documents(models.Model):
    title = models.CharField(max_length=255)

    file = models.FileField(upload_to='documents/')

    upload_at = models.DateTimeField(auto_now_add = True)                                       

    processed = models.BooleanField(default = False)

    def __str__(self):
        return self.title

#Chat session model
class ChatSession(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return f"Session{self.id}"

#Chat Message Model
class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession,
        on_delete = models.CASCADE,
        related_name = 'messages'
    )

    role = models.CharField(max_length = 20)    

    context = models.TextField()

    created_at = models.DateTimeField(auto_now_add = True)