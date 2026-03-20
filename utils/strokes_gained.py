"""
Strokes gained calculations — ported from functions_test_offline.R.

Key formula per shot:
    SG = expected_strokes(position_before) - expected_strokes(position_after) - 1
For the final shot (holed): expected_strokes(position_after) = 0
"""
import os
import pandas as pd
import numpy as np
from functools import lru_cache

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

FEET_PER_METER = 3.28084


@lru_cache(maxsize=1)
def _load_swing() -> pd.DataFrame:
    path = os.path.join(_DATA_DIR, "distance_sg.csv")
    df = pd.read_csv(path, sep=";", decimal=",")
    df.columns = df.columns.str.strip()
    df.rename(columns={df.columns[0]: "Meter"}, inplace=True)
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@lru_cache(maxsize=1)
def _load_putting() -> pd.DataFrame:
    path = os.path.join(_DATA_DIR, "proputting3.csv")
    df = pd.read_csv(path, sep=";", decimal=",")
    df.columns = df.columns.str.strip()
    df.rename(columns={df.columns[0]: "Feet", df.columns[1]: "Oneputt", df.columns[2]: "Threeputt"}, inplace=True)
    for col in ["Oneputt", "Threeputt"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Expected putts from distance (same formula as R)
    df["Putting"] = (
        1 * df["Oneputt"]
        + 3 * df["Threeputt"]
        + 2 * (1 - df["Oneputt"] - df["Threeputt"])
    ).round(2)
    return df


def _round_distance(distance: float, surface: str) -> float:
    """Mirror R logic: distances > 300m are rounded to nearest 10."""
    d = float(distance)
    if surface != "Green" and d > 300:
        return round(d / 10) * 10
    return d


def _lookup_swing(surface: str, distance_m: float) -> float | None:
    swing = _load_swing()
    d = int(round(_round_distance(distance_m, surface)))
    row = swing[swing["Meter"] == d]
    if row.empty:
        # Find closest available distance
        idx = (swing["Meter"] - d).abs().idxmin()
        row = swing.iloc[[idx]]
    col_map = {
        "Tee": "Tee",
        "Fairway": "Fairway",
        "Rough": "Rough",
        "Sand": "Sand",
        "Recovery": "Recovery",
    }
    col = col_map.get(surface)
    if col is None or col not in row.columns:
        return None
    val = row[col].values[0]
    return float(val) if not pd.isna(val) else None


def _lookup_putting(distance_feet: float) -> float | None:
    putting = _load_putting()
    d = int(round(float(distance_feet)))
    d = max(1, min(d, putting["Feet"].max()))
    row = putting[putting["Feet"] == d]
    if row.empty:
        idx = (putting["Feet"] - d).abs().idxmin()
        row = putting.iloc[[idx]]
    val = row["Putting"].values[0]
    return float(val) if not pd.isna(val) else None


def expected_strokes(surface: str, distance: float, distance_unit: str = "meters") -> float | None:
    """
    Return expected strokes from a given position.
    surface: one of Tee / Fairway / Rough / Sand / Recovery / Green
    distance: in meters for non-green, feet for Green
    distance_unit: 'meters' or 'feet' (used for Green shots entered in feet)
    """
    if surface == "Green":
        feet = distance if distance_unit == "feet" else distance * FEET_PER_METER
        return _lookup_putting(feet)
    else:
        meters = distance if distance_unit == "meters" else distance / FEET_PER_METER
        return _lookup_swing(surface, meters)


def shot_strokes_gained(
    surface_before: str,
    dist_before: float,
    unit_before: str,
    surface_after: str | None,
    dist_after: float | None,
    unit_after: str | None,
    holed: bool,
) -> float | None:
    """
    Strokes gained for one shot.
    holed=True means the shot was holed (expected strokes after = 0).
    """
    se_start = expected_strokes(surface_before, dist_before, unit_before)
    if se_start is None:
        return None
    if holed:
        se_end = 0.0
    else:
        if surface_after is None or dist_after is None:
            return None
        se_end = expected_strokes(surface_after, dist_after, unit_after)
        if se_end is None:
            return None
    return round(se_start - se_end - 1, 4)


def _shot_phase(surface: str, distance_m: float) -> str:
    """Categorise a shot into a strokes gained phase."""
    if surface == "Tee":
        return "tee"
    if surface == "Green":
        return "putting"
    if distance_m <= 30:
        return "short_game"
    return "approach"


# ── Round-level calculations ───────────────────────────────────────────────────

def calculate_round_stats(shots: list[dict], holes: list[dict]) -> dict:
    """
    Given shots (from DB) and holes (course data), compute full round stats.

    shots: list of dicts with keys:
        hole_number, shot_number, surface, distance_to_hole, distance_unit,
        shot_distance, holed

    holes: list of dicts with keys:
        hole_number, par, distance_meters

    Returns a dict with all stats needed for the dashboard.
    """
    if not shots:
        return {}

    hole_map = {h["hole_number"]: h for h in holes}
    shots_by_hole: dict[int, list[dict]] = {}
    for s in shots:
        hn = int(s["hole_number"])
        shots_by_hole.setdefault(hn, []).append(s)

    # ── Per-hole results ───────────────────────────────────────────────────────
    scorecard = []
    stg_tee_list, stg_app_list, stg_sg_list, stg_putt_list = [], [], [], []
    fir_results, gir_results = [], []
    driving_distances = []

    for hole_num in sorted(shots_by_hole.keys()):
        hole_shots = sorted(shots_by_hole[hole_num], key=lambda x: int(x["shot_number"]))
        hole_info = hole_map.get(hole_num, {})
        par = int(hole_info.get("par", 4))
        score = len(hole_shots)

        # Per-shot SG
        hole_stg = {"tee": 0.0, "approach": 0.0, "short_game": 0.0, "putting": 0.0}
        for i, shot in enumerate(hole_shots):
            surface = shot["surface"]
            dist = float(shot["distance_to_hole"]) if shot["distance_to_hole"] else 0
            unit = shot["distance_unit"] or "meters"
            holed = bool(int(shot["holed"])) if shot["holed"] is not None else False

            if i + 1 < len(hole_shots):
                next_shot = hole_shots[i + 1]
                next_surface = next_shot["surface"]
                next_dist = float(next_shot["distance_to_hole"]) if next_shot["distance_to_hole"] else 0
                next_unit = next_shot["distance_unit"] or "meters"
                sg = shot_strokes_gained(surface, dist, unit, next_surface, next_dist, next_unit, False)
            else:
                sg = shot_strokes_gained(surface, dist, unit, None, None, None, True)

            if sg is not None:
                dist_m = dist if unit == "meters" else dist / FEET_PER_METER
                phase = _shot_phase(surface, dist_m)
                hole_stg[phase] += sg

        stg_tee_list.append(hole_stg["tee"])
        stg_app_list.append(hole_stg["approach"])
        stg_sg_list.append(hole_stg["short_game"])
        stg_putt_list.append(hole_stg["putting"])

        # Driving distance (shot 1, if shot_distance recorded)
        tee_shot = hole_shots[0]
        if tee_shot.get("shot_distance"):
            try:
                driving_distances.append(float(tee_shot["shot_distance"]))
            except (ValueError, TypeError):
                pass

        # FIR: par 4 and 5 only — shot 2 surface is Fairway
        if par >= 4 and len(hole_shots) >= 2:
            fir_results.append(hole_shots[1]["surface"] == "Fairway")

        # GIR: on green in par - 2 or fewer shots
        gir_threshold = par - 2
        gir = any(
            int(s["shot_number"]) <= gir_threshold and s["surface"] == "Green"
            for s in hole_shots
        )
        gir_results.append(gir)

        # Putts on this hole
        putts = sum(1 for s in hole_shots if s["surface"] == "Green")

        scorecard.append({
            "hole": hole_num,
            "par": par,
            "score": score,
            "score_vs_par": score - par,
            "putts": putts,
            "gir": gir,
            "fir": fir_results[-1] if par >= 4 else None,
            "stg_tee": round(hole_stg["tee"], 2),
            "stg_approach": round(hole_stg["approach"], 2),
            "stg_short_game": round(hole_stg["short_game"], 2),
            "stg_putting": round(hole_stg["putting"], 2),
        })

    # ── Aggregate ──────────────────────────────────────────────────────────────
    total_score = sum(h["score"] for h in scorecard)
    total_par = sum(h["par"] for h in scorecard)
    holes_played = len(scorecard)
    norm = 18 / holes_played if holes_played > 0 else 1  # normalise to 18

    total_putts = sum(h["putts"] for h in scorecard)
    three_putts = sum(
        1 for hn, hs in shots_by_hole.items()
        if sum(1 for s in hs if s["surface"] == "Green") >= 3
    )

    fir_pct = sum(fir_results) / len(fir_results) if fir_results else 0
    gir_pct = sum(gir_results) / len(gir_results) if gir_results else 0

    scrambles = sum(
        1 for h in scorecard
        if not h["gir"] and h["score_vs_par"] <= 0
    )
    scramble_opps = sum(1 for h in scorecard if not h["gir"])
    scrambling = scrambles / scramble_opps if scramble_opps else 0

    score_dist = {
        "Eagle": sum(1 for h in scorecard if h["score_vs_par"] <= -2),
        "Birdie": sum(1 for h in scorecard if h["score_vs_par"] == -1),
        "Par": sum(1 for h in scorecard if h["score_vs_par"] == 0),
        "Bogey": sum(1 for h in scorecard if h["score_vs_par"] == 1),
        "Double": sum(1 for h in scorecard if h["score_vs_par"] == 2),
        "Worse": sum(1 for h in scorecard if h["score_vs_par"] >= 3),
    }

    stg_total = (
        sum(stg_tee_list) + sum(stg_app_list)
        + sum(stg_sg_list) + sum(stg_putt_list)
    )

    return {
        "scorecard": scorecard,
        "score": total_score,
        "par": total_par,
        "score_vs_par": total_score - total_par,
        "holes_played": holes_played,
        "putts": total_putts,
        "three_putts": three_putts,
        "fir_pct": round(fir_pct, 3),
        "gir_pct": round(gir_pct, 3),
        "scrambling": round(scrambling, 3),
        "driving_distances": driving_distances,
        "avg_drive": round(np.mean(driving_distances), 1) if driving_distances else None,
        "score_distribution": score_dist,
        # Normalised to 18 holes
        "stg_tee": round(sum(stg_tee_list) * norm, 2),
        "stg_approach": round(sum(stg_app_list) * norm, 2),
        "stg_short_game": round(sum(stg_sg_list) * norm, 2),
        "stg_putting": round(sum(stg_putt_list) * norm, 2),
        "stg_total": round(stg_total * norm, 2),
    }
