from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from studentProfileDetails.models.auth_models import (
    LoginRequest, LoginResponse, TokenRefreshRequest, TokenRefreshResponse,
    PasswordResetRequest, PasswordResetConfirm, PasswordChangeRequest,
    StudentCreateWithAuth, AdminCreateRequest, UserResponse
)
from studentProfileDetails.db_utils import StudentManager
from studentProfileDetails.auth.dependencies import get_current_user, require_role

from studentProfileDetails.managers.authUtils import (handle_login,handle_refresh_token,handle_change_password,
    handle_create_student_with_auth,handle_create_admin,handle_admin_reset_student_password)

class ResetPasswordRequest_admin_reset_student(BaseModel):
    current_password: str
    new_password: str
router = APIRouter()
security = HTTPBearer()

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    return handle_login(payload.email, payload.password)


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(payload: TokenRefreshRequest):
    return handle_refresh_token(payload.refresh_token)

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(**current_user)

@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Change current user's password."""

    return handle_change_password(
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password
    )
@router.post("/create-student-with-auth")
def create_student_with_auth(
    payload: StudentCreateWithAuth,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new student with authentication (admin only)."""
    return handle_create_student_with_auth(payload)

@router.post("/create-admin")
def create_admin(
    payload: AdminCreateRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new admin (admin only)."""
    return handle_create_admin(payload)

@router.post("/admin/admin-reset-student-password/{student_id}")
def reset_student_password(
    student_id: str,
    payload: ResetPasswordRequest_admin_reset_student,
    current_user: dict = Depends(get_current_user),
):
    return handle_admin_reset_student_password(
        student_id=student_id,
        payload=payload,
        current_user=current_user,
    )
