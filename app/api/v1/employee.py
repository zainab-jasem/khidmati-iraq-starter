"""
app/api/v1/employee.py
Employee-facing endpoints for managing reports within their governorate.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_employee
from app.database import get_db
from app.models.comment import ReportComment
from app.models.report import Report
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.report import (
    ReportDetailResponse,
    ReportResponse,
    ResolveRequest,
    StatusUpdateRequest,
)
from app.services import report_service

router = APIRouter(prefix="/employee", tags=["Employee"])


@router.get("/reports", response_model=list[ReportResponse])
def list_governorate_reports(
    status: Optional[ReportStatus] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """FR-06: List and filter reports in the employee's governorate."""
    query = db.query(Report).filter(Report.governorate_id == employee.governorate_id)

    if status:
        query = query.filter(Report.status == status)
    if category_id:
        query = query.filter(Report.category_id == category_id)

    return query.order_by(Report.created_at.desc()).all()


@router.get("/reports/assigned", response_model=list[ReportResponse])
def list_assigned_reports(
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """List reports assigned to the current employee."""
    return (
        db.query(Report)
        .filter(Report.assigned_employee_id == employee.id)
        .order_by(Report.created_at.desc())
        .all()
    )


@router.patch("/reports/{report_id}/status", response_model=ReportResponse)
def update_status(
    report_id: int,
    data: StatusUpdateRequest,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """Update the status of a report in the employee's governorate."""
    return report_service.employee_update_status(db, employee, report_id, data)


@router.post("/reports/{report_id}/comments", response_model=CommentResponse, status_code=201)
def add_public_comment(
    report_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """Add a public comment to a report (visible to the citizen)."""
    report_service.get_report_for_employee(db, employee, report_id)
    return report_service.add_comment(db, employee, report_id, data.content, is_internal=False)


@router.post("/reports/{report_id}/internal-notes", response_model=CommentResponse, status_code=201)
def add_internal_note(
    report_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """Add an internal note (not visible to citizens)."""
    report_service.get_report_for_employee(db, employee, report_id)
    return report_service.add_comment(db, employee, report_id, data.content, is_internal=True)


@router.post("/reports/{report_id}/resolve", response_model=ReportResponse)
def resolve_report(
    report_id: int,
    data: ResolveRequest,
    db: Session = Depends(get_db),
    employee: User = Depends(require_employee),
):
    """Resolve a report with a mandatory resolution summary."""
    return report_service.employee_resolve_report(db, employee, report_id, data)
