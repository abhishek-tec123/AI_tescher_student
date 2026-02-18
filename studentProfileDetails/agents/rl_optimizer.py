import os
import random
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from studentProfileDetails.generate_response_with_groq import generate_response_with_groq

logger = logging.getLogger(__name__)

class RLOptimizer:
    """
    RL-based optimizer for refining query processing and retrieval.
    """
    
    ACTION_SPACE = ["rewrite_query", "expand_context", "filter_context", "generate_response"]
    
    def __init__(self, epsilon: float = 0.2):
        self.epsilon = epsilon
        
    def select_action(self, state: Dict[str, Any]) -> str:
        """
        Policy network: Simple epsilon-greedy with heuristics.
        """
        # 1. Epsilon-greedy exploration
        if random.random() < self.epsilon:
            action = random.choice(self.ACTION_SPACE)
            logger.info(f"RL: Exploring action -> {action}")
            return action
            
        # 2. Heuristics (Exploitation)
        previous_actions = state.get("previous_actions", [])
        
        # If no context retrieved yet, prioritize rewriting or expanding
        if not state.get("context"):
            if "rewrite_query" not in previous_actions:
                return "rewrite_query"
            return "expand_context"
            
        # If we have too many chunks, maybe filter
        if len(state.get("context", [])) > 5:
            if "filter_context" not in previous_actions:
                return "filter_context"
                
        # Default to generation if we've tried things or have a good state
        return "generate_response"

    def calculate_reward(self, feedback: Optional[str], quality_scores: Dict[str, Any]) -> float:
        """
        Calculate reward based on student feedback and system quality scores.
        """
        reward = 0.0
        
        # Primary signal: Human feedback
        if feedback == "like":
            reward += 1.0
        elif feedback == "dislike":
            reward -= 1.0
            
        # Secondary signal: Quality scores (normalized to 0.0 - 1.0 range)
        # We weigh them less than direct human feedback
        if quality_scores:
            rag_relevance = quality_scores.get("rag_relevance", 0) / 100.0
            completeness = quality_scores.get("answer_completeness", 0) / 100.0
            hallucination = quality_scores.get("hallucination_risk", 0) / 100.0
            
            reward += (rag_relevance * 0.2) + (completeness * 0.2) - (hallucination * 0.1)
            
        return round(reward, 3)

    def rewrite_query(self, query: str, context_text: str = "") -> str:
        """
        Action: Rewrite the query for better retrieval.
        """
        prompt = "Rewrite the following student query to be more specific and suitable for a textbook search. Output ONLY the rewritten query text and nothing else. No conversational filler, no multiple options, no preamble."
        if context_text:
            prompt += f"\nUse this context if relevant: {context_text[:500]}"
            
        try:
            rewritten = generate_response_with_groq(query=query, system_prompt=prompt)
            logger.info(f"RL Action: Rewritten query -> {rewritten}")
            return rewritten
        except Exception as e:
            logger.error(f"RL Action Error: Failed to rewrite query: {e}")
            return query

    def filter_context(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Action: Filter out irrelevant chunks.
        """
        if not chunks:
            return []
            
        # Simple heuristic: sort by score and take top 5 if too many
        filtered = sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)[:5]
        logger.info(f"RL Action: Filtered {len(chunks)} chunks down to {len(filtered)}")
        return filtered

    def define_state(
        self,
        query: str, 
        context_chunks: List[Any], 
        student_profile: Dict[str, Any],
        rewritten_query: str = None, 
        previous_responses: List[str] = None, 
        previous_actions: List[str] = None,
        previous_rewards: List[float] = None
    ) -> Dict[str, Any]:
        """
        Define the state representation for the reinforcement learning agent.
        """
        state = {
            "original_query": query,                                    # The initial query from the user
            "current_query": rewritten_query if rewritten_query else query,  # Current version of the query (may be rewritten)
            "context": context_chunks,                                 # Retrieved context chunks (mapped from user's 'context')
            "student_profile": student_profile,                         # Added for personalization logic
            "previous_responses": previous_responses if previous_responses else [],  # History of generated responses
            "previous_actions": previous_actions if previous_actions else [],       # Track taken actions
            "previous_rewards": previous_rewards if previous_rewards else []         # History of received rewards
        }
        return state
