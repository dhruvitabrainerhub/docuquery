import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DocuQuery.settings')

# Django apps PEHLE load honi chahiye — tabhi routing/consumers import karo
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from Docchat.middleware import TokenAuthMiddleware
import Docchat.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": TokenAuthMiddleware(
        URLRouter(
            Docchat.routing.websocket_urlpatterns
        )
    ),
})

