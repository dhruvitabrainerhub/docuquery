import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from Docchat.models import ChatSession, ChatMessage
from Docchat.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# Dedicated thread pool — LLM streaming runs here, event loop never blocks
_executor = ThreadPoolExecutor(max_workers=4)


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            logger.warning("[WS] Connection rejected: Unauthenticated user.")
            await self.close(code=4001)
            return

        kwargs          = self.scope["url_route"]["kwargs"]
        self.user_id    = str(self.user.id)
        self.session_id = kwargs["session_id"]

        # Per-user room & per-session room
        self.user_group    = f"user_{self.user_id}"
        self.session_group = f"session_{self.session_id}"

        await self.channel_layer.group_add(self.user_group,    self.channel_name)
        await self.channel_layer.group_add(self.session_group, self.channel_name)
        await self.accept()

        logger.info(f"[WS] user={self.user.username} (id={self.user_id}) session={self.session_id} connected")
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": "Connected successfully.",
            "user_id": self.user_id,
            "username": self.user.username,
            "session_id": self.session_id,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group') and hasattr(self, 'session_group'):
            await self.channel_layer.group_discard(self.user_group,    self.channel_name)
            await self.channel_layer.group_discard(self.session_group, self.channel_name)
        logger.info(f"[WS] session={getattr(self, 'session_id', None)} disconnected")

    async def receive(self, text_data):
        data     = json.loads(text_data)
        question = data.get("question", "").strip()

        if not question:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "'question' is required."
            }))
            return

        # Session must belong to this authenticated user
        session = await database_sync_to_async(
            ChatSession.objects.filter(id=self.session_id, user=self.user).first
        )()

        if not session:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Session not found or does not belong to this user."
            }))
            return


        logger.debug(f"[WS] user={self.user_id} question={question[:50]}")
        history    = await self._get_history(session)
        raw_answer = await self._stream_to_client(question, history, self.user_id)
        await self._save_messages(session, question, raw_answer)

    async def _stream_to_client(self, question: str, history: str, user_id: str) -> str:
        loop   = asyncio.get_event_loop()
        queue  = asyncio.Queue()
        raw_answer = ""

        def _run_generator():
            # user_id pass karo — RAGService sirf is user ke docs search karega
            for event in RAGService.stream_answer(question, history, user_id=user_id):
                loop.call_soon_threadsafe(queue.put_nowait, event)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(_executor, _run_generator)

        while True:
            event = await queue.get()
            if event is None:
                break
            await self.send(text_data=json.dumps(event))
            if event["type"] == "complete":
                raw_answer = event["raw"]

        return raw_answer

    async def document_ready(self, event):
        """Celery task embedding complete hone par yeh call karta hai."""
        await self.send(text_data=json.dumps({
            "type": "document_ready",
            "document_id": event["document_id"],
            "message": event["message"],
        }))

    @database_sync_to_async
    def _get_history(self, session):
        return ''.join(
            f"{msg.role}: {msg.content}\n"
            for msg in session.messages.order_by('created_at')
        )

    @database_sync_to_async
    def _save_messages(self, session, question, raw_answer):
        ChatMessage.objects.create(session=session, role='user',      content=question)
        ChatMessage.objects.create(session=session, role='assistant', content=raw_answer)
