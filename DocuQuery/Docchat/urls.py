from django.urls import path
from .views import (
    UploadDocumentView,
    ProcessDocumentView,
    ChatStreamView,
    CreateSessionView,
    DocumentStatusView,
    ChromaDebugView,
)
from .auth_views import RegisterView, LoginView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('auth/register/', RegisterView.as_view(),         name='register'),
    path('auth/login/',    LoginView.as_view(),            name='login'),
    path('auth/refresh/',  TokenRefreshView.as_view(),     name='token-refresh'),
    path('upload/',        UploadDocumentView.as_view(),   name='upload'),
    path('process/<int:document_id>/',          ProcessDocumentView.as_view(),  name='process'),
    path('documents/<int:document_id>/status/', DocumentStatusView.as_view(),   name='document-status'),
    path('session/',                            CreateSessionView.as_view(),     name='session-create'),
    # path('chat/<uuid:session_id>/',           ChatView.as_view(),              name='chat'),
    path('chat/<uuid:session_id>/stream/',      ChatStreamView.as_view(),        name='chat-stream'),
    path('chroma-debug/',                       ChromaDebugView.as_view(),       name='chroma-debug'),
]
