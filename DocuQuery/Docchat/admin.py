from django.contrib import admin

# Register your models here.
from .models import(
    Documents,
    ChatSession,
    ChatMessage
)

class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'title',
        'file',
        'upload_at',
        'processed'
    ]

class ChatMessageAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'session',
        'role',
        'created_at'
    ]

class ChatSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'title',
        'created_at'
    ]

admin.site.register(Documents,DocumentAdmin)
admin.site.register(ChatSession,ChatSessionAdmin)
admin.site.register(ChatMessage,ChatMessageAdmin)