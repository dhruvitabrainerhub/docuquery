from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY')
if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY is not set in environment variables.")
    
llm = ChatOpenAI(
    model = 'openai/gpt-4o-mini',
    base_url = 'https://openrouter.ai/api/v1',
    api_key = api_key
)

