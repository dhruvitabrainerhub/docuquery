from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


@database_sync_to_async
def get_user_from_jwt(token_str):
    """
    Validate JWT access token and return the corresponding User.
    Returns AnonymousUser on any failure.
    """
    try:
        # Decode + validate the access token (signature, expiry, etc.)
        access_token = AccessToken(token_str)
        user_id      = access_token['user_id']
        return User.objects.get(id=user_id)
    except (TokenError, InvalidToken, User.DoesNotExist, KeyError):
        return AnonymousUser()


class TokenAuthMiddleware:
    """
    WebSocket middleware that reads a JWT access token from the
    query string (?token=<access_token>) and attaches the resolved
    User to scope['user'].

    Usage (client side):
        ws://host/ws/chat/<session_id>/?token=<access_token>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token_str    = query_params.get('token', [None])[0]

        if token_str:
            scope['user'] = await get_user_from_jwt(token_str)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)
