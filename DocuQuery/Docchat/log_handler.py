import logging
import datetime
import threading
import os

try:
    from elasticsearch import Elasticsearch
    _ES_AVAILABLE = True
except ImportError:
    _ES_AVAILABLE = False


class ElasticsearchHandler(logging.Handler):
    """
    Lightweight logging handler — directly indexes logs into Elasticsearch.
    Non-blocking: uses a background thread so logging never slows down the app.
    Silently skips if ES is unavailable (e.g. local dev without ES running).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        if not _ES_AVAILABLE:
            return None
        if self._client is None:
            with self._lock:
                if self._client is None:
                    host = os.getenv('ELASTICSEARCH_HOST', 'http://elasticsearch:9200')
                    try:
                        self._client = Elasticsearch(host)
                    except Exception:
                        return None
        return self._client

    def emit(self, record):
        try:
            client = self._get_client()
            if client is None:
                return

            doc = {
                '@timestamp': datetime.datetime.utcnow().isoformat(),
                'level':      record.levelname,
                'logger':     record.name,
                'message':    self.format(record),
                'module':     record.module,
                'funcName':   record.funcName,
            }
            if record.exc_info:
                doc['exception'] = self.formatException(record.exc_info)

            index = f"docuquery-logs-{datetime.date.today().strftime('%Y.%m.%d')}"

            # Fire-and-forget in background thread — never blocks request cycle
            threading.Thread(
                target=self._index,
                args=(client, index, doc),
                daemon=True
            ).start()

        except Exception:
            self.handleError(record)

    def _index(self, client, index, doc):
        try:
            client.index(index=index, document=doc)
        except Exception:
            pass  # ES down = silently skip, never crash the app
