"""Shared constants for the golf tracker."""

SURFACES = ["Tee", "Fairway", "Rough", "Sand", "Green", "Recovery"]

CLUBS = [
    "Driver",
    "3 Wood",
    "5 Wood",
    "3 Hybrid",
    "4 Hybrid",
    "5 Hybrid",
    "3 Iron",
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

TEES = ["Yellow", "White", "Red", "Blue", "Black"]

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
