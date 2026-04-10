"""
Topic Boundary Detector (Semantic Safety Detection)

Uses semantic similarity to detect off-topic queries and jailbreak attempts.
Replaces regex-based detection with embedding-based topic boundary enforcement.
"""

import re
import logging
from typing import Tuple, List, Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from scipy.spatial.distance import cosine
    HAS_NUMPY = True
except ImportError:
    np = None
    cosine = None
    HAS_NUMPY = False


class TopicBoundaryDetector:
    """
    Uses semantic similarity to enforce topic boundaries.
    Detects off-topic queries by comparing embeddings to topic content.
    """
    
    # Basic jailbreak patterns (kept for critical safety cases)
    CRITICAL_PATTERNS = [
        r"\[system\s*\]|\[admin\s*\]|\[root\s*\]",
        r"\n\s*system\s*:",
        r"\n\s*user\s*:",
        r"\n\s*assistant\s*:",
    ]
    
    # Encoding tricks that might hide malicious content
    ENCODING_PATTERNS = [
        r"[A-Za-z0-9+/]{100,}={0,2}",  # Base64-like
        r"\\u[0-9a-fA-F]{4}",         # Unicode escape
        r"\\x[0-9a-fA-F]{2}",         # Hex escape
        r"&#x?[0-9a-fA-F]+;",         # HTML entity
        r"%[0-9a-fA-F]{2}",           # URL encoding
    ]
    
    def __init__(
        self,
        strict_mode: bool = True,
        embedding_model=None,
        similarity_threshold: float = 0.25,
        topic_centroid_similarity_threshold: float = 0.20
    ):
        self.strict_mode = strict_mode
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.topic_centroid_threshold = topic_centroid_similarity_threshold
        self.compiled_critical = [re.compile(p, re.IGNORECASE) for p in self.CRITICAL_PATTERNS]
        self.compiled_encoding = [re.compile(p, re.IGNORECASE) for p in self.ENCODING_PATTERNS]
        self._embedding_cache: Dict[str, List[float]] = {}
        self._topic_centroid_cache: Dict[str, List[float]] = {}
    
    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate embedding for query with caching."""
        cache_key = query.lower().strip()
        
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        if self.embedding_model is None:
            logger.error("No embedding model available")
            return None
        
        try:
            if hasattr(self.embedding_model, 'embed_query'):
                embedding = self.embedding_model.embed_query(query)
            elif hasattr(self.embedding_model, 'aembed_query'):
                embedding = await self.embedding_model.aembed_query(query)
            else:
                logger.error("Embedding model has no embed_query method")
                return None
            
            self._embedding_cache[cache_key] = embedding
            
            # Limit cache size
            if len(self._embedding_cache) > 1000:
                keys_to_remove = list(self._embedding_cache.keys())[:100]
                for key in keys_to_remove:
                    del self._embedding_cache[key]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def _calculate_topic_centroid(self, metadata_index: List[Dict]) -> Optional[List[float]]:
        """Calculate average embedding vector for topic."""
        cache_key = str(hash(str(sorted([m.get('chunk_id', '') for m in metadata_index]))))
        
        if cache_key in self._topic_centroid_cache:
            return self._topic_centroid_cache[cache_key]
        
        embeddings = [m['embedding'] for m in metadata_index if m.get('embedding')]
        if not embeddings:
            return None
        
        if HAS_NUMPY:
            centroid = np.mean(embeddings, axis=0).tolist()
        else:
            # Fallback: manual averaging
            dim = len(embeddings[0])
            centroid = [sum(e[i] for e in embeddings) / len(embeddings) for i in range(dim)]
        
        self._topic_centroid_cache[cache_key] = centroid
        return centroid
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not HAS_NUMPY:
            # Fallback implementation
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        
        return 1 - cosine(vec1, vec2)
    
    async def check_topic_boundary(
        self,
        query: str,
        topic_metadata: List[Dict],
        topic_name: str = "this topic"
    ) -> Tuple[bool, float, str, Dict[str, Any]]:
        """
        Check if query is semantically related to topic using embeddings.
        
        Returns:
            (is_on_topic, confidence_score, reason, details)
        """
        details = {
            "method": "semantic_similarity",
            "checks": [],
            "threshold": self.similarity_threshold,
            "topic_name": topic_name
        }
        
        if not query or not isinstance(query, str):
            return False, 0.0, "Empty or invalid query", details
        
        # Check 1: Critical patterns (system prompt injection)
        query_lower = query.lower()
        for pattern in self.compiled_critical:
            match = pattern.search(query_lower)
            if match:
                reason = f"Critical pattern detected: {match.group()[:50]}"
                details["checks"].append({
                    "type": "critical_pattern",
                    "match": match.group()[:50]
                })
                logger.warning(f"Safety check: {reason}")
                return False, 0.0, reason, details
        
        # Check 2: Encoding tricks
        for pattern in self.compiled_encoding:
            matches = pattern.findall(query)
            if len(matches) > 5:
                details["checks"].append({
                    "type": "encoding_obfuscation",
                    "match_count": len(matches)
                })
                if self.strict_mode:
                    return False, 0.0, "Encoding obfuscation detected", details
        
        # Check 3: Semantic similarity to topic (PRIMARY CHECK)
        query_embedding = await self._get_query_embedding(query)
        
        if query_embedding is None:
            logger.warning("Could not generate query embedding, falling back to permissive")
            return True, 1.0, "Embedding unavailable - allowing query", details
        
        # Calculate topic centroid
        topic_centroid = self._calculate_topic_centroid(topic_metadata)
        
        if topic_centroid is None:
            logger.warning("Could not calculate topic centroid, falling back to permissive")
            return True, 1.0, "Topic centroid unavailable - allowing query", details
        
        # Calculate similarity to topic centroid
        centroid_similarity = self._cosine_similarity(query_embedding, topic_centroid)
        details["centroid_similarity"] = round(centroid_similarity, 4)
        
        # Calculate similarity to best matching chunk
        best_chunk_similarity = 0.0
        best_chunk_id = None
        
        for meta in topic_metadata:
            chunk_embedding = meta.get('embedding')
            if chunk_embedding:
                sim = self._cosine_similarity(query_embedding, chunk_embedding)
                if sim > best_chunk_similarity:
                    best_chunk_similarity = sim
                    best_chunk_id = meta.get('chunk_id')
        
        details["best_chunk_similarity"] = round(best_chunk_similarity, 4)
        details["best_chunk_id"] = best_chunk_id
        
        # Determine if on-topic using combined criteria
        # Must pass BOTH: reasonable centroid similarity OR high chunk match
        is_on_topic = (
            centroid_similarity >= self.topic_centroid_threshold or
            best_chunk_similarity >= self.similarity_threshold
        )
        
        # Use the higher of the two scores as confidence
        confidence = max(centroid_similarity, best_chunk_similarity)
        
        if is_on_topic:
            reason = f"Query is semantically related to {topic_name}"
            details["checks"].append({
                "type": "semantic_match",
                "centroid_sim": round(centroid_similarity, 4),
                "chunk_sim": round(best_chunk_similarity, 4)
            })
        else:
            reason = f"Query appears off-topic for {topic_name} (similarity: {confidence:.2f})"
            details["checks"].append({
                "type": "semantic_mismatch",
                "centroid_sim": round(centroid_similarity, 4),
                "chunk_sim": round(best_chunk_similarity, 4),
                "threshold": self.similarity_threshold
            })
            logger.warning(f"Off-topic detected: {reason}")
        
        return is_on_topic, confidence, reason, details
    
    def detect(self, query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Legacy interface for basic safety checks (without topic context).
        
        Returns:
            (is_jailbreak, reason, details)
        """
        details = {
            "method": "basic_safety",
            "checks": []
        }
        
        if not query or not isinstance(query, str):
            return False, "Empty or invalid query", details
        
        query_lower = query.lower()
        
        # Check critical patterns only
        for pattern in self.compiled_critical:
            match = pattern.search(query_lower)
            if match:
                reason = f"Critical pattern detected: {match.group()[:50]}"
                details["checks"].append({
                    "type": "critical_pattern",
                    "match": match.group()[:50]
                })
                return True, reason, details
        
        # Check encoding
        for pattern in self.compiled_encoding:
            matches = pattern.findall(query)
            if len(matches) > 5:
                return True, "Encoding obfuscation detected", details
        
        # Check length
        if len(query) > 3000:
            return True, "Query exceeds maximum length (3000 chars)", details
        
        return False, "No jailbreak detected", details
    
    async def check_off_topic(
        self,
        query: str,
        topic_name: str,
        topic_metadata: List[Dict],
        topic_keywords: List[str] = None
    ) -> Tuple[bool, str, float, Dict[str, Any]]:
        """
        Check if query is off-topic using semantic similarity.
        
        Returns:
            (is_off_topic, reason, confidence, details)
        """
        is_on_topic, confidence, reason, details = await self.check_topic_boundary(
            query=query,
            topic_metadata=topic_metadata,
            topic_name=topic_name
        )
        
        # Invert for legacy interface
        is_off_topic = not is_on_topic
        
        return is_off_topic, reason, confidence, details
    
    def sanitize_query(self, query: str) -> str:
        """
        Basic sanitization of query.
        Removes potentially dangerous patterns while preserving meaning.
        """
        if not query:
            return ""
        
        sanitized = query
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())
        
        # Limit length
        if len(sanitized) > 3000:
            sanitized = sanitized[:3000]
        
        return sanitized
    
    async def get_safety_report(
        self,
        query: str,
        topic_metadata: List[Dict] = None,
        topic_name: str = "this topic"
    ) -> Dict[str, Any]:
        """
        Get detailed safety analysis of a query with semantic topic checking.
        """
        # Basic jailbreak detection
        is_jailbreak, reason, details = self.detect(query)
        
        # Semantic topic check if metadata available
        topic_check = None
        if topic_metadata:
            is_on_topic, confidence, topic_reason, topic_details = await self.check_topic_boundary(
                query=query,
                topic_metadata=topic_metadata,
                topic_name=topic_name
            )
            topic_check = {
                "is_on_topic": is_on_topic,
                "confidence": confidence,
                "reason": topic_reason,
                "details": topic_details
            }
        
        return {
            "is_safe": not is_jailbreak and (topic_check["is_on_topic"] if topic_check else True),
            "detection_result": reason,
            "details": details,
            "topic_check": topic_check,
            "query_length": len(query),
            "query_preview": query[:100] + "..." if len(query) > 100 else query
        }


# Backward compatibility alias
JailbreakDetector = TopicBoundaryDetector
