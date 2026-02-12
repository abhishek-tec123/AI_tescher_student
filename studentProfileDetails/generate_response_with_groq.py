import os
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def generate_response_with_groq(
    query: str,
    context: str | None = None,
    system_prompt: str = "Provide a clear, short, and simple response."
) -> str:
    """
    Generates a simple response for a general query.
    Optionally uses context (e.g., text to summarize or reference).
    """

    if not query.strip():
        raise ValueError("Query cannot be empty")

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables.")

    # Build input for LLM
    if context:
        full_input = f"""
{system_prompt}

QUESTION:
{query}

CONTEXT:
{context}
""".strip()
    else:
        full_input = f"""
{system_prompt}

QUESTION:
{query}
""".strip()

    llm = ChatGroq(
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=groq_api_key
    )

    response = llm.invoke([HumanMessage(content=full_input)])

    result = getattr(response, "content", str(response)).strip()

    logger.info("Response generated successfully")

    return result
