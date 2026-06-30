"""add hotel tables: rooms, guests, reservations, test_results

Revision ID: d3f04a295bc8
Revises: dae900574783
Create Date: 2026-06-27 08:38:23.689091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.enums import BookingChannel, BookingSource, ReservationStatus


# revision identifiers, used by Alembic.
revision: str = 'd3f04a295bc8'
down_revision: Union[str, None] = 'dae900574783'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hotel tables: Rooms, Guests, Reservations, test_results."""
    # ### Commands manually written for SQLite compatibility ###

    # --- Rooms table ---
    op.create_table(
        'Rooms',
        sa.Column('room_id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column(
            'allowed_booking_channel',
            sa.Enum(BookingChannel),
            nullable=False,
            server_default='ANY',
        ),
        sa.Column('checkin_time', sa.String(), nullable=False, server_default='15:00'),
        sa.Column('checkout_time', sa.String(), nullable=False, server_default='09:00'),
        sa.UniqueConstraint('name', name='uq_rooms_name'),
    )

    # --- Guests table ---
    op.create_table(
        'Guests',
        sa.Column('guest_id', sa.Integer(), primary_key=True),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('date_of_birth', sa.String(), nullable=False),
        sa.Column('is_special_guest', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('special_preferences', sa.String(), nullable=True),
    )

    # --- Reservations table ---
    op.create_table(
        'Reservations',
        sa.Column('reservation_id', sa.Integer(), primary_key=True),
        sa.Column(
            'room_id',
            sa.Integer(),
            sa.ForeignKey('Rooms.room_id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'guest_id',
            sa.Integer(),
            sa.ForeignKey('Guests.guest_id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('check_in_date', sa.Date(), nullable=False),
        sa.Column('check_out_date', sa.Date(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(ReservationStatus),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column(
            'booking_source',
            sa.Enum(BookingSource),
            nullable=False,
            server_default='WALK_IN',
        ),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # --- test_results table ---
    op.create_table(
        'test_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.Integer(), nullable=True),
        sa.Column('batch_uuid', sa.String(), nullable=False, server_default=''),
        sa.Column('friendly_name', sa.String(), nullable=True, server_default=''),
        sa.Column('batch_type', sa.String(), nullable=False),
        sa.Column('request_index', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=True),
        sa.Column('context_length', sa.Integer(), nullable=True),
        sa.Column('vllm_version', sa.String(), nullable=True),
        sa.Column('thinking_enabled', sa.Boolean(), nullable=True),
        sa.Column('system_prompt', sa.String(), nullable=True),
        sa.Column('user_prompt', sa.String(), nullable=True),
        sa.Column('response_format', sa.String(), nullable=True),
        sa.Column('json_malformed', sa.Boolean(), nullable=True),
        sa.Column('response_length', sa.Integer(), nullable=True),
        sa.Column('request_sent_time', sa.String(), nullable=True),
        sa.Column('response_received_time', sa.String(), nullable=True),
        sa.Column('response_content', sa.String(), nullable=True),
        sa.Column('valid_response', sa.Boolean(), nullable=True),
        sa.Column('identifier', sa.String(), nullable=True),
    )

    # --- Indexes ---
    op.create_index(
        'idx_reservations_room_dates',
        'Reservations',
        ['room_id', 'check_in_date', 'check_out_date', 'status'],
    )
    op.create_index('idx_reservations_guest', 'Reservations', ['guest_id'])
    # ### end manual commands ###


def downgrade() -> None:
    """Remove hotel tables."""
    op.drop_index('idx_reservations_guest', table_name='Reservations')
    op.drop_index('idx_reservations_room_dates', table_name='Reservations')
    op.drop_table('test_results')
    op.drop_table('Reservations')
    op.drop_table('Guests')
    op.drop_table('Rooms')
    # Drop enum types (SQLite doesn't truly support enums, but Alembic tracks them)
    sa.Enum(*BookingSource.__members__.values(), name='bookingsource').drop(op.get_bind(), checkfirst=True)
    sa.Enum(*ReservationStatus.__members__.values(), name='reservationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(*BookingChannel.__members__.values(), name='bookingchannel').drop(op.get_bind(), checkfirst=True)