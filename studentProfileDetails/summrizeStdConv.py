import os
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def summarize_text_with_groq(
    text: str,
    prompt: str = "Summarize the following text clearly and concisely."
) -> str:
    """
    Summarizes the given text using Groq LLM based on the provided prompt.
    """

    if not text.strip():
        raise ValueError("Input text cannot be empty")

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")

    # Final input sent to LLM
    full_input = f"""
{prompt}

TEXT:
{text}
""".strip()

    llm = ChatGroq(
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=groq_api_key
    )

    response = llm.invoke([HumanMessage(content=full_input)])

    summary = getattr(response, "content", str(response)).strip()

    logger.info("Text summarized successfully")

    return summary

import json

def extract_text_from_history(history):
    """
    Converts conversation history into a plain text string for summarization.
    Handles cases where 'response' might be a dict or string.
    """
    texts = []
    for item in history:
        resp = item.get("response", "")
        if isinstance(resp, dict):
            # Convert dict to string safely (e.g., JSON)
            resp = json.dumps(resp)
        elif not isinstance(resp, str):
            resp = str(resp)
        texts.append(resp.strip())
    return "\n".join(texts)
