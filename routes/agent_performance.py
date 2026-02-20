from fastapi import APIRouter, HTTPException, Query
from typing import List
from pydantic import BaseModel
from datetime import datetime
from studentProfileDetails.agents.agent_performance_monitor import AgentPerformanceMonitor

router = APIRouter(prefix="/agent-performance", tags=["agent-performance"])


# ================================
# RESPONSE MODELS
# ================================

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


class AgentOverviewWithCountResponse(BaseModel):
    agents: List[AgentOverviewResponse]
    total_agents: int

class HealthCheckResponse(BaseModel):
    critical_agents: List[AgentOverviewResponse]
    total_agents: int
    critical_count: int
    alert_summary: dict
    last_checked: str


# ================================
# STATIC ROUTES FIRST
# ================================

@router.get("/overview", response_model=AgentOverviewWithCountResponse)
async def get_all_agents_overview(
    days: int = Query(default=30, ge=1, le=365)
):
    try:
        monitor = AgentPerformanceMonitor()
        overview_data = monitor.get_all_agents_overview(days)
        agents = [AgentOverviewResponse(**agent) for agent in overview_data]
        return AgentOverviewWithCountResponse(
            agents=agents,
            total_agents=len(agents)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-check", response_model=HealthCheckResponse)
async def get_health_check(
    threshold_score: float = Query(default=60, ge=0, le=100)
):
    try:
        monitor = AgentPerformanceMonitor()
        critical_agents = monitor.get_agents_needing_attention(threshold_score)
        all_agents = monitor.get_all_agents_overview()

        alert_summary = {}
        for agent in all_agents:
            level = agent["performance_level"]
            alert_summary[level] = alert_summary.get(level, 0) + 1

        return HealthCheckResponse(
            critical_agents=[AgentOverviewResponse(**a) for a in critical_agents],
            total_agents=len(all_agents),
            critical_count=len(critical_agents),
            alert_summary=alert_summary,
            last_checked=datetime.utcnow().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_metrics_summary(
    days: int = Query(default=30, ge=1, le=365)
):
    try:
        monitor = AgentPerformanceMonitor()
        all_agents = monitor.get_all_agents_overview(days)

        if not all_agents:
            return {
                "message": "No agent data available",
                "period": f"Last {days} days",
                "total_agents": 0
            }

        total_conversations = sum(a["total_conversations"] for a in all_agents)
        avg_score = sum(a["overall_score"] for a in all_agents) / len(all_agents)

        performance_levels = {}
        for agent in all_agents:
            level = agent["performance_level"]
            performance_levels[level] = performance_levels.get(level, 0) + 1

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
            "top_performers": all_agents[:5],
            "agents_needing_attention": len([a for a in all_agents if a["overall_score"] < 60])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# DYNAMIC ROUTES (NAMESPACED)
# ================================

@router.get("/agent/{agent_id}", response_model=PerformanceResponse)
async def get_agent_performance(
    agent_id: str,
    days: int = Query(default=30, ge=1, le=365)
):
    try:
        monitor = AgentPerformanceMonitor()
        performance_data = monitor.get_agent_performance_metrics(agent_id, days)
        return PerformanceResponse(**performance_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}/trends")
async def get_agent_trends(
    agent_id: str,
    days: int = Query(default=30, ge=7, le=365)
):
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
        raise HTTPException(status_code=500, detail=str(e))