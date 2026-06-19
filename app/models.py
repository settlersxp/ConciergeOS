#!/usr/bin/env python3
"""
SQLAlchemy ORM models for the hotel database.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String
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