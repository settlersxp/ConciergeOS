#!/usr/bin/env python3
"""
Generate hotel room numbers across 3 wings (East, North, West) with variable floors.

Room format: {Side}{Floor}{Room} {Wing}
Example: L0001 E  (Left side, Floor 00, Room 01, East wing)
         R0305 N  (Right side, Floor 03, Room 05, North wing)

Hotel layout:
  - East:  floors 00–05  (6 floors)
  - North: floors 00–10  (11 floors)
  - West:  floors 00–15  (16 floors)

Rooms per side per floor vary deterministically to ensure 200+ total rooms.
"""

import os
import json

# Define the Generator directory (same as this script)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Wing configuration: (floor_count, min_rooms_per_side, max_rooms_per_side)
# Floors start at 0 (ground floor included)
wings_config = {
    "E": {
        "name": "East",
        "floors": 6,       # floors 00–05
        "min_rooms_per_side": 3,
        "max_rooms_per_side": 5,
    },
    "N": {
        "name": "North",
        "floors": 11,      # floors 00–10
        "min_rooms_per_side": 3,
        "max_rooms_per_side": 4,
    },
    "W": {
        "name": "West",
        "floors": 16,      # floors 00–15
        "min_rooms_per_side": 2,
        "max_rooms_per_side": 3,
    },
}


def rooms_per_side(floor: int, wing_code: str) -> int:
    """
    Deterministically compute the number of rooms on one side of a given floor.

    Uses a modulo-based pattern so the result is reproducible and varies
    between min_rooms_per_side and max_rooms_per_side.
    """
    cfg = wings_config[wing_code]
    min_r = cfg["min_rooms_per_side"]
    max_r = cfg["max_rooms_per_side"]

    if min_r == max_r:
        return min_r

    # Cycle through the range based on floor number
    spread = max_r - min_r + 1
    return min_r + (floor % spread)


def generate_rooms() -> list:
    """Generate all room numbers for the hotel."""
    rooms = []

    for wing_code, cfg in wings_config.items():
        for floor in range(cfg["floors"]):
            left_count = rooms_per_side(floor, wing_code)
            right_count = rooms_per_side(floor + 1, wing_code)  # offset for variation

            # Generate Left-side rooms: L{floor:02d}{room:02d}
            for room_num in range(1, left_count + 1):
                room_number = f"L{floor:02d}{room_num:02d} {wing_code}"
                rooms.append({
                    "room_number": room_number,
                    "side": "L",
                    "floor": floor,
                    "room_seq": room_num,
                    "wing_code": wing_code,
                    "wing_name": cfg["name"],
                })

            # Generate Right-side rooms: R{floor:02d}{room:02d}
            for room_num in range(1, right_count + 1):
                room_number = f"R{floor:02d}{room_num:02d} {wing_code}"
                rooms.append({
                    "room_number": room_number,
                    "side": "R",
                    "floor": floor,
                    "room_seq": room_num,
                    "wing_code": wing_code,
                    "wing_name": cfg["name"],
                })

    return rooms


def save_rooms(rooms: list):
    """Save rooms to a txt file and a JSON file."""
    os.makedirs(BASE_DIR, exist_ok=True)

    # Save plain text file (one room per line)
    txt_path = os.path.join(BASE_DIR, "rooms.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        for room in rooms:
            f.write(room["room_number"] + '\n')
    print(f"Saved {len(rooms)} rooms to {txt_path}")

    # Save structured JSON file
    json_path = os.path.join(BASE_DIR, "rooms.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(rooms, f, ensure_ascii=False, indent=2)
    print(f"Saved structured data to {json_path}")

    # Print summary per wing
    print("\n--- Room Summary ---")
    for wing_code in ["E", "N", "W"]:
        wing_rooms = [r for r in rooms if r["wing_code"] == wing_code]
        print(f"  {wings_config[wing_code]['name']} ({wing_code}): {len(wing_rooms)} rooms")

    print(f"\nTotal rooms generated: {len(rooms)}")


if __name__ == "__main__":
    all_rooms = generate_rooms()
    save_rooms(all_rooms)
    print("\nDone! Room files created in Generator folder.")