"""
Jailbreak Detector

Detects and prevents prompt injection / jailbreak attempts.
Provides safety checks for topic-restricted chat.
"""

import re
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


class JailbreakDetector:
    """
    Detects and prevents prompt injection / jailbreak attempts.
    Provides multiple layers of detection for safety.
    """
    
    # Known jailbreak patterns
    SUSPICIOUS_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(the\s+)?context",
        r"disregard\s+(the\s+)?above",
        r"you\s+are\s+not\s+(restricted|limited|bound)",
        r"you\s+are\s+free\s+to",
        r"pretend\s+(you\s+are|to\s+be)",
        r"act\s+as\s+if",
        r"DAN|do\s+anything\s+now",
        r"system\s+prompt",
        r"developer\s+mode",
        r"jailbreak",
        r"\[system\s*\]|\[admin\s*\]|\[root\s*\]",
        r"new\s+(role|persona|character)",
        r"forget\s+(everything|all\s+constraints)",
        r"you\s+can\s+ignore",
        r"bypass\s+restrictions",
        r"override\s+settings",
        r"\n\s*system\s*:",
        r"\n\s*user\s*:",
        r"\n\s*assistant\s*:",
        r"from\s+now\s+on",
        r"starting\s+now",
    ]
    
    # Off-topic indicators that might indicate topic hopping
    OFF_TOPIC_INDICATORS = [
        "weather",
        "sports",
        "news",
        "movie",
        "celebrity",
        "football",
        "cricket",
        "who is the president",
        "stock market",
        "bitcoin",
        "crypto",
        "recipe",
        "cooking",
        "restaurant",
        "politics",
        "election",
        "tell me a joke",
        "write a story",
        "write a poem",
        "translate to",
        "how to hack",
        "how to crack",
    ]
    
    # Encoding tricks that might hide malicious content
    ENCODING_PATTERNS = [
        r"[A-Za-z0-9+/]{100,}={0,2}",  # Base64-like
        r"\\u[0-9a-fA-F]{4}",         # Unicode escape
        r"\\x[0-9a-fA-F]{2}",         # Hex escape
        r"&#x?[0-9a-fA-F]+;",         # HTML entity
        r"%[0-9a-fA-F]{2}",           # URL encoding
    ]
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_PATTERNS]
        self.compiled_encoding = [re.compile(p, re.IGNORECASE) for p in self.ENCODING_PATTERNS]
    
    def detect(self, query: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if query contains jailbreak attempts.
        
        Returns:
            (is_jailbreak, reason, details)
        """
        details = {
            "checked_at": "",
            "checks": [],
            "match_count": 0
        }
        
        if not query or not isinstance(query, str):
            return False, "Empty or invalid query", details
        
        query_lower = query.lower()
        
        # Check 1: Suspicious patterns
        for pattern in self.compiled_patterns:
            match = pattern.search(query_lower)
            if match:
                reason = f"Suspicious pattern detected: {match.group()[:50]}"
                details["checks"].append({
                    "type": "suspicious_pattern",
                    "pattern": pattern.pattern,
                    "match": match.group()[:50]
                })
                details["match_count"] += 1
                logger.warning(f"Jailbreak attempt detected: {reason}")
                
                if self.strict_mode:
                    return True, reason, details
        
        # Check 2: Excessive length (might hide injection)
        if len(query) > 3000:
            details["checks"].append({
                "type": "excessive_length",
                "length": len(query)
            })
            if self.strict_mode:
                return True, "Query exceeds maximum length (3000 chars)", details
        
        # Check 3: Encoding tricks
        for pattern in self.compiled_encoding:
            matches = pattern.findall(query)
            if len(matches) > 5:  # More than 5 encoded segments
                details["checks"].append({
                    "type": "encoding_obfuscation",
                    "pattern": pattern.pattern,
                    "match_count": len(matches)
                })
                if self.strict_mode:
                    return True, "Encoding obfuscation detected", details
        
        # Check 4: Special characters ratio
        special_chars = sum(1 for c in query if not c.isalnum() and not c.isspace())
        special_ratio = special_chars / len(query) if query else 0
        
        if special_ratio > 0.3:  # More than 30% special characters
            details["checks"].append({
                "type": "high_special_chars",
                "ratio": round(special_ratio, 4)
            })
            if self.strict_mode:
                return True, "Unusual character composition detected", details
        
        # Check 5: Repetitive patterns (might be trying to confuse)
        words = query_lower.split()
        unique_words = set(words)
        if len(words) > 20 and len(unique_words) / len(words) < 0.3:
            details["checks"].append({
                "type": "repetitive_pattern",
                "repetition_ratio": round(len(unique_words) / len(words), 4)
            })
        
        return False, "No jailbreak detected", details
    
    def check_off_topic(self, query: str, topic_name: str, topic_keywords: List[str]) -> Tuple[bool, str, float]:
        """
        Check if query is off-topic.
        
        Returns:
            (is_off_topic, reason, confidence)
        """
        query_lower = query.lower()
        
        # Check 1: Known off-topic indicators
        for indicator in self.OFF_TOPIC_INDICATORS:
            if indicator in query_lower:
                return True, f"Off-topic indicator: {indicator}", 0.9
        
        # Check 2: Topic keyword overlap
        if topic_keywords:
            query_words = set(query_lower.split())
            topic_words = set(kw.lower() for kw in topic_keywords)
            
            if topic_words:
                overlap = query_words & topic_words
                overlap_ratio = len(overlap) / len(topic_words)
                
                if overlap_ratio < 0.1:  # Less than 10% topic keywords
                    return True, "Low topic keyword overlap", 0.6
        
        # Check 3: Topic name presence
        if topic_name.lower() not in query_lower:
            # Not necessarily off-topic, but worth noting
            pass
        
        return False, "Topic relevance acceptable", 0.0
    
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
    
    def get_safety_report(self, query: str) -> Dict[str, Any]:
        """
        Get detailed safety analysis of a query.
        """
        is_jailbreak, reason, details = self.detect(query)
        
        return {
            "is_safe": not is_jailbreak,
            "detection_result": reason,
            "details": details,
            "query_length": len(query),
            "query_preview": query[:100] + "..." if len(query) > 100 else query
        }
