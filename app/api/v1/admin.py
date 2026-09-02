"""
app/api/v1/admin.py
Admin-only endpoints for user management, report oversight, and dashboard.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.database import get_db
from app.models.category import ServiceCategory
from app.models.report import Report, ReportPriority, ReportStatus
from app.models.user import User, UserRole
from app.schemas.report import (
    AssignRequest,
    PaginatedResponse,
    PriorityUpdateRequest,
    ReportDetailResponse,
    ReportResponse,
)
from app.schemas.user import CreateEmployeeRequest, UserPublic
from app.services import report_service

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Employee management
# ---------------------------------------------------------------------------

@router.post("/employees", response_model=UserPublic, status_code=201)
def create_employee(
    data: CreateEmployeeRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin creates a new employee account."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ConflictError("An account with this email already exists.")

    from app.models.governorate import Governorate
    governorate = db.get(Governorate, data.governorate_id)
    if not governorate or not governorate.is_active:
        from app.core.exceptions import BadRequestError
        raise BadRequestError("INVALID_GOVERNORATE", "Governorate not found or inactive.")

    employee = User(
        full_name=data.full_name,
        email=data.email,
        phone_number=data.phone_number,
        hashed_password=hash_password(data.password),
        role=UserRole.employee,
        governorate_id=data.governorate_id,
        is_active=True,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return UserPublic.model_validate(employee)


# ---------------------------------------------------------------------------
# User listing
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all users."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/status", response_model=UserPublic)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Activate or deactivate a user account."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User")
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


# ---------------------------------------------------------------------------
# Report management
# ---------------------------------------------------------------------------
@router.patch("/reports/{report_id}/priority", response_model=ReportResponse)
def update_report_priority(
    report_id: int,
    data: PriorityUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    FR-09: Admin updates report priority level.
    """
    return report_service.admin_update_priority(db, report_id, data)
@router.get("/reports", response_model=PaginatedResponse)
def list_reports(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    List all reports.
    TODO (TASK-01): Implement filtering, search, and pagination.
    """
    items = db.query(Report).order_by(Report.created_at.desc()).all()

    return PaginatedResponse(
        page=1,
        page_size=len(items) if items else 20,
        total=len(items),
        items=[ReportResponse.model_validate(r) for r in items],
    )


@router.patch("/reports/{report_id}/assign", response_model=ReportResponse)
def assign_report(
    report_id: int,
    data: AssignRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Assign an employee to a report."""
    return report_service.admin_assign_report(db, admin, report_id, data)


@router.patch("/reports/{report_id}/priority", response_model=ReportResponse)
def update_priority(
    report_id: int,
    data: PriorityUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update the priority of a report."""
    return report_service.admin_update_priority(db, report_id, data)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    High-level statistics for the admin dashboard.
    TODO (TASK-08): Complete the dashboard implementation.
    """
    return {
        "total_reports": 0,
        "open_reports": 0,
        "resolved_reports": 0,
        "reports_by_status": {},
        "reports_by_priority": {},
        "reports_by_category": {},
    }
