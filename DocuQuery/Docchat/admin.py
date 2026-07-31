from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Documents, ChatSession, ChatMessage


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
    list_display  = ['id', 'title', 'get_username', 'status', 'processed', 'upload_at']
    list_filter   = ['status', 'processed']
    search_fields = ['title', 'user__username']
    ordering      = ['-upload_at']

    def get_username(self, obj):
        return obj.user.username if obj.user else '—'
    get_username.short_description = 'Uploaded By'


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