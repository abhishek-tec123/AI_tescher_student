from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from studentProfileDetails.agents.agent_performance_monitor import AgentPerformanceMonitor

router = APIRouter(prefix="/agent-performance", tags=["agent-performance"])

class PerformanceResponse(BaseModel):
    agent_id: str
    agent_metadata: dict
    performance_period: str
    total_conversations: int
    metrics: dict
    performance_level: str
    health_indicators: dict
    trend_analysis: dict
    recommendations: List[str]
    last_updated: str

class AgentOverviewResponse(BaseModel):
    agent_id: str
    agent_name: str
    class_name: str
    subject: str
    overall_score: float
    performance_level: str
    total_conversations: int
    health_status: str
    last_updated: str

class HealthCheckResponse(BaseModel):
    critical_agents: List[AgentOverviewResponse]
    total_agents: int
    critical_count: int
    alert_summary: dict
    last_checked: str

@router.get("/{agent_id}", response_model=PerformanceResponse)
async def get_agent_performance(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze")
):
    """
    Get detailed performance metrics for a specific agent.
    
    - **agent_id**: The subject_agent_id of the agent
    - **days**: Number of days to analyze (1-365)
    
    Returns comprehensive performance analysis including:
    - Quality scores (pedagogical value, confidence, relevance, completeness)
    - Hallucination risk assessment
    - Student satisfaction metrics
    - Health indicators with color-coded status
    - Performance trends over time
    - Actionable recommendations
    """
    try:
        monitor = AgentPerformanceMonitor()
        performance_data = monitor.get_agent_performance_metrics(agent_id, days)
        
        return PerformanceResponse(**performance_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent performance: {str(e)}"
        )

@router.get("/overview", response_model=List[AgentOverviewResponse])
async def get_all_agents_overview(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze")
):
    """
    Get performance overview for all agents.
    
    - **days**: Number of days to analyze (1-365)
    
    Returns a summary of all agents including:
    - Agent ID, name, class, and subject
    - Overall performance score
    - Performance level (Excellent, Good, Average, Poor, Critical)
    - Total conversation count
    - Health status
    - Last update timestamp
    
    Sorted by overall score (highest first).
    """
    try:
        monitor = AgentPerformanceMonitor()
        overview_data = monitor.get_all_agents_overview(days)
        
        return [AgentOverviewResponse(**agent) for agent in overview_data]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agents overview: {str(e)}"
        )

@router.get("/health-check", response_model=HealthCheckResponse)
async def get_health_check(
    threshold_score: float = Query(default=60, ge=0, le=100, description="Performance threshold for alerts")
):
    """
    Get health check for all agents needing attention.
    
    - **threshold_score**: Performance score threshold (0-100)
    
    Returns:
    - List of critical agents (below threshold)
    - Total agent count and critical count
    - Alert summary by performance level
    - Last check timestamp
    
    Useful for monitoring and alerting systems.
    """
    try:
        monitor = AgentPerformanceMonitor()
        critical_agents = monitor.get_agents_needing_attention(threshold_score)
        all_agents = monitor.get_all_agents_overview()
        
        # Generate alert summary
        alert_summary = {}
        for agent in all_agents:
            level = agent["performance_level"]
            alert_summary[level] = alert_summary.get(level, 0) + 1
        
        health_check_data = {
            "critical_agents": [AgentOverviewResponse(**agent) for agent in critical_agents],
            "total_agents": len(all_agents),
            "critical_count": len(critical_agents),
            "alert_summary": alert_summary,
            "last_checked": datetime.utcnow().isoformat()
        }
        
        return HealthCheckResponse(**health_check_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error performing health check: {str(e)}"
        )

@router.get("/trends/{agent_id}")
async def get_agent_trends(
    agent_id: str,
    days: int = Query(default=30, ge=7, le=365, description="Number of days to analyze")
):
    """
    Get detailed trend analysis for a specific agent.
    
    - **agent_id**: The subject_agent_id of the agent
    - **days**: Number of days to analyze (7-365)
    
    Returns detailed trend data including:
    - Performance direction (up/down/stable)
    - Score changes over time
    - Period-by-period comparison
    - Trend visualization data
    """
    try:
        monitor = AgentPerformanceMonitor()
        performance_data = monitor.get_agent_performance_metrics(agent_id, days)
        
        return {
            "agent_id": agent_id,
            "trend_analysis": performance_data["trend_analysis"],
            "performance_history": performance_data["metrics"],
            "recommendations": performance_data["recommendations"],
            "analysis_period": f"Last {days} days"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving agent trends: {str(e)}"
        )

@router.get("/compare")
async def compare_agents(
    agent_ids: List[str] = Query(description="List of agent IDs to compare"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze")
):
    """
    Compare performance metrics between multiple agents.
    
    - **agent_ids**: List of subject_agent_ids to compare
    - **days**: Number of days to analyze (1-365)
    
    Returns side-by-side comparison including:
    - Performance metrics for each agent
    - Relative rankings
    - Strengths and weaknesses analysis
    - Comparative insights
    """
    try:
        if len(agent_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 agent IDs required for comparison"
            )
        
        monitor = AgentPerformanceMonitor()
        comparison_data = []
        
        for agent_id in agent_ids:
            performance = monitor.get_agent_performance_metrics(agent_id, days)
            comparison_data.append({
                "agent_id": agent_id,
                "agent_name": performance["agent_metadata"].get("agent_metadata", {}).get("agent_name", "Unknown"),
                "class_name": performance["agent_metadata"].get("class", "Unknown"),
                "subject": performance["agent_metadata"].get("subject", "Unknown"),
                "overall_score": performance["metrics"]["overall_score"],
                "performance_level": performance["performance_level"].value,
                "metrics": performance["metrics"],
                "health_indicators": performance["health_indicators"]
            })
        
        # Sort by overall score for ranking
        comparison_data.sort(key=lambda x: x["overall_score"], reverse=True)
        
        # Add rankings
        for i, agent in enumerate(comparison_data, 1):
            agent["rank"] = i
        
        return {
            "comparison_period": f"Last {days} days",
            "agents_compared": len(agent_ids),
            "comparison_data": comparison_data,
            "best_performer": comparison_data[0] if comparison_data else None,
            "worst_performer": comparison_data[-1] if comparison_data else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing agents: {str(e)}"
        )

@router.get("/metrics/summary")
async def get_metrics_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze")
):
    """
    Get aggregated metrics summary across all agents.
    
    - **days**: Number of days to analyze (1-365)
    
    Returns system-wide metrics including:
    - Average performance scores
    - Performance distribution
    - Total conversations
    - Health statistics
    - System-wide trends
    """
    try:
        monitor = AgentPerformanceMonitor()
        all_agents = monitor.get_all_agents_overview(days)
        
        if not all_agents:
            return {
                "message": "No agent data available",
                "period": f"Last {days} days",
                "total_agents": 0
            }
        
        # Calculate aggregates
        total_conversations = sum(agent["total_conversations"] for agent in all_agents)
        avg_score = sum(agent["overall_score"] for agent in all_agents) / len(all_agents)
        
        # Performance distribution
        performance_levels = {}
        for agent in all_agents:
            level = agent["performance_level"]
            performance_levels[level] = performance_levels.get(level, 0) + 1
        
        # Health distribution
        health_distribution = {}
        for agent in all_agents:
            health = agent["health_status"]
            health_distribution[health] = health_distribution.get(health, 0) + 1
        
        return {
            "period": f"Last {days} days",
            "total_agents": len(all_agents),
            "total_conversations": total_conversations,
            "average_score": round(avg_score, 1),
            "performance_distribution": performance_levels,
            "health_distribution": health_distribution,
            "top_performers": all_agents[:3],
            "agents_needing_attention": len([a for a in all_agents if a["overall_score"] < 60])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving metrics summary: {str(e)}"
        )
