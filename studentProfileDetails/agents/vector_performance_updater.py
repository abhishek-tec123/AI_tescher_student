"""
Vector Performance Updater

Updates performance data directly in vector documents after each conversation.
This keeps performance tracking with the agent documents themselves.
"""

import os
from datetime import datetime
from pymongo import MongoClient
from typing import Dict, Any

class VectorPerformanceUpdater:
    """Updates performance data in vector documents."""
    
    def __init__(self):
        self.client = MongoClient(os.environ.get("MONGODB_URI"))
    
    def update_agent_performance_in_vectors(self, subject_agent_id: str, quality_scores: Dict[str, float], 
                                          feedback: str = "neutral", confusion_type: str = "NO_CONFUSION",
                                          student_id: str = None) -> bool:
        """
        Update performance data for an agent in all vector documents.
        
        Args:
            subject_agent_id: The agent ID to update
            quality_scores: Dictionary with pedagogical_value, critical_confidence, etc.
            feedback: Student feedback (like/dislike/neutral)
            confusion_type: Detected confusion type
            student_id: Student ID (optional, for tracking unique students)
        
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            # Find all databases and collections that contain this agent
            updated_count = 0
            
            for db_name in self.client.list_database_names():
                if db_name in ["admin", "local", "config", "teacher_ai"]:
                    continue
                    
                db = self.client[db_name]
                
                for collection_name in db.list_collection_names():
                    collection = db[collection_name]
                    
                    # Check if this collection has the agent
                    sample_doc = collection.find_one({"subject_agent_id": subject_agent_id})
                    if sample_doc:
                        # Get current performance data from first document
                        current_performance = sample_doc.get("performance", self._get_default_performance())
                        
                        # Update performance metrics with student tracking
                        updated_performance = self._calculate_updated_performance(
                            current_performance, quality_scores, feedback, confusion_type, student_id
                        )
                        
                        # Update ALL documents for this agent in this collection
                        result = collection.update_many(
                            {"subject_agent_id": subject_agent_id},
                            {"$set": {"performance": updated_performance}}
                        )
                        
                        if result.modified_count > 0:
                            updated_count += result.modified_count
                            print(f"✅ Updated {result.modified_count} documents in {db_name}.{collection_name}")
            
            if updated_count > 0:
                print(f"✅ Total updated: {updated_count} vector documents for {subject_agent_id}")
                return True
            else:
                print(f"⚠️ No documents found for agent {subject_agent_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating vector performance: {e}")
            return False
    
    def _get_default_performance(self) -> Dict[str, Any]:
        """Get default performance structure."""
        return {
            "performance_period": "Last 30 days",
            "total_conversations": 0,
            "metrics": {
                "pedagogical_value": 0,
                "critical_confidence": 0,
                "rag_relevance": 0,
                "answer_completeness": 0,
                "hallucination_risk": 0,
                "overall_score": 0,
                "satisfaction_rate": 0,
                "feedback_counts": {
                    "like": 0,
                    "dislike": 0,
                    "neutral": 0
                },
                "confusion_distribution": {}
            },
            "performance_level": "Critical",
            "health_indicators": {
                "quality_health": {"status": "No Data", "color": "gray"},
                "hallucination_health": {"status": "No Data", "color": "gray"},
                "satisfaction_health": {"status": "No Data", "color": "gray"}
            },
            "trend_analysis": {"trend": "No Data", "direction": "neutral"},
            "recommendations": ["Agent has no conversation data - needs testing and deployment"],
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _calculate_updated_performance(
        self,
        current_performance: Dict[str, Any],
        quality_scores: Dict[str, float],
        feedback: str,
        confusion_type: str,
        student_id: str = None
    ) -> Dict[str, Any]:
        """Calculate updated performance metrics."""

        MULTIPLIER = 1.0  # ← Applied every time

        total_conversations = current_performance.get("total_conversations", 0)
        current_metrics = current_performance.get("metrics", {})
        current_feedback_counts = current_metrics.get(
            "feedback_counts", {"like": 0, "dislike": 0, "neutral": 0}
        )
        current_confusion_dist = current_metrics.get("confusion_distribution", {})

        current_student_usage = current_performance.get("student_usage", {
            "total_students": 0,
            "student_ids": [],
            "conversation_per_student": {},
            "student_performance": {}
        })

        new_total_conversations = total_conversations + 1

        # -------- Running averages --------
        new_metrics = {}
        metric_keys = [
            "pedagogical_value",
            "critical_confidence",
            "rag_relevance",
            "answer_completeness",
            "hallucination_risk"
        ]

        for metric in metric_keys:
            current_value = current_metrics.get(metric, 0)
            new_value = quality_scores.get(metric, 0)

            avg = ((current_value * total_conversations) + new_value) / new_total_conversations

            # 🔥 Apply multiplier and cap at 100
            new_metrics[metric] = min(avg * MULTIPLIER, 100)

        # -------- Overall score (exclude hallucination_risk) --------
        core_metrics = [
            "pedagogical_value",
            "critical_confidence",
            "rag_relevance",
            "answer_completeness"
        ]

        core_values = [new_metrics[m] for m in core_metrics]
        overall_score = sum(core_values) / len(core_values) if core_values else 0
        new_metrics["overall_score"] = min(overall_score, 100)

        # -------- Feedback update --------
        new_feedback_counts = current_feedback_counts.copy()
        if feedback in new_feedback_counts:
            new_feedback_counts[feedback] += 1

        total_feedback = sum(new_feedback_counts.values())
        satisfaction_rate = (
            new_feedback_counts["like"] / total_feedback * 100
            if total_feedback > 0 else 0
        )

        new_metrics["satisfaction_rate"] = round(satisfaction_rate, 1)
        new_metrics["feedback_counts"] = new_feedback_counts

        # -------- Confusion distribution --------
        new_confusion_dist = current_confusion_dist.copy()
        new_confusion_dist[confusion_type] = new_confusion_dist.get(confusion_type, 0) + 1
        new_metrics["confusion_distribution"] = new_confusion_dist

        # -------- Student tracking --------
        new_student_usage = current_student_usage.copy()

        if student_id:
            if student_id not in new_student_usage["student_ids"]:
                new_student_usage["student_ids"].append(student_id)
                new_student_usage["total_students"] += 1

            current_student_conversations = new_student_usage["conversation_per_student"].get(student_id, 0)
            new_student_usage["conversation_per_student"][student_id] = current_student_conversations + 1

            student_current_performance = new_student_usage["student_performance"].get(student_id, {
                "conversations": 0,
                "average_score": 0,
                "feedback_counts": {"like": 0, "dislike": 0, "neutral": 0}
            })

            student_conversations = student_current_performance["conversations"] + 1

            student_average_score = (
                (student_current_performance["average_score"] *
                student_current_performance["conversations"])
                + new_metrics["overall_score"]
            ) / student_conversations

            student_feedback_counts = student_current_performance["feedback_counts"].copy()
            if feedback in student_feedback_counts:
                student_feedback_counts[feedback] += 1

            new_student_usage["student_performance"][student_id] = {
                "conversations": student_conversations,
                "average_score": round(student_average_score, 1),
                "feedback_counts": student_feedback_counts,
                "last_interaction": datetime.utcnow().isoformat()
            }

        # -------- Performance level --------
        if overall_score >= 85:
            performance_level = "Excellent"
        elif overall_score >= 70:
            performance_level = "Good"
        elif overall_score >= 55:
            performance_level = "Average"
        elif overall_score >= 40:
            performance_level = "Poor"
        else:
            performance_level = "Critical"

        health_indicators = self._calculate_health_indicators(new_metrics)
        recommendations = self._generate_recommendations(
            new_metrics, performance_level, new_student_usage
        )

        updated_performance =  {
            "performance_period": "All Time (Cumulative)",
            "total_conversations": new_total_conversations,
            "unique_students": new_student_usage["total_students"],
            "student_usage": new_student_usage,
            "metrics": new_metrics,
            "performance_level": performance_level,
            "health_indicators": health_indicators,
            "trend_analysis": {"trend": "Stable", "direction": "neutral"},
            "recommendations": recommendations,
            "last_updated": datetime.utcnow().isoformat()
        }

        return updated_performance
        
    def _calculate_health_indicators(self, metrics: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Calculate health indicators based on metrics."""
        overall_score = metrics.get("overall_score", 0)
        hallucination_risk = metrics.get("hallucination_risk", 0)
        satisfaction_rate = metrics.get("satisfaction_rate", 0)
        
        # Quality health based on overall score
        if overall_score >= 85:
            quality_health = {"status": "Excellent", "color": "green"}
        elif overall_score >= 70:
            quality_health = {"status": "Good", "color": "blue"}
        elif overall_score >= 55:
            quality_health = {"status": "Average", "color": "yellow"}
        elif overall_score >= 40:
            quality_health = {"status": "Poor", "color": "orange"}
        else:
            quality_health = {"status": "Critical", "color": "red"}
        
        # Hallucination health based on risk score (higher = better)
        if hallucination_risk >= 85:
            hallucination_health = {"status": "Safe", "color": "green"}
        elif hallucination_risk >= 70:
            hallucination_health = {"status": "Low Risk", "color": "blue"}
        elif hallucination_risk >= 55:
            hallucination_health = {"status": "Moderate Risk", "color": "yellow"}
        elif hallucination_risk >= 40:
            hallucination_health = {"status": "High Risk", "color": "orange"}
        else:
            hallucination_health = {"status": "Critical Risk", "color": "red"}
        
        # Satisfaction health based on satisfaction rate
        if satisfaction_rate >= 85:
            satisfaction_health = {"status": "Excellent", "color": "green"}
        elif satisfaction_rate >= 70:
            satisfaction_health = {"status": "Good", "color": "blue"}
        elif satisfaction_rate >= 55:
            satisfaction_health = {"status": "Average", "color": "yellow"}
        elif satisfaction_rate >= 40:
            satisfaction_health = {"status": "Poor", "color": "orange"}
        else:
            satisfaction_health = {"status": "Critical", "color": "red"}
        
        return {
            "quality_health": quality_health,
            "hallucination_health": hallucination_health,
            "satisfaction_health": satisfaction_health
        }
    
    def _generate_recommendations(self, metrics: Dict[str, Any], performance_level: str, student_usage: Dict[str, Any] = None) -> list:
        """Generate recommendations based on performance metrics."""
        recommendations = []
        
        overall_score = metrics.get("overall_score", 0)
        hallucination_risk = metrics.get("hallucination_risk", 0)
        satisfaction_rate = metrics.get("satisfaction_rate", 0)
        total_conversations = metrics.get("total_conversations", 0)
        
        if total_conversations == 0:
            recommendations.append("Agent has no conversation data - needs testing and deployment")
            return recommendations
        
        if overall_score >= 85:
            recommendations.append("Agent is performing excellently - maintain current configuration")
            recommendations.append("Consider sharing best practices with lower-performing agents")
        elif overall_score >= 70:
            recommendations.append("Agent is performing well - continue current approach")
        elif overall_score >= 55:
            recommendations.append("Agent performance is average - consider optimization")
        else:
            recommendations.append("Agent needs immediate attention and improvement")
        
        if hallucination_risk < 70:
            recommendations.append("Review and improve response accuracy to reduce hallucination risk")
        
        if satisfaction_rate < 70:
            recommendations.append("Investigate student feedback to improve satisfaction")
        
        # Add student usage recommendations
        if student_usage:
            total_students = student_usage.get("total_students", 0)
            if total_students > 0:
                recommendations.append(f"Agent has been used by {total_students} unique students")
                
                # Find most active students
                student_conversations = student_usage.get("conversation_per_student", {})
                if student_conversations:
                    top_students = sorted(student_conversations.items(), key=lambda x: x[1], reverse=True)[:3]
                    recommendations.append("Most active students:")
                    for student_id, conv_count in top_students:
                        recommendations.append(f"  - Student {student_id}: {conv_count} conversations")
                
                # Find student performance insights
                student_performance = student_usage.get("student_performance", {})
                if student_performance:
                    high_performers = []
                    low_performers = []
                    
                    for student_id, perf in student_performance.items():
                        avg_score = perf.get("average_score", 0)
                        if avg_score >= 80:
                            high_performers.append(student_id)
                        elif avg_score < 60:
                            low_performers.append(student_id)
                    
                    if high_performers:
                        recommendations.append(f"High-performing students: {', '.join(high_performers)}")
                    if low_performers:
                        recommendations.append(f"Students needing support: {', '.join(low_performers)}")
        
        if not recommendations:
            recommendations.append("Continue monitoring agent performance")
        
        return recommendations
    
    def get_agent_performance_from_vectors(self, subject_agent_id: str) -> Dict[str, Any]:
        """Get performance data from vector documents."""
        try:
            for db_name in self.client.list_database_names():
                if db_name in ["admin", "local", "config", "teacher_ai"]:
                    continue
                    
                db = self.client[db_name]
                
                for collection_name in db.list_collection_names():
                    collection = db[collection_name]
                    
                    # Find first document with this agent
                    doc = collection.find_one({"subject_agent_id": subject_agent_id})
                    if doc:
                        performance = doc.get("performance", self._get_default_performance())
                        
                        # Add agent metadata
                        agent_metadata = doc.get("agent_metadata", {})
                        
                        return {
                            "agent_id": subject_agent_id,
                            "agent_metadata": agent_metadata,
                            **performance
                        }
            
            # Return default if not found
            return {
                "agent_id": subject_agent_id,
                "agent_metadata": {},
                **self._get_default_performance()
            }
            
        except Exception as e:
            print(f"❌ Error getting performance from vectors: {e}")
            return {
                "agent_id": subject_agent_id,
                "agent_metadata": {},
                **self._get_default_performance()
            }

# Convenience function for easy usage
def update_vector_performance(subject_agent_id: str, quality_scores: Dict[str, float], 
                             feedback: str = "neutral", confusion_type: str = "NO_CONFUSION",
                             student_id: str = None) -> bool:
    """
    Update agent performance in vector documents after each conversation.
    
    Call this function after each agent query to maintain performance tracking.
    
    Args:
        subject_agent_id: The agent ID
        quality_scores: Dictionary with pedagogical_value, critical_confidence, etc.
        feedback: Student feedback (like/dislike/neutral)
        confusion_type: Detected confusion type
        student_id: Student ID (optional, for tracking unique students)
    
    Returns:
        bool: True if update successful, False otherwise
    """
    try:
        updater = VectorPerformanceUpdater()
        return updater.update_agent_performance_in_vectors(
            subject_agent_id=subject_agent_id,
            quality_scores=quality_scores,
            feedback=feedback,
            confusion_type=confusion_type,
            student_id=student_id
        )
    except Exception as e:
        print(f"❌ Error updating vector performance: {e}")
        return False

def get_vector_performance(subject_agent_id: str) -> Dict[str, Any]:
    """
    Get agent performance from vector documents.
    
    Args:
        subject_agent_id: The agent ID
        
    Returns:
        Dict containing performance data
    """
    try:
        updater = VectorPerformanceUpdater()
        return updater.get_agent_performance_from_vectors(subject_agent_id)
    except Exception as e:
        print(f"❌ Error getting vector performance: {e}")
        return {
            "agent_id": subject_agent_id,
            "agent_metadata": {},
            "performance_period": "Last 30 days",
            "total_conversations": 0,
            "metrics": {
                "pedagogical_value": 0,
                "critical_confidence": 0,
                "rag_relevance": 0,
                "answer_completeness": 0,
                "hallucination_risk": 0,
                "overall_score": 0,
                "satisfaction_rate": 0,
                "feedback_counts": {"like": 0, "dislike": 0, "neutral": 0},
                "confusion_distribution": {}
            },
            "performance_level": "Critical",
            "health_indicators": {
                "quality_health": {"status": "No Data", "color": "gray"},
                "hallucination_health": {"status": "No Data", "color": "gray"},
                "satisfaction_health": {"status": "No Data", "color": "gray"}
            },
            "trend_analysis": {"trend": "No Data", "direction": "neutral"},
            "recommendations": ["Agent has no conversation data - needs testing and deployment"],
            "last_updated": datetime.utcnow().isoformat()
        }
