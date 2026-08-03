from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import Documents, ChatSession, ChatMessage
from .tasks import process_document_task
import logging

logger = logging.getLogger(__name__)


# ─── Customize default User Admin ──────────────────────────────────────────
class CustomUserAdmin(UserAdmin):
    list_display  = ['id', 'username', 'email', 'is_staff', 'is_active', 'date_joined']
    list_filter   = ['is_staff', 'is_active']
    search_fields = ['username', 'email']
    ordering      = ['-date_joined']


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ─── Documents ──────────────────────────────────────────────────────────────
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ['id', 'title', 'get_username', 'get_status_colored', 'processed', 'upload_at']
    list_filter   = ['status', 'processed']
    search_fields = ['title', 'user__username']
    ordering      = ['-upload_at']
    actions       = ['re_embed_documents']

    def get_username(self, obj):
        return obj.user.username if obj.user else '—'
    get_username.short_description = 'Uploaded By'

    def get_status_colored(self, obj):
        """Display status with color coding"""
        colors = {
            Documents.Status.PENDING: '#FFA500',    # Orange
            Documents.Status.PROCESSING: '#3498DB', # Blue
            Documents.Status.DONE: '#27AE60',       # Green
            Documents.Status.FAILED: '#E74C3C',     # Red
        }
        color = colors.get(obj.status, '#95A5A6')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    get_status_colored.short_description = 'Status'

    def re_embed_documents(self, request, queryset):
        """Admin action to re-embed selected documents"""
        count = 0
        for document in queryset:
            # Set status to PROCESSING before queuing the task
            document.status = Documents.Status.PROCESSING
            document.processed = False
            document.task_id = None
            document.save(update_fields=['status', 'processed', 'task_id'])
            
            # Queue the re-embedding task
            task = process_document_task.delay(document.id)
            
            # Save the task ID for reference
            document.task_id = task.id
            document.save(update_fields=['task_id'])
            
            logger.info(f"[Admin] Document {document.id} ({document.title}) re-embedding started → PROCESSING")
            count += 1
        
        self.message_user(request, f"{count} document(s) queued for re-embedding. Status updated to 'Processing'.")
    
    re_embed_documents.short_description = "Re-embed selected documents"


# ─── Chat Sessions ──────────────────────────────────────────────────────────
class ChatSessionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'title', 'get_username', 'created_at']
    search_fields = ['title', 'user__username']
    ordering      = ['-created_at']

    def get_username(self, obj):
        return obj.user.username if obj.user else '—'
    get_username.short_description = 'User'


# ─── Chat Messages ──────────────────────────────────────────────────────────
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ['id', 'get_session_user', 'session', 'role', 'created_at']
    list_filter   = ['role']
    search_fields = ['session__user__username', 'content']
    ordering      = ['-created_at']

    def get_session_user(self, obj):
        return obj.session.user.username if obj.session and obj.session.user else '—'
    get_session_user.short_description = 'User'


admin.site.register(Documents,   DocumentAdmin)
admin.site.register(ChatSession, ChatSessionAdmin)
admin.site.register(ChatMessage, ChatMessageAdmin)