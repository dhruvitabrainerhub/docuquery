import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb

_embedding_model = None
_vector_db = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name='sentence-transformers/all-MiniLM-L6-v2'
        )
    return _embedding_model


def get_vector_db():
    global _vector_db
    if _vector_db is None:
        chroma_host = os.getenv('CHROMA_HOST', 'localhost')
        chroma_port = int(os.getenv('CHROMA_PORT', 8001))

        if chroma_host != 'localhost':
            # Docker environment — use HTTP client (chromadb container)
            client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        else:
            # Local development — use persistent local storage
            client = chromadb.PersistentClient(path='./chroma_db')

        _vector_db = Chroma(
            client=client,
            collection_name='documents',
            embedding_function=get_embedding_model(),
        )
    return _vector_db
