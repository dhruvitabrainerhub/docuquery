from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # ws/chat/<session_id>/?token=<auth_token>
    re_path(r"^ws/chat/(?P<session_id>[0-9a-f-]+)/$", ChatConsumer.as_asgi()),
]

