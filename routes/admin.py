from fastapi import APIRouter, Depends
from studentProfileDetails.agents.mainAgent import (
    get_base_prompt,
    update_base_prompt_handler,
    UpdatePromptRequest,
)
from studentProfileDetails.auth.dependencies import require_role
from studentProfileDetails.managers.admin_manager import AdminManager

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
