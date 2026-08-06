import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DocchatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Docchat'

    def ready(self):
        import Docchat.signals  # noqa: F401

        # Pre-load the PyTorch/HuggingFace embedding model in the MAIN THREAD
        # at Django startup. This prevents a Segmentation Fault (exit code 139)
        # that occurs when PyTorch C++ internals are first initialized inside a
        # worker thread (e.g. Daphne's ASGI thread pool via database_sync_to_async).
        try:
            from Docchat.services.embeddings import get_embedding_model, get_vector_db
            get_embedding_model()  # Initialize PyTorch in main thread
            get_vector_db()        # Initialize Chroma client in main thread
            logger.info("[Startup] Embedding model + vector DB loaded successfully")
        except Exception as e:
            logger.warning(f"[Startup] Could not pre-load models: {e}")