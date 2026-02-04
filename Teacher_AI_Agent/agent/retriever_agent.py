"""
RetrieverAgent - Student-adaptive Retriever Agent
Handles:
- Embedding model loading (cached)
- Vector similarity search
- LLM response generation
- Optional dynamic student profile
"""

import os
import logging
from typing import Optional, Dict
from langchain_huggingface import HuggingFaceEmbeddings
import sys

from search.structured_response import StudentProfile

# -----------------------------
# Path setup
# -----------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# -----------------------------
# Imports
# -----------------------------
from Teacher_AI_Agent.model_cache import model_cache
from search.SimilaritySearch import retrieve_chunk_for_query_send_to_llm

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RetrievalOrchestratorAgent:
    """
    Passive Retriever Agent with optional student-adaptive prompts.
    """

    def __init__(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_model: Optional[HuggingFaceEmbeddings] = None
    ):
        self.embedding_model_name = embedding_model_name
        self._embedding_model = embedding_model
        self._loaded = False

    # -----------------------------
    # Embedding model (lazy + cached)
    # -----------------------------
    @property
    def embedding_model(self) -> HuggingFaceEmbeddings:
        if self._embedding_model is None:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self._embedding_model = model_cache.get_embedding_model(self.embedding_model_name)
            logger.info("✅ Embedding model loaded successfully")
        return self._embedding_model

    # -----------------------------
    # Preload (NO LLM CALL)
    # -----------------------------
    def load(self):
        if self._loaded:
            logger.info("♻️ RetrieverAgent already loaded")
            return
        logger.info("⚡ Preloading RetrieverAgent...")
        _ = self.embedding_model
        self._loaded = True
        logger.info("✅ RetrieverAgent preload complete")

    # -----------------------------
    # Retrieval + LLM with optional student profile
    # -----------------------------
    def orchestrate_retrieval_and_response(
        self,
        query: str,
        db_name: str,
        collection_name: str,
        student_profile: Optional[dict] = None  # user can pass dict or None
    ) -> str:

        # Validate profile
        if isinstance(student_profile, dict):
            profile = StudentProfile(**student_profile)  # convert dict to Pydantic
        elif isinstance(student_profile, StudentProfile):
            profile = student_profile  # already validated
        else:
            profile = StudentProfile()  # default

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if not self._loaded:
            self.load()

        logger.info("=" * 80)
        logger.info(f"🔍 Processing query in {db_name}.{collection_name}")
        logger.info("=" * 80)
        logger.info(f"Full Query ({len(query)} chars):")
        logger.info(query[:500] + ("..." if len(query) > 500 else ""))
        logger.info("=" * 80)

        try:
            result = retrieve_chunk_for_query_send_to_llm(
                query=query,
                db_name=db_name,
                collection_name=collection_name,
                embedding_model=self.embedding_model,
                student_profile=profile.dict()  # send as dict to similarity_search/groq
            )
            return result  # {"response": str, "quality_scores": dict}
        except Exception as e:
            logger.error(f"❌ Error during retrieval: {e}")
            raise


    # -----------------------------
    # Info helper
    # -----------------------------
    def get_embedding_model_info(self) -> Dict[str, str]:
        model = self.embedding_model
        return {
            "model_name": getattr(model, "model_name", self.embedding_model_name),
            "model_type": type(model).__name__
        }
