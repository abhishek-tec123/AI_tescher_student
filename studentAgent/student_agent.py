import os
import sys
import logging
from typing import Optional, Dict

# Ensure parent path is available
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from Teacher_AI_Agent.agent.retriever_agent import RetrievalOrchestratorAgent
from studentAgent.run_single_queryFun import run_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StudentAgent:
    """
    High-level agent wrapper for running queries
    with optional student personalization.
    """

    def __init__(self):
        self.retriever_agent = RetrievalOrchestratorAgent()
        self._loaded = False

    def load(self):
        """
        Load retriever resources once (embeddings, vector DB, etc.)
        """
        if not self._loaded:
            logger.info("Loading RetrieverAgent...")
            self.retriever_agent.load()
            self._loaded = True

    def ask(
        self,
        query: str,
        class_name: str,
        subject: str,
        student_profile: Optional[Dict] = None,
    ):
        """
        Run a query with optional student profile.

        Args:
            query (str): Student question
            class_name (str): Class/grade (e.g., '10th')
            subject (str): Subject (e.g., 'Science')
            student_profile (dict, optional): Personalization config
        """
        if not self._loaded:
            self.load()

        logger.info("Running query for class=%s subject=%s", class_name, subject)

        return run_query(
            retriever_agent=self.retriever_agent,
            query=query,
            db_name=class_name,
            collection_name=subject,
            student_profile=student_profile,
        )
