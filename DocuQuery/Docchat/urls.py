from django.urls import path
from .views import(
    UploadDocumentView,
    ProcessDocumentView,
    ChatView,
    CreateSessionView
)

urlpatterns = [
    path(
        'upload/',
        UploadDocumentView.as_view()
    ),
    path(
        'process/<int:document_id>/',
        ProcessDocumentView.as_view()
    ),
    path(
        'session/',
        CreateSessionView.as_view()
    ),
    path(
        'chat/<int:session_id>/',
        ChatView.as_view()
    ),
]