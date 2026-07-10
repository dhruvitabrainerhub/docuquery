from django.urls import path
from .views import(
    UploadDocumentView,
    ProcessDocumentView,
    ChatView,
    CreateSessionView,
    TaskStatusView
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
        'chat/<uuid:session_id>/',
        ChatView.as_view()
    ),
    path(
        'documents/<int:document_id>/status/',
        TaskStatusView.as_view(),
        name='task-status',
    ),
]