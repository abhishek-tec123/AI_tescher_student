from fastapi import APIRouter, Depends
from studentProfileDetails.agents.mainAgent import (
    get_base_prompt,
    update_base_prompt_handler,
    UpdatePromptRequest,
)
from studentProfileDetails.auth.dependencies import require_role
from studentProfileDetails.managers.admin_manager import AdminManager
from studentProfileDetails.db_utils import StudentManager
from Teacher_AI_Agent.dbFun.collections import list_all_collections

router = APIRouter()

@router.post("/update-base-prompt")
def update_base_prompt(
    payload: UpdatePromptRequest,
    current_user: dict = Depends(require_role("admin"))
):
    return update_base_prompt_handler(payload)

@router.get("/current-base-prompt")
def get_current_prompt(current_user: dict = Depends(require_role("admin"))):
    return {
        "base_prompt": get_base_prompt()
    }

@router.get("/list-admins")
def list_admins(current_user: dict = Depends(require_role("admin"))):
    """List all admins (admin only)."""
    admin_manager = AdminManager()
    admins = admin_manager.list_admins()
    return {
        "total": len(admins),
        "admins": admins
    }

@router.get("/dashboard-counts")
def get_dashboard_stats(current_user: dict = Depends(require_role("admin"))):
    """Get dashboard statistics: all students, total agents, and total conversations."""
    # Get all students
    student_manager = StudentManager()
    students = student_manager.list_students()
    
    # Get all agents with their conversation counts
    agents_data = list_all_collections()
    total_agents = 0
    total_conversations = 0
    
    if agents_data["status"] == "success":
        agents = agents_data.get("agents", [])
        total_agents = len(agents)
        total_conversations = sum(agent.get("total_conversations", 0) for agent in agents)
    
    return {
        "students": {
            "total": len(students)
        },
        "agents": {
            "total": total_agents,
            "total_conversations": total_conversations
        }
    }
