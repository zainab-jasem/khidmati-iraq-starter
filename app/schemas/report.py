"""
app/schemas/report.py
Pydantic v2 schemas for reports, filters, and pagination.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.report import ReportPriority, ReportStatus
from app.schemas.category import CategoryResponse
from app.schemas.location import AreaResponse, GovernorateResponse
from app.schemas.user import UserPublic


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ReportCreate(BaseModel):
    category_id: int
    governorate_id: int
    area_id: int
    title: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=20)
    address_details: str | None = None


class ReportUpdate(BaseModel):
    """Citizens can update only these fields while the report is 'submitted'."""
    category_id: int | None = None
    area_id: int | None = None
    title: str | None = Field(default=None, min_length=5, max_length=255)
    description: str | None = Field(default=None, min_length=20)
    address_details: str | None = None


class StatusUpdateRequest(BaseModel):
    """Employee changes the report status."""
    new_status: ReportStatus
    note: str | None = None


class AssignRequest(BaseModel):
    """Admin assigns an employee to a report."""
    employee_id: int
    note: str | None = None


class PriorityUpdateRequest(BaseModel):
    """Admin changes the priority."""
    priority: ReportPriority


class ResolveRequest(BaseModel):
    """Employee resolves a report – resolution summary is required."""
    resolution_summary: str = Field(min_length=10)


# ---------------------------------------------------------------------------
# Nested author info (lighter than full UserPublic)
# ---------------------------------------------------------------------------

class AuthorInfo(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    full_name: str
    role: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    reference_number: str
    citizen_id: int
    category_id: int
    governorate_id: int
    area_id: int
    title: str
    description: str
    address_details: str | None
    status: ReportStatus
    priority: ReportPriority
    assigned_employee_id: int | None
    resolution_summary: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportDetailResponse(ReportResponse):
    """Report response with nested related objects."""
    category: CategoryResponse | None = None
    governorate: GovernorateResponse | None = None
    area: AreaResponse | None = None
    citizen: UserPublic | None = None
    assigned_employee: UserPublic | None = None


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------

class StatusHistoryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    report_id: int
    previous_status: str | None
    new_status: str
    changed_by_id: int
    note: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[Any]


# ---------------------------------------------------------------------------
# Admin filters (passed as query params)
# ---------------------------------------------------------------------------

class ReportFilterParams(BaseModel):
    status: ReportStatus | None = None
    priority: ReportPriority | None = None
    category_id: int | None = None
    governorate_id: int | None = None
    assigned_employee_id: int | None = None
    search: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
