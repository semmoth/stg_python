"""Shared constants for the golf tracker."""

SURFACES = ["Tee", "Fairway", "Rough", "Sand", "Green", "Recovery"]

CLUBS = [
    "Driver",
    "4 Wood",
    "2 Hybrid",
    "4 Iron",
    "5 Iron",
    "6 Iron",
    "7 Iron",
    "8 Iron",
    "9 Iron",
    "PW",
    "GW",
    "SW",
    "LW",
]

TEES = ["Yellow", "Red"]

# Tee ID mapping for database
TEES_ID = {
    "Yellow": 1,
    "Red": 2,
}

CLUB_DISTANCE_ESTIMATES = {
    "Driver": 250,
    "4 Wood": 230,
    "2 Hybrid": 210,
    "4 Iron": 185,
    "5 Iron": 175,
    "6 Iron": 165,
    "7 Iron": 155,
    "8 Iron": 145,
    "9 Iron": 135,
    "PW": 125,
    "GW": 105,
    "SW": 90,
    "LW": 80,
}

# Shots from these surfaces are measured in feet (on the green)
GREEN_SURFACES = ["Green"]

# Shots categorised by phase for strokes gained
# Everything ≤ 30m from the hole (non-green, non-tee) = Short Game
SHORT_GAME_MAX_METERS = 30

# App color scheme (matching original)
COLOR_PRIMARY = "#076652"
COLOR_ACCENT = "#ffdf00"
COLOR_NEGATIVE = "firebrick"
COLOR_POSITIVE = "#076652"
