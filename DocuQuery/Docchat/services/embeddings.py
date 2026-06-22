from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from django.conf import settings

embedding_model = HuggingFaceEmbeddings(
    model_name = 'sentence-transformers/all-MiniLM-L6-v2'
)

vector_db = Chroma(
    collection_name = "documents",
    persist_directory = settings.CHROMA_DB_PATH, 
    embedding_function = embedding_model
)