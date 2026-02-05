from fastapi import APIRouter
from studentProfileDetails.agents.mainAgent import (
    get_base_prompt,
    update_base_prompt_handler,
    UpdatePromptRequest,
)

router = APIRouter()

@router.post("/update-base-prompt")
def update_base_prompt(payload: UpdatePromptRequest):
    return update_base_prompt_handler(payload)

@router.get("/current-base-prompt")
def get_current_prompt():
    return {
        "base_prompt": get_base_prompt()
    }
