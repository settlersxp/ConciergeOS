#!/usr/bin/env python3
"""
Pydantic schemas for API request/response validation.
"""

from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List

from pydantic import BaseModel, Field

from app.enums import BookingSource, ReservationStatus

if TYPE_CHECKING:
    from app.models import Reservation


# ---------------------------------------------------------------------------
# Reservation schemas
# ---------------------------------------------------------------------------

class ReservationResponse(BaseModel):
    """Single reservation output (includes joined room/guest data)."""

    reservation_id: int
    room_id: int
    room_name: str
    guest_id: int
    first_name: str
    last_name: str
    check_in_date: date
    check_out_date: date
    status: ReservationStatus
    booking_source: BookingSource

    @classmethod
    def from_orm_reservation(
        cls,
        reservation: "Reservation",
    ) -> "ReservationResponse":
        """Create a ReservationResponse directly from an ORM Reservation object (room/guest must be loaded)."""
        return cls(
            reservation_id=reservation.reservation_id,
            room_id=reservation.room_id,
            room_name=reservation.room.name,
            guest_id=reservation.guest_id,
            first_name=reservation.guest.first_name,
            last_name=reservation.guest.last_name,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            status=reservation.status,
            booking_source=reservation.booking_source,
        )


# ---------------------------------------------------------------------------
# Error schemas
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Detected error on a reservation."""

    reservation_id: int
    room_name: str
    room_id: int
    guest_name: str
    check_in_date: date
    check_out_date: date
    status: ReservationStatus
    error_type: str
    description: str


# ---------------------------------------------------------------------------
# Summary schema
# ---------------------------------------------------------------------------

class ReservationsSummary(BaseModel):
    """Top-level dashboard payload."""

    rooms: Dict[str, List[ReservationResponse]]
    errors: List[ErrorResponse]


# ---------------------------------------------------------------------------
# Shift reservation schemas
# ---------------------------------------------------------------------------

class ShiftRequest(BaseModel):
    """Request body for shifting reservation dates."""

    days: int = Field(
        default=1,
        description="Number of days to shift (positive = forward, negative = backward)"
    )


class ShiftSampleEntry(BaseModel):
    check_in: str
    check_out: str


class ShiftResponse(BaseModel):
    """Response from the shift-reservations endpoint."""

    ok: bool
    shifted: int | None = None
    days: int | None = None
    message: str | None = None
    error: str | None = None
    before: List[ShiftSampleEntry] = []
    after: List[ShiftSampleEntry] = []


# ---------------------------------------------------------------------------
# Guest search schemas
# ---------------------------------------------------------------------------

class GuestSearchRequest(BaseModel):
    """Request body for searching a guest by name."""

    customer_name: str = Field(..., description="Full or partial name of the customer to search for")
    prompt_id: str = Field(default="guest-search", description="Prompt ID to use for the LLM query")
    version: int | None = Field(default=None, description="Prompt version (uses default if None)")
    runtime_variables: Dict[str, str] = Field(default_factory=dict, description="Runtime variables for {table.field} placeholders in the user_prompt")


class GuestSearchResponse(BaseModel):
    """Response from the guest-search endpoint."""

    query: str
    llm_response: str
    cached: bool = False
    """Indicates whether the response was served from cache (True) or generated fresh (False)."""


class NameExtractionResponse(BaseModel):
    """Response from the extract-name endpoint (multimodal name extraction)."""

    extracted_name: str
    source: str  # "image" or "audio"


# ---------------------------------------------------------------------------
# Prompt versioning schemas
# ---------------------------------------------------------------------------

class PromptVersionSchema(BaseModel):
    """Output schema for a single prompt version."""

    id: int
    prompt_id: str
    version: int
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    is_default: bool
    metadata: dict | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PromptSummarySchema(BaseModel):
    """Summary for listing prompt IDs."""

    prompt_id: str
    default_version: int
    version_count: int
    name: str


class CreatePromptRequest(BaseModel):
    """Request body for creating a new prompt (v1)."""

    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    metadata: dict | None = None


class UpdatePromptRequest(BaseModel):
    """Request body for updating an existing prompt version."""

    name: str | None = None
    intention: str | None = None
    restrictions: str | None = None
    output_structure: str | None = None
    user_prompt_template: str | None = None
    metadata: dict | None = None


class DuplicatePromptRequest(BaseModel):
    """Request body for duplicating a prompt version."""

    name: str | None = None


class SetDefaultRequest(BaseModel):
    """Request body for setting the default prompt version."""

    version: int


# ---------------------------------------------------------------------------
# Performance testing schemas
# ---------------------------------------------------------------------------

class PerformanceTestRequest(BaseModel):
    """Request body for running performance tests."""

    customer_name: str = Field(default="عائشة إبراهيم")
    vllm_url: str = Field(default="http://10.0.0.227:8000/v1")
    models_endpoint: str = Field(default="http://10.0.0.227:8000/v1/models")
    sequential_batch_size: int = Field(default=5)
    concurrent_batch_size: int = Field(default=8)
    test_mode: str = Field(default="single")
    friendly_name: str = Field(default="")
    model_name: str = Field(default="")
    vllm_version: str = Field(default="")
    thinking_enabled: bool = Field(default=False)
    user_prompt: str = Field(default="")
    expected_response_format: str = Field(default="auto")
    data_format: str = Field(default="csv")
    batch_uuid: str = Field(default="")
    # Optional: resolve user_prompt from a prompt version
    prompt_id: str | None = Field(default=None)
    prompt_version: int | None = Field(default=None)
    # Runtime variables for {table.field} placeholders in the user_prompt
    runtime_variables: Dict[str, str] = Field(default_factory=dict)


class UpdateValidResponseRequest(BaseModel):
    """Request body for patching the valid_response flag."""

    valid_response: bool


class PerformanceTestResultSchema(BaseModel):
    """Single performance test result row."""

    id: int
    run_id: int | None = None
    batch_uuid: str = ""
    friendly_name: str | None = None
    batch_type: str
    request_index: int
    model_name: str | None = None
    context_length: int | None = None
    vllm_version: str | None = None
    thinking_enabled: bool | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    response_format: str | None = None
    json_malformed: bool | None = None
    response_length: int | None = None
    request_sent_time: str | None = None
    response_received_time: str | None = None
    response_content: str | None = None
    valid_response: bool | None = None
    identifier: str | None = None

    model_config = {"from_attributes": True}


class PerformanceTestBatchSchema(BaseModel):
    """Summary of a unique test batch."""

    batch_uuid: str
    friendly_name: str | None = None
    total_requests: int = 0
    first_run_time: str | None = None


class TestGuestSchema(BaseModel):
    """Performance test guest information."""

    guest_id: int
    first_name: str
    last_name: str
    full_name: str
    reservation_count: int = 0


class SetupGuestsResponse(BaseModel):
    """Response from the setup-guests endpoint."""

    ok: bool
    guests: List[Dict[str, Any]] = []
    total: int = 0
    error: str | None = None


class GenerateXmlResponse(BaseModel):
    """Response from the generate-xml endpoint."""

    ok: bool
    path: str | None = None
    size_bytes: int | None = None
    error: str | None = None


class GenerateAllResponse(BaseModel):
    """Response from the generate-all endpoint."""

    ok: bool
    files: Dict[str, Dict[str, Any]] = {}
    error: str | None = None


class DeleteBatchResponse(BaseModel):
    """Response from the delete-batch endpoint."""

    ok: bool
    deleted_count: int = 0
    batch_uuid: str = ""
    error: str | None = None


class UpdateValidResponseResponse(BaseModel):
    """Response from the update-valid-response endpoint."""

    ok: bool = True
    id: int | None = None
    valid_response: bool | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Validation schemas
# ---------------------------------------------------------------------------

class ValidateGuestsRequest(BaseModel):
    """Request body for validating batch results against test guests."""

    batch_uuid: str
    guest_ids: List[int] | None = None
    result_ids: List[int] | None = None


class SingleGuestValidation(BaseModel):
    """Validation result for a single guest-response pair."""

    guest_id: int
    guest_name: str
    result_id: int | None = None
    is_match: bool | None = None
    """LLM's suggestion: True=Match, False=Mismatch, None=Error"""
    valid_response: bool | None = None
    """Human's previous validation flag from the database (null = not reviewed)"""
    llm_reasoning: str | None = None
    ground_truth: str | None = None
    llm_response_content: str | None = None


class ValidateGuestsResponse(BaseModel):
    """Response from the validate-guests endpoint."""

    ok: bool = True
    results: List[SingleGuestValidation] = []
    summary: Dict[str, Any] | None = None
    error: str | None = None


class UpdateIdentifierRequest(BaseModel):
    """Request body for updating the identifier on a test result."""

    identifier: str


class UpdateIdentifierResponse(BaseModel):
    """Response from the update-identifier endpoint."""

    ok: bool = True
    id: int | None = None
    identifier: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Guest detail schemas (expandable guest rows)
# ---------------------------------------------------------------------------

class ReservationDetailSchema(BaseModel):
    """Detailed reservation information for guest detail view."""

    reservation_id: int
    room_id: int
    room_name: str
    check_in_date: date
    check_out_date: date
    status: ReservationStatus
    booking_source: BookingSource
    created_at: str | None = None

    model_config = {"from_attributes": True}


class GuestDetailSchema(BaseModel):
    """Detailed guest information including all reservations."""

    guest_id: int
    first_name: str
    last_name: str
    date_of_birth: str | None = None
    is_special_guest: bool | None = None
    special_preferences: str | None = None
    reservations: List[ReservationDetailSchema] = []


# ---------------------------------------------------------------------------
# Prompt Group schemas
# ---------------------------------------------------------------------------

class PromptGroupItemSchema(BaseModel):
    """Single prompt+version entry within a group."""

    item_id: int
    group_id: int
    position: int
    prompt_id: str
    prompt_version: int

    model_config = {"from_attributes": True}


class PromptGroupItemCreate(BaseModel):
    """Request body for adding a prompt+version to a group."""

    position: int
    prompt_id: str
    prompt_version: int


class PromptGroupScheduleSchema(BaseModel):
    """Schedule record for a group."""

    schedule_id: int
    group_id: int
    run_at: str
    schedule_type: str = "daily"
    active: bool
    created_at: str

    model_config = {"from_attributes": True}


class PromptGroupScheduleCreate(BaseModel):
    """Request body to schedule a group execution."""

    run_at: str  # ISO 8601 datetime string
    schedule_type: str = "daily"  # "daily", "weekly", or "none"


class PromptGroupResultSchema(BaseModel):
    """Execution result record."""

    result_id: int
    group_id: int
    executed_at: str
    scheduled: bool
    result_file: str | None = None
    status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}


class PromptGroupSchema(BaseModel):
    """Output schema for a prompt group (includes items, schedules, results)."""

    group_id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str
    items: List[PromptGroupItemSchema] = []
    schedules: List[PromptGroupScheduleSchema] = []
    results: List[PromptGroupResultSchema] = []

    model_config = {"from_attributes": True}


class CreateGroupRequest(BaseModel):
    """Request body for creating a new prompt group."""

    name: str
    description: str | None = None
    items: List[PromptGroupItemCreate] = []


class UpdateGroupRequest(BaseModel):
    """Request body for updating a group (name, description, items order)."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    items: List[PromptGroupItemCreate] | None = None
