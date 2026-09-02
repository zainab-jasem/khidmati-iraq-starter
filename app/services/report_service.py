"""
app/services/report_service.py
Core business logic for report management.
All status-transition rules live in this file.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestError,
    InvalidStatusTransitionError,
    NotFoundError,
    PermissionDeniedError,
)
from app.models.area import Area
from app.models.category import ServiceCategory
from app.models.comment import ReportComment
from app.models.governorate import Governorate
from app.models.report import Report, ReportPriority, ReportStatus, generate_reference_number
from app.models.status_history import ReportStatusHistory
from app.models.user import User, UserRole
from app.schemas.report import (
    AssignRequest,
    PriorityUpdateRequest,
    ReportCreate,
    ReportUpdate,
    ResolveRequest,
    StatusUpdateRequest,
)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

# Allowed transitions for employees
# TODO (TASK-05): Define valid transitions
EMPLOYEE_TRANSITIONS: dict[ReportStatus, list[ReportStatus]] = {}

def validate_transition(from_status: ReportStatus, to_status: ReportStatus) -> None:
    """
    TODO (TASK-05): Raise InvalidStatusTransitionError if the transition is not allowed.
    """
    pass


# ---------------------------------------------------------------------------
# Helper: record a status change in history
# ---------------------------------------------------------------------------

def record_status_change(
    db: Session,
    report: Report,
    new_status: ReportStatus,
    changed_by: User,
    note: str | None = None,
) -> None:
    """
    Update report.status and append a ReportStatusHistory row.
    Does NOT commit – the caller is responsible for the transaction.
    """
    history = ReportStatusHistory(
        report_id=report.id,
        previous_status=report.status.value if report.status else None,
        new_status=new_status.value,
        changed_by_id=changed_by.id,
        note=note,
    )
    report.status = new_status
    db.add(history)


# ---------------------------------------------------------------------------
# Helper: validate location consistency
# ---------------------------------------------------------------------------

def validate_location(
    db: Session,
    governorate_id: int,
    area_id: int,
    category_id: int,
) -> tuple[Governorate, Area, ServiceCategory]:
    """
    Ensure the governorate, area, and category exist, are active,
    and that the area belongs to the governorate.
    """
    governorate = db.get(Governorate, governorate_id)
    if not governorate or not governorate.is_active:
        raise BadRequestError("INVALID_GOVERNORATE", "Governorate not found or inactive.")

    area = db.get(Area, area_id)
    if not area or not area.is_active:
        raise BadRequestError("INVALID_AREA", "Area not found or inactive.")
    if area.governorate_id != governorate_id:
        raise BadRequestError("INVALID_AREA_GOVERNORATE", "Area does not belong to the selected governorate.")

    category = db.get(ServiceCategory, category_id)
    if not category or not category.is_active:
        raise BadRequestError("INVALID_CATEGORY", "Category not found or inactive.")

    return governorate, area, category


# ---------------------------------------------------------------------------
# Citizen actions
# ---------------------------------------------------------------------------

def create_report(db: Session, citizen: User, data: ReportCreate) -> Report:
    """Create a new report submitted by a citizen."""
    validate_location(db, data.governorate_id, data.area_id, data.category_id)

    year = datetime.now(timezone.utc).year
    ref = generate_reference_number(db, year)

    report = Report(
        reference_number=ref,
        citizen_id=citizen.id,
        category_id=data.category_id,
        governorate_id=data.governorate_id,
        area_id=data.area_id,
        title=data.title,
        description=data.description,
        address_details=data.address_details,
        status=ReportStatus.submitted,
        priority=ReportPriority.medium,
    )
    db.add(report)
    db.flush()  # Get report.id before recording history.

     # FR-05: تسجيل القيمة الابتدائية للبلاغ بجدول السجل
    status_history = ReportStatusHistory(
        report_id=report.id,
        old_status=None,
        new_status=ReportStatus.submitted,
        changed_by_id=citizen.id,
        note="تم تقديم البلاغ بنجاح"
    )
    db.add(status_history)
    
    db.commit()
    db.refresh(report)
    return report


def get_citizen_report(db: Session, citizen: User, report_id: int) -> Report:
    """
    Return a report.
    TODO (TASK-02): Ensure citizens can only view their own reports!
    """
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report")
    return report


def update_citizen_report(db: Session, citizen: User, report_id: int, data: ReportUpdate) -> Report:
    """
    Citizens can update a report only while it is in 'submitted' status.
    They cannot change status, priority, or assigned employee.
    """
    report = get_citizen_report(db, citizen, report_id)

    if report.status != ReportStatus.submitted:
        raise BadRequestError(
            "REPORT_NOT_EDITABLE",
            "You can only edit a report while it is in 'submitted' status.",
        )

    if data.category_id is not None or data.area_id is not None:
        # Re-validate location if either location field changed.
        new_cat = data.category_id if data.category_id else report.category_id
        new_area = data.area_id if data.area_id else report.area_id
        validate_location(db, report.governorate_id, new_area, new_cat)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)

    db.commit()
    db.refresh(report)
    return report


def cancel_report(db: Session, citizen: User, report_id: int) -> Report:
    """
    A citizen can cancel their own report only when it is in a cancellable state.
    Creates a status-history entry.
    """
    report = get_citizen_report(db, citizen, report_id)

    cancellable_statuses = {ReportStatus.submitted, ReportStatus.under_review}
    if report.status not in cancellable_statuses:
        raise BadRequestError(
            "CANNOT_CANCEL",
            "You can only cancel a report that is in 'submitted' or 'under_review' status.",
        )

    report.status = ReportStatus.cancelled
    # TODO (TASK-05): Record this change in status history.

    db.commit()
    db.refresh(report)
    return report


# ---------------------------------------------------------------------------
# Employee actions
# ---------------------------------------------------------------------------

def get_report_for_employee(db: Session, employee: User, report_id: int) -> Report:
    """Return a report only if it belongs to the employee's governorate."""
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report")
    # Employees can only access reports from their governorate.
    if report.governorate_id != employee.governorate_id:
        raise PermissionDeniedError("This report is outside your governorate.")
    return report


def employee_update_status(
    db: Session, employee: User, report_id: int, data: StatusUpdateRequest
) -> Report:
    """Employee changes a report status."""
    report = get_report_for_employee(db, employee, report_id)
    
    # TODO (TASK-05): Validate transition using allowed transition table.
    report.status = data.new_status
    
    # TODO (TASK-05): Record status change.
    
    db.commit()
    db.refresh(report)
    return report


def employee_resolve_report(
    db: Session, employee: User, report_id: int, data: ResolveRequest
) -> Report:
    """
    Resolve a report.
    TODO (TASK-07): Enforce resolution rules and tracking.
    """
    report = get_report_for_employee(db, employee, report_id)

    report.resolution_summary = data.resolution_summary
    report.resolved_at = datetime.now(timezone.utc)
    report.status = ReportStatus.resolved
    
    # TODO (TASK-07): Record status change in history.
    
    db.commit()
    db.refresh(report)
    return report


def add_comment(
    db: Session,
    author: User,
    report_id: int,
    content: str,
    is_internal: bool = False,
) -> ReportComment:
    """Add a comment to a report. is_internal is only allowed for staff."""
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report")

    comment = ReportComment(
        report_id=report_id,
        author_id=author.id,
        content=content,
        is_internal=is_internal,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


# ---------------------------------------------------------------------------
# Admin actions
# ---------------------------------------------------------------------------

def admin_assign_report(
    db: Session, admin: User, report_id: int, data: AssignRequest
) -> Report:
    """
    Admin assigns an employee to a report.
    Validates that the employee is active and in the same governorate.
    """
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report")

    employee = db.get(User, data.employee_id)
    if employee is None:
        raise NotFoundError("Employee")

    if employee.role != UserRole.employee:
        raise BadRequestError("NOT_EMPLOYEE", "The selected user is not an employee.")

    if not employee.is_active:
        raise BadRequestError("INACTIVE_EMPLOYEE", "The selected employee is inactive.")

    # TODO (TASK-04): Ensure employee belongs to the same governorate.
    
    report.assigned_employee_id = employee.id
    report.status = ReportStatus.assigned
    
    # TODO (TASK-04): Record this status change in history.
    
    db.commit()
    db.refresh(report)
    return report


def admin_update_priority(
    db: Session, report_id: int, data: PriorityUpdateRequest
) -> Report:
    """Admin updates the priority of a report."""
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report")

    report.priority = data.priority
    db.commit()
    db.refresh(report)
    return report
def assign_report(db: Session, report_id: int, employee_id: int, current_user: User) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise NotFoundError("Report")

    target_employee = db.get(User, employee_id)
    if not target_employee:
        raise NotFoundError("Employee")

    report.assigned_employee_id = employee_id
    db.commit()
    db.refresh(report)
    return report   