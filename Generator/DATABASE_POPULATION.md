# Database Population Guide

This document provides a comprehensive guide for populating a fresh ConciergeOS database. It covers all scripts in the Generator folder organized into three sections: Data Generation, Database Population, and Errors Setup.

## Prerequisites

Before running any Generator scripts:

1. **Database must be initialized**: Run `python create_hotel_db.py [--recreate]` first
2. **Name data must exist**: Run `python Generator/generate_names.py` to generate `Generator/all_names.json`

---

## Section 1: Data Generation

Generates raw name data and room definitions as JSON/text files. These files serve as input for the database population step.

### 1.1 Name Generation

**Script**: `generate_names.py`

**Command**:
```bash
python Generator/generate_names.py
```

**Output**: `Generator/all_names.json`

**Description**: 
- Generates ~50 names per alphabet (400 total) across 8 writing systems
- Writing systems: Latin, Cyrillic, Chinese, Japanese, Arabic, Devanagari, Korean, Nordic
- Names support multilingual guest search functionality

**Dependencies**: None (standalone script)

---

### 1.2 Room Generation

**Script**: `generate_rooms.py`

**Command**:
```bash
python Generator/generate_rooms.py
```

**Output**: `Generator/rooms.json`, `Generator/rooms.txt`

**Description**: 
- Creates room definitions (~205 rooms across 3 wings)
- Rooms are categorized by booking channel:
  - `ANY` — Can be booked via any channel
  - `ON_SITE_ONLY` — Walk-in guests only
  - `STAFF_ASSIGNMENT` — Staff-only assignments (uses `00:00` for both check-in/check-out times)
- Each room has configurable check-in and check-out times

**Dependencies**: None (standalone script)

---

## Section 2: Database Population

Inserts generated data into the SQLite database (`database.db`).

### 2.1 Populate Rooms

**Script**: `populate_rooms.py`

**Command**:
```bash
python Generator/populate_rooms.py
```

**Input**: `Generator/rooms.json`

**Description**:
- Reads room definitions from `rooms.json`
- Inserts rooms into the `Rooms` table
- Each room gets: `room_id`, `name`, `allowed_booking_channel`, `check_in_time`, `check_out_time`

**Dependencies**: Requires `rooms.json` from Section 1.2

---

### 2.2 Populate Guests and Reservations

**Script**: `populate_reservations.py`

**Command**:
```bash
python Generator/populate_reservations.py
```

**Input**: `Generator/all_names.json`

**Description**:
- Creates realistic guest and reservation data
- Clears existing Guests and Reservations data (allows re-running)
- Assigns 1-6 guests per reservation

#### Date/Status Buckets

For non-STAFF_ASSIGNMENT rooms, reservations are distributed across weighted buckets:

| Bucket | Check-in Date | Check-out Date | Status | Weight |
|--------|--------------|----------------|--------|--------|
| 1 | Past (7-30 days ago) | Today | `CHECKED_IN` | 1 |
| 2 | Past (7-30 days ago) | Future (1-7 days) | `CHECKED_IN` | 3 |
| 3 | Past (14-60 days ago) | Past (2-10 days ago) | `CHECKED_OUT` | 1 |
| 4 | Today | Future (1-7 days) | `CONFIRMED` | 1 |

STAFF_ASSIGNMENT rooms always use Bucket 2 (CHECKED_IN with past check-in, future checkout).

#### Name Collisions

The script creates controlled name collision scenarios for testing:
- **5 CHECKED_OUT collisions**: Same guest name across different rooms with overlapping past dates
- **5 CHECKED_IN collisions**: Same guest name across different rooms with overlapping dates

This creates scenarios where the same `(first_name, last_name)` pair appears in 2+ different rooms.

#### Booking Source Rules

The booking source is determined by the room's `allowed_booking_channel`:

| Room Channel | Booking Source |
|--------------|----------------|
| `ON_SITE_ONLY` | `WALK_IN` |
| `ANY` | Random of `WEBSITE`, `PHONE`, `OTA` |
| `STAFF_ASSIGNMENT` | `INTERNAL` |

#### Guest Data Generation

Each guest record includes:
- `first_name`, `last_name` — from the generated name pool
- `date_of_birth` — random date (18-80 years old from today)
- `is_special_guest` — set to 0 (false) by default
- `special_preferences` — NULL by default

#### Summary Output

On completion, the script prints:
- Total guests inserted
- Total reservation rows (normal + collisions)
- Rooms with reservations count
- Status distribution for normal reservations
- Name collision verification details

---

### 2.3 (Optional) Setup Performance Test Guests

**Script**: `setup_performance_guests.py`

**Command**:
```bash
python Generator/setup_performance_guests.py
```

**Description**:
- Creates 13 dedicated test guests
- Each guest has 4 reservations
- Used for LLM performance benchmarking

**Dependencies**: None (can run independently after database initialization)

---

## Section 3: Errors Setup

Injects controlled errors into existing reservations for testing error detection features.

### 3.1 Inject Controlled Errors

**Script**: `setup_errors.py`

**Command**:
```bash
python Generator/setup_errors.py
```

**Output**: `Generator/erroneous_reservations.json`

**Description**:
1. Identifies reservations with name collisions (same first+last name across 2+ rooms)
2. Selects 4 collision reservations and introduces controlled errors
3. Persists affected reservation IDs to `erroneous_reservations.json`

#### Error Type A: Erroneous Status (2 reservations)

| # | Reservation Type | Original Status | New Status | Description |
|---|-----------------|-----------------|------------|-------------|
| 1 | CHECKED_IN (past check-in, future checkout) | `CHECKED_IN` | `CANCELLED` | Erroneous cancellation |
| 2 | CONFIRMED (today check-in, future checkout) | `CONFIRMED` | `CHECKED_OUT` | Erroneous status |

#### Error Type B: Unsynchronized Dates (2 reservations)

| # | Reservation Type | Field Modified | Original | New | Description |
|---|-----------------|----------------|----------|-----|-------------|
| 3 | CHECKED_IN | `check_out_date` | Future date | Past date (3 days after check-in) | Guest appears checked out with future checkout |
| 4 | CHECKED_OUT | `check_in_date` | Past date | Future date (+5 days) | Guest appears checked in with future check-in |

#### Exclusion List

The script respects the `EXCLUDED_RESERVATION_IDS` list defined in the script file. Reservations with IDs in this list will NEVER be turned into erroneous data. Edit the script to add IDs:

```python
EXCLUDED_RESERVATION_IDS: List[int] = [
    # Add IDs here, e.g.: 1, 42, 99
]
```

#### Console Output

The script prints:
- Before/after state for each affected reservation
- Summary of all erroneous reservation IDs
- Number of name collisions found in the database

---

## Complete Setup Sequence

For a fresh database, run these commands in order:

```bash
# 1. Initialize the database
python create_hotel_db.py

# 2. Generate name data
python Generator/generate_names.py

# 3. Generate and populate rooms
python Generator/generate_rooms.py
python Generator/populate_rooms.py

# 4. Populate guests and reservations
python Generator/populate_reservations.py

# 5. (Optional) Setup performance test guests
python Generator/setup_performance_guests.py

# 6. Inject errors for testing
python Generator/setup_errors.py
```

---

## Utility Scripts

### Shift Reservation Dates

**Script**: `shift_reservations.py`

**Commands**:
```bash
python Generator/shift_reservations.py              # Shift by 1 day (default)
python Generator/shift_reservations.py --days 3     # Shift forward by 3 days
python Generator/shift_reservations.py --days -2    # Shift backward by 2 days
```

**Description**: Shifts all reservation dates forward or backward by N days. Useful for maintaining realistic date ranges over time.

---

## Data Flow Diagram

```
generate_names.py          →  all_names.json
generate_rooms.py          →  rooms.json, rooms.txt
                                ↓
populate_rooms.py          →  Rooms table (database.db)
populate_reservations.py   →  Guests + Reservations tables (database.db)
                                ↓
setup_performance_guests.py →  Additional test guests + reservations
setup_errors.py            →  Modified reservations (erroneous)
                                ↓
erroneous_reservations.json (persisted IDs)
```

---

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `Names file not found: all_names.json` | `generate_names.py` not run | Run `python Generator/generate_names.py` first |
| `Database not found at database.db` | Database not initialized | Run `python create_hotel_db.py` first |
| `No rooms found in the database` | Rooms not populated | Run `python Generator/populate_rooms.py` first |
| `Not enough collision reservations` | Not enough data for error injection | Run `populate_reservations.py` again or increase data |
| `EXCLUDED_RESERVATION_IDS` blocking errors | IDs in exclusion list | Edit `EXCLUDED_RESERVATION_IDS` in `setup_errors.py` |