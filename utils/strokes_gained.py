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


def _normalize_surface(surface: str) -> str:
    if not isinstance(surface, str):
        return surface
    clean = surface.strip().title()
    mapping = {
        "Tee": "Tee",
        "Fairway": "Fairway",
        "Rough": "Rough",
        "Sand": "Sand",
        "Recovery": "Recovery",
        "Green": "Green",
    }
    return mapping.get(clean, surface.strip())


def _lookup_swing(surface: str, distance_m: float) -> float | None:
    surface = _normalize_surface(surface)
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
    surface = _normalize_surface(surface)
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
    surface = _normalize_surface(surface)
    if surface == "Tee":
        return "tee"
    if surface == "Green":
        return "putting"
    if surface == "Recovery":
        return "recovery"
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

    hole_map = {int(h["hole_number"]): h for h in holes}
    shots_by_hole: dict[int, list[dict]] = {}
    for s in shots:
        hn = int(s["hole_number"])
        shots_by_hole.setdefault(hn, []).append(s)

    # ── Per-hole results ───────────────────────────────────────────────────────
    scorecard = []
    stg_tee_list, stg_app_list, stg_sg_list, stg_putt_list, stg_recovery_list = [], [], [], [], []
    stg_app_fairway_list, stg_app_rough_list, stg_app_sand_list = [], [], []
    stg_par3_list, stg_par4_list, stg_par5_list = [], [], []
    fir_results, gir_results = [], []
    driving_distances = []
    # Putting distance tracking
    puts_6ft = 0
    puts_6_10ft = 0
    puts_10_30ft = 0
    puts_30plus = 0
    makes_6ft = 0
    makes_6_10ft = 0
    makes_10_30ft = 0
    makes_30plus = 0
    # SG by putting distance
    sg_6ft = 0.0
    sg_6_10ft = 0.0
    sg_10_30ft = 0.0
    sg_30plus = 0.0

    for hole_num in sorted(shots_by_hole.keys()):
        hole_shots = sorted(shots_by_hole[hole_num], key=lambda x: int(x["shot_number"]))
        hole_info = hole_map.get(hole_num, {})
        par = int(hole_info.get("par", 4))
        score = len(hole_shots)

        # Per-shot SG
        hole_stg = {
            "tee": 0.0, "approach": 0.0, "recovery": 0.0, "short_game": 0.0, "putting": 0.0,
            "approach_fairway": 0.0, "approach_rough": 0.0, "approach_sand": 0.0,
        }
        for i, shot in enumerate(hole_shots):
            surface = (shot["surface"] or "").strip()
            dist = float(shot["distance_to_hole"]) if shot["distance_to_hole"] else 0
            unit = shot["distance_unit"] or "meters"
            holed = bool(int(shot["holed"])) if shot["holed"] is not None else False
            
            # Track putting by distance (Green surface = putting)
            if surface == "Green" and dist > 0:
                # Convert to feet if needed
                dist_feet = dist if unit == "feet" else dist * FEET_PER_METER
                if dist_feet <= 6:
                    puts_6ft += 1
                    if holed:
                        makes_6ft += 1
                elif dist_feet <= 10:
                    puts_6_10ft += 1
                    if holed:
                        makes_6_10ft += 1
                elif dist_feet <= 30:
                    puts_10_30ft += 1
                    if holed:
                        makes_10_30ft += 1
                else:
                    puts_30plus += 1
                    if holed:
                        makes_30plus += 1

            if i + 1 < len(hole_shots):
                next_shot = hole_shots[i + 1]
                next_surface = (next_shot["surface"] or "").strip()
                next_dist = float(next_shot["distance_to_hole"]) if next_shot["distance_to_hole"] else 0
                next_unit = next_shot["distance_unit"] or "meters"
                sg = shot_strokes_gained(surface, dist, unit, next_surface, next_dist, next_unit, False)
            else:
                sg = shot_strokes_gained(surface, dist, unit, None, None, None, True)

            if sg is not None:
                dist_m = dist if unit == "meters" else dist / FEET_PER_METER
                phase = _shot_phase(surface, dist_m)
                hole_stg[phase] += sg
                if phase == "approach":
                    norm_surf = _normalize_surface(surface)
                    if norm_surf == "Fairway":
                        hole_stg["approach_fairway"] += sg
                    elif norm_surf == "Rough":
                        hole_stg["approach_rough"] += sg
                    elif norm_surf == "Sand":
                        hole_stg["approach_sand"] += sg
                
                # Accumulate SG by putting distance for Green shots
                if surface == "Green" and dist > 0:
                    dist_feet = dist if unit == "feet" else dist * FEET_PER_METER
                    if dist_feet <= 6:
                        sg_6ft += sg
                    elif dist_feet <= 10:
                        sg_6_10ft += sg
                    elif dist_feet <= 30:
                        sg_10_30ft += sg
                    else:
                        sg_30plus += sg

        stg_tee_list.append(hole_stg["tee"])
        stg_app_list.append(hole_stg["approach"])
        stg_recovery_list.append(hole_stg["recovery"])
        stg_sg_list.append(hole_stg["short_game"])
        stg_putt_list.append(hole_stg["putting"])
        stg_app_fairway_list.append(hole_stg["approach_fairway"])
        stg_app_rough_list.append(hole_stg["approach_rough"])
        stg_app_sand_list.append(hole_stg["approach_sand"])
        hole_total = (hole_stg["tee"] + hole_stg["approach"] + hole_stg["recovery"]
                      + hole_stg["short_game"] + hole_stg["putting"])
        if par == 3:
            stg_par3_list.append(hole_total)
        elif par == 4:
            stg_par4_list.append(hole_total)
        elif par == 5:
            stg_par5_list.append(hole_total)

        # Driving distance: only when driver was used on tee shot
        tee_shot = hole_shots[0]
        if tee_shot.get("club") == "Driver" and tee_shot.get("shot_distance"):
            try:
                driving_distances.append(float(tee_shot["shot_distance"]))
            except (ValueError, TypeError):
                pass

        # FIR: only count for par > 3; requires second shot on fairway
        if par > 3:
            if len(hole_shots) >= 2:
                fir_results.append(hole_shots[1]["surface"] == "Fairway")
            else:
                fir_results.append(False)

        # GIR rules:
        #  - Par 3: green on shot 2 (or hole-in-one)
        #  - Par 4: green on shot 2 or 3
        #  - Par 5: green on shot 2, 3 or 4
        if score == 1:
            gir = True
        else:
            gir_threshold = max(2, par - 1)
            gir = any(
                2 <= int(s["shot_number"]) <= gir_threshold and s["surface"] == "Green"
                for s in hole_shots
            )
        gir_results.append(gir)

        # Putts on this hole
        putts = sum(1 for s in hole_shots if s["surface"] == "Green")

        # Tiger 5 Rules tracking:
        # 1. Bogey on Par 5
        par5_bogey = par == 5 and score - par >= 1
        # 2. Double bogey or worse
        double_bogey = score - par >= 2
        # 3. Three-putt
        three_putt = putts >= 3
        # 4. Bogey with scoring club: approach shot from fairway/rough within 130m that led to bogey
        scoring_club_bogey = False
        if score - par == 1 and len(hole_shots) >= 2:
            # Find the last non-green shot (the approach shot that got you to the green)
            approach_shot = None
            for shot in reversed(hole_shots[:-1]):  # Exclude the last shot (which might be holed)
                if shot["surface"] != "Green":
                    approach_shot = shot
                    break
            if approach_shot and approach_shot["surface"] in ["Fairway", "Rough"]:
                dist = float(approach_shot.get("distance_to_hole", 0))
                if dist < 131:  # Using 131 to be inclusive of 130
                    scoring_club_bogey = True
        # 5. Missed easy up-and-down: had chance from close range (<10m) but failed to save par
        up_and_down = False
        had_close_approach = False
        for shot in hole_shots:
            if shot["surface"] in ["Fairway", "Rough", "Sand"]:
                dist = float(shot.get("distance_to_hole", 0))
                if dist < 10:
                    had_close_approach = True
                    break
        # Violation: had close approach within 10m but didn't save par
        if had_close_approach and score > par:
            up_and_down = True

        scorecard.append({
            "hole": hole_num,
            "par": par,
            "score": score,
            "score_vs_par": score - par,
            "putts": putts,
            "gir": gir,
            "fir": fir_results[-1] if par > 3 else None,
            "stg_tee": round(hole_stg["tee"], 2),
            "stg_approach": round(hole_stg["approach"], 2),
            "stg_recovery": round(hole_stg["recovery"], 2),
            "stg_short_game": round(hole_stg["short_game"], 2),
            "stg_putting": round(hole_stg["putting"], 2),
            # Tiger 5 Rules
            "par5_bogey": par5_bogey,
            "double_bogey": double_bogey,
            "three_putt": three_putt,
            "scoring_club_bogey": scoring_club_bogey,
            "up_and_down": up_and_down,
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
        + sum(stg_recovery_list) + sum(stg_sg_list) + sum(stg_putt_list)
    )

    gir_holes_list = [h for h in scorecard if h["gir"]]
    gir_birdie_pct = (
        sum(1 for h in gir_holes_list if h["score_vs_par"] <= -1) / len(gir_holes_list)
        if gir_holes_list else 0
    )

    # Score vs Par by par type
    par3_scores = [h["score_vs_par"] for h in scorecard if h["par"] == 3]
    par4_scores = [h["score_vs_par"] for h in scorecard if h["par"] == 4]
    par5_scores = [h["score_vs_par"] for h in scorecard if h["par"] == 5]

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
        "gir_birdie_pct": round(gir_birdie_pct, 3),
        "driving_distances": driving_distances,
        "avg_drive": round(np.mean(driving_distances), 1) if driving_distances else None,
        "score_distribution": score_dist,
        "par3_vs_par": sum(par3_scores) if par3_scores else 0,
        "par4_vs_par": sum(par4_scores) if par4_scores else 0,
        "par5_vs_par": sum(par5_scores) if par5_scores else 0,
        # Putting by distance
        "puts_6ft": puts_6ft,
        "makes_6ft": makes_6ft,
        "puts_6_10ft": puts_6_10ft,
        "makes_6_10ft": makes_6_10ft,
        "puts_10_30ft": puts_10_30ft,
        "makes_10_30ft": makes_10_30ft,
        "puts_30plus": puts_30plus,
        "makes_30plus": makes_30plus,
        # SG by putting distance
        "sg_6ft": round(sg_6ft * norm, 2),
        "sg_6_10ft": round(sg_6_10ft * norm, 2),
        "sg_10_30ft": round(sg_10_30ft * norm, 2),
        "sg_30plus": round(sg_30plus * norm, 2),
        # Tiger 5 Rules
        "tiger5_par5_bogeys": sum(1 for h in scorecard if h["par5_bogey"]),
        "tiger5_double_bogeys": sum(1 for h in scorecard if h["double_bogey"]),
        "tiger5_three_putts": sum(1 for h in scorecard if h["three_putt"]),
        "tiger5_scoring_bogeys": sum(1 for h in scorecard if h["scoring_club_bogey"]),
        "tiger5_up_and_downs": sum(1 for h in scorecard if h["up_and_down"]),
        # Normalised to 18 holes
        "stg_tee": round(sum(stg_tee_list) * norm, 2),
        "stg_approach": round(sum(stg_app_list) * norm, 2),
        "stg_recovery": round(sum(stg_recovery_list) * norm, 2),
        "stg_short_game": round(sum(stg_sg_list) * norm, 2),
        "stg_putting": round(sum(stg_putt_list) * norm, 2),
        "stg_total": round(stg_total * norm, 2),
        # Approach breakdown by surface (normalised to 18 holes)
        "stg_approach_fairway": round(sum(stg_app_fairway_list) * norm, 2),
        "stg_approach_rough": round(sum(stg_app_rough_list) * norm, 2),
        "stg_approach_sand": round(sum(stg_app_sand_list) * norm, 2),
        # STG by par type (raw round total — not normalised)
        "stg_par3": round(sum(stg_par3_list), 2),
        "stg_par4": round(sum(stg_par4_list), 2),
        "stg_par5": round(sum(stg_par5_list), 2),
    }
