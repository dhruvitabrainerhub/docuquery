from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

embedding_model = HuggingFaceEmbeddings(
    model_name = 'sentence-transformers/all-MiniLM-L6-v2'
)

vector_db = Chroma(
    collection_name = "documents",
    persist_directory = "./chroma_db",
    embedding_function = embedding_model
)