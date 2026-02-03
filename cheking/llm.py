import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_LLM")

if not GROQ_API_KEY or not GROQ_MODEL:
    raise ValueError("Please set GROQ_API_KEY and GROQ_LLM in your .env")

# Initialize the Groq LLM
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model=GROQ_MODEL,
    temperature=0.3
)

print(f"✅ Using Groq LLM: {GROQ_MODEL}")
