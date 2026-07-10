from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from django.conf import settings

_embedding_model = None
_vector_db = None

def get_vector_db():
    global _embedding_model, _vector_db

    if _vector_db is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name = 'sentence-transformers/all-MiniLM-L6-v2'
    )


        _vector_db = Chroma(
            collection_name = "documents",
            persist_directory = settings.CHROMA_DB_PATH, 
            embedding_function = _embedding_model
        )
    return _vector_db       
    