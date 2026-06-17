# ConciergeOS

ConciergeOS is a hotel concierge and reservation management system built with Python and SQLite. It provides tools for generating test data, including rooms, guests with multilingual names, and reservations with realistic date/status distributions.

## Project Structure

```
HotelCMSERP/
├── create_hotel_db.py          # SQLite schema initialization
├── Generator/
│   ├── generate_names.py       # Multilingual name generator
│   ├── generate_rooms.py       # Room data generator
│   ├── populate_rooms.py       # Inserts rooms into database
│   ├── populate_reservations.py # Generates guests & reservations
│   ├── all_names.json          # Master name list (8 alphabets)
│   ├── *_names.txt             # Per-alphabet name files
│   ├── rooms.json              # Structured room data
│   └── rooms.txt               # Human-readable room list
```

## What It Does

ConciergeOS models a single-tenant hotel with three core entities:

### Rooms
Rooms are categorized by booking channel:
- **ANY** — Bookable through any channel (OTA, website, phone)
- **ON_SITE_ONLY** — Only bookable as walk-in reservations
- **STAFF_ASSIGNMENT** — Internal staff assignments (no guest bookings)

Each room has configurable check-in/check-out times. STAFF_ASSIGNMENT rooms use `00:00` for both times.

### Guests
Guest records support multilingual names across 8 writing systems:
- Latin (European languages)
- Cyrillic (Russian, Ukrainian, etc.)
- Chinese (Simplified)
- Japanese (Kanji/Kana)
- Arabic
- Devanagari (Hindi, Marathi, etc.)
- Korean (Hangul)
- Nordic (Scandinavian with special characters)

Each guest has a first name, last name, date of birth, and optional special preferences.

### Reservations
Reservations link guests to rooms with the following statuses:
- `PENDING` → `CONFIRMED` → `CHECKED_IN` → `CHECKED_OUT` (or `CANCELLED`)

The system supports 1-6 guests per reservation and tracks booking source based on room type:
- ON_SITE_ONLY → `WALK_IN`
- ANY → random of `WEBSITE`, `PHONE`, `OTA`
- STAFF_ASSIGNMENT → `INTERNAL`

## How It Works

### 1. Initialize the Database
```bash
python create_hotel_db.py [--recreate]
```
Creates `hotel.db` with the `Rooms`, `Guests`, and `Reservations` tables, including indexes for efficient date-range and guest lookups.

### 2. Generate Name Data
```bash
python Generator/generate_names.py
```
Generates ~50 names per alphabet (400 total) and saves them to individual `.txt` files and a consolidated `all_names.json`.

### 3. Generate and Populate Rooms
```bash
python Generator/generate_rooms.py    # Creates rooms.json and rooms.txt
python Generator/populate_rooms.py    # Inserts rooms into the database
```
Generates ~205 rooms across three building wings (East, North, West), each mapped to a booking channel.

### 4. Populate Guests and Reservations
```bash
python Generator/populate_reservations.py
```
Creates realistic reservation data with:
- **Weighted status distribution**: More CHECKED_IN than CHECKED_OUT or CONFIRMED
- **Name collisions**: Intentional duplicate guest names across multiple rooms (for testing deduplication logic)
- **STAFF_ASSIGNMENT handling**: All staff rooms are always CHECKED_IN with past check-in and future check-out dates
- **Booking source enforcement**: Sources are determined by room booking channel

## Database Schema

```sql
Rooms (
    room_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    allowed_booking_channel TEXT CHECK (IN ('ON_SITE_ONLY', 'STAFF_ASSIGNMENT', 'ANY')),
    checkin_time TEXT DEFAULT '15:00',
    checkout_time TEXT DEFAULT '09:00'
)

Guests (
    guest_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    date_of_birth TEXT,
    is_special_guest INTEGER DEFAULT 0,
    special_preferences TEXT
)

Reservations (
    reservation_id INTEGER PRIMARY KEY,
    room_id INTEGER REFERENCES Rooms,
    guest_id INTEGER REFERENCES Guests,
    check_in_date TEXT,
    check_out_date TEXT,
    status TEXT CHECK (IN ('PENDING', 'CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED')),
    booking_source TEXT,
    created_at TIMESTAMP
)
```

## Requirements

- Python 3.8+
- SQLite 3 (built into Python standard library)

No external dependencies are required — the entire project uses Python's standard library.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.