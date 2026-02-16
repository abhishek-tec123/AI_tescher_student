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

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


import json
import logging

logger = logging.getLogger(__name__)


def update_running_summary(
    *,
    student_id: str,
    subject: str,
    new_entry: dict,
    student_manager
) -> str:
    """
    Updates running summary in MongoDB under:
    conversation_summary.{subject}
    """

    # -----------------------------
    # 1️⃣ Get Previous Summary from Mongo
    # -----------------------------
    student_doc = student_manager.students.find_one(
        {"student_id": student_id},
        {"conversation_summary": 1}
    )

    previous_summary = ""

    if student_doc:
        previous_summary = (
            student_doc.get("conversation_summary", {})
            .get(subject, "")
        )

    # -----------------------------
    # 2️⃣ Prepare New Conversation Text
    # -----------------------------
    response = new_entry.get("response", "")

    if isinstance(response, dict):
        response_text = json.dumps(response)
    elif not isinstance(response, str):
        response_text = str(response)
    else:
        response_text = response

    combined_text = f"""
PREVIOUS SUMMARY:
{previous_summary}

NEW CONVERSATION ENTRY:
User: {new_entry.get("query", "")}
Assistant: {response_text}
""".strip()

    # -----------------------------
    # 3️⃣ Generate Updated Summary
    # -----------------------------
    try:
        updated_summary = summarize_text_with_groq(
            text=combined_text,
            prompt="Update this running student learning summary concisely. Preserve important concepts and progress."
        )

        # -----------------------------
        # 4️⃣ Save to MongoDB
        # -----------------------------
        student_manager.students.update_one(
            {"student_id": student_id},
            {
                "$set": {
                    f"conversation_summary.{subject}": updated_summary
                }
            }
        )

        logger.info("Conversation summary updated in MongoDB")

        return updated_summary

    except Exception as e:
        logger.error(f"Summary update failed: {e}")
        return previous_summary
