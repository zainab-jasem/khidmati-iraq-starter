"""
app/api/v1/reports.py
Citizen-facing report endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_active_user, require_citizen
from app.database import get_db
from app.models.comment import ReportComment
from app.models.report import Report
from app.models.status_history import ReportStatusHistory
from app.models.user import User, UserRole
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.report import (
    ReportCreate,
    ReportDetailResponse,
    ReportResponse,
    ReportUpdate,
    StatusHistoryResponse,
)
from app.services import report_service
router = APIRouter(prefix="/reports", tags=["Reports – Citizen"])
@router.post("", response_model=ReportResponse, status_code=201)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Submit a new service-problem report."""
    return report_service.create_report(db, citizen, data)


@router.get("/my", response_model=list[ReportResponse])
def my_reports(
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """List all reports submitted by the current citizen."""
    return (
        db.query(Report)
        .filter(Report.citizen_id == citizen.id)
        .order_by(Report.created_at.desc())
        .all()
    )
@router.get("/{report_id}", response_model=ReportDetailResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Get a single report — citizens can only see their own."""
    report = db.query(Report).filter(Report.id == report_id).first()
    
    # 1. التأكد من وجود البلاغ
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # 2. التأكد من أن البلاغ يخص هذا المواطن حصراً (FR-01)
    if report.citizen_id != citizen.id:
        raise HTTPException(
            status_code=403, 
            detail="You do not have permission to access this report"
        )
        
    return report
@router.patch("/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: int,
    data: ReportUpdate,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Update a report while it is still in 'submitted' status."""
    return report_service.update_citizen_report(db, citizen, report_id, data)


@router.post("/{report_id}/cancel", response_model=ReportResponse)
def cancel_report(
    report_id: int,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Cancel a submitted or under-review report."""
    return report_service.cancel_report(db, citizen, report_id)


@router.get("/{report_id}/history", response_model=list[StatusHistoryResponse])
def get_report_history(
    report_id: int,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Return the status-change history for the citizen's report."""
    # Ensure the citizen owns this report first.
    report_service.get_citizen_report(db, citizen, report_id)
    return (
        db.query(ReportStatusHistory)
        .filter(ReportStatusHistory.report_id == report_id)
        .order_by(ReportStatusHistory.created_at.asc())
        .all()
    )


@router.get("/{report_id}/comments", response_model=list[CommentResponse])
def get_report_comments(
    report_id: int,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """
    Return public comments on the citizen's report.
    Internal (staff) notes are hidden from citizens.
    """
    report_service.get_citizen_report(db, citizen, report_id)
    return (
        db.query(ReportComment)
        .filter(
            ReportComment.report_id == report_id,
            ReportComment.is_internal == False,
        )
        .order_by(ReportComment.created_at.asc())
        .all()
    )


@router.post("/{report_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    report_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    citizen: User = Depends(require_citizen),
):
    """Add a public comment to the citizen's own report."""
    # Ensure ownership before commenting.
    report_service.get_citizen_report(db, citizen, report_id)
    return report_service.add_comment(db, citizen, report_id, data.content, is_internal=False)
