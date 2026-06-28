#!/usr/bin/env python3
"""
SQLAlchemy ORM models for the hotel database.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import BookingChannel, BookingSource, ReservationStatus


class Room(Base):
    """Maps to the Rooms table."""

    __tablename__ = "Rooms"

    room_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    allowed_booking_channel: Mapped[BookingChannel] = mapped_column(
        Enum(BookingChannel), nullable=False, server_default=BookingChannel.ANY
    )
    checkin_time: Mapped[str] = mapped_column(String, nullable=False, server_default="15:00")
    checkout_time: Mapped[str] = mapped_column(String, nullable=False, server_default="09:00")

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="room")


class Guest(Base):
    """Maps to the Guests table."""

    __tablename__ = "Guests"

    guest_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String, nullable=False)
    is_special_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    special_preferences: Mapped[str | None] = mapped_column(String, nullable=True)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="guest")


class Reservation(Base):
    """Maps to the Reservations table."""

    __tablename__ = "Reservations"

    reservation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Rooms.room_id", ondelete="RESTRICT"), nullable=False
    )
    guest_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Guests.guest_id", ondelete="RESTRICT"), nullable=False
    )
    # Stored as ISO date strings in SQLite (YYYY-MM-DD), but Python sees them as date objects.
    # SQLAlchemy's Date type handles the conversion automatically.
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), nullable=False, server_default=ReservationStatus.PENDING
    )
    booking_source: Mapped[BookingSource] = mapped_column(
        Enum(BookingSource), nullable=False, server_default=BookingSource.WALK_IN
    )
    created_at: Mapped[datetime | None] = mapped_column(default=datetime.now)

    room: Mapped[Room] = relationship(back_populates="reservations")
    guest: Mapped[Guest] = relationship(back_populates="reservations")


# ---------------------------------------------------------------------------
# Performance testing model (stored in database.db alongside hotel models)
# ---------------------------------------------------------------------------

class PerformanceTestResult(Base):
    """Maps to the test_results table in database.db.

    This model shares the same `Base` as hotel models and uses the same
    engine via `app.db`.
    """

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_uuid: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    friendly_name: Mapped[str | None] = mapped_column(String, nullable=True, server_default="")
    batch_type: Mapped[str] = mapped_column(String, nullable=False)
    request_index: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vllm_version: Mapped[str | None] = mapped_column(String, nullable=True)
    thinking_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    user_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    response_format: Mapped[str | None] = mapped_column(String, nullable=True)
    json_malformed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_sent_time: Mapped[str | None] = mapped_column(String, nullable=True)
    response_received_time: Mapped[str | None] = mapped_column(String, nullable=True)
    response_content: Mapped[str | None] = mapped_column(String, nullable=True)
    valid_response: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    identifier: Mapped[str | None] = mapped_column(String, nullable=True)


# ---------------------------------------------------------------------------
# Prompt versioning model (stored in hotel.db)
# ---------------------------------------------------------------------------

class PromptVersion(Base):
    """Maps to the prompt_versions table.

    Each prompt is identified by a unique {prompt_id, version} pair and stores
    the prompt in 4 structured fields that are combined at runtime.
    """

    __tablename__ = "PromptVersions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    restrictions: Mapped[str] = mapped_column(Text, nullable=False)
    output_structure: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )


# ---------------------------------------------------------------------------
# Prompt Groups models (stored in hotel.db)
# ---------------------------------------------------------------------------

class PromptGroup(Base):
    """A named, ordered collection of prompt+version pairs forming a chain."""

    __tablename__ = "PromptGroup"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["PromptGroupItem"]] = relationship(back_populates="group", cascade="all, delete-orphan", order_by="PromptGroupItem.position")
    schedules: Mapped[list["PromptGroupSchedule"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    results: Mapped[list["PromptGroupResult"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class PromptGroupItem(Base):
    """Single prompt+version entry within a PromptGroup, with ordering."""

    __tablename__ = "PromptGroupItem"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)

    group: Mapped["PromptGroup"] = relationship(back_populates="items")


class PromptGroupSchedule(Base):
    """Scheduled execution time for a PromptGroup chain."""

    __tablename__ = "PromptGroupSchedule"

    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped["PromptGroup"] = relationship(back_populates="schedules")


class PromptGroupResult(Base):
    """Execution result record for a PromptGroup chain run."""

    __tablename__ = "PromptGroupResult"

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    result_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    group: Mapped["PromptGroup"] = relationship(back_populates="results")
