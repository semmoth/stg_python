"""
Equipment — version-controlled bag configurations.

Tracks which clubs are in the bag over time. Activate a config to make it
the current bag shown in Data Entry. Historical configs stay linked to the
rounds played while they were active (by date range for reference).
"""
import streamlit as st
import json
from datetime import date

from db.queries import (
    get_equipment_configs,
    get_active_equipment_config,
    create_equipment_config,
    set_active_equipment_config,
    delete_equipment_config,
)
from utils.constants import CLUBS

st.title("🎒 Equipment")

# ── Seed initial configs if the table is empty ─────────────────────────────────
configs = get_equipment_configs()

if not configs:
    current_clubs = [
        "Driver", "4 Wood", "7 Wood", "2 Hybrid",
        "4 Iron", "5 Iron", "6 Iron", "7 Iron", "8 Iron", "9 Iron",
        "PW", "GW", "SW", "LW", "Putter",
    ]
    new_clubs = [
        "Driver", "4 Wood", "7 Wood", "2 Hybrid",
        "5 Iron", "6 Iron", "7 Iron", "8 Iron", "9 Iron",
        "PW", "W", "SW", "LW", "Putter",
    ]
    current_id = create_equipment_config(
        "Ping iBlade 4-PW",
        current_clubs,
        "2025-01-01",
        "Current irons 4-PW. 7 Wood in bag as alternate to 2 Hybrid.",
    )
    set_active_equipment_config(current_id)
    create_equipment_config(
        "Ping iBlade 5-PW + W",
        new_clubs,
        "2026-06-07",
        "New fitted irons — 5-PW plus dedicated W wedge. No 4 Iron, no separate GW. "
        "Activate when irons arrive.",
    )
    configs = get_equipment_configs()
    st.rerun()

# ── Current bag ────────────────────────────────────────────────────────────────
active = get_active_equipment_config()

st.subheader("Current bag")
if active:
    st.markdown(f"**{active['name']}** — active since {active['effective_from']}")
    if active.get("notes"):
        st.caption(active["notes"])
    bag_clubs = json.loads(active["clubs"])
    cols = st.columns(4)
    for i, club in enumerate(bag_clubs):
        cols[i % 4].markdown(f"• {club}")
else:
    st.warning("No active bag set. Activate one below.")

st.markdown("---")

# ── All configurations ─────────────────────────────────────────────────────────
st.subheader("All configurations")

for cfg in configs:
    is_active = int(cfg.get("active", 0)) == 1
    icon = "✅ " if is_active else ""
    label = f"{icon}**{cfg['name']}** — since {cfg['effective_from']}"

    with st.expander(label, expanded=is_active):
        if cfg.get("notes"):
            st.caption(cfg["notes"])

        clubs_in_cfg = json.loads(cfg["clubs"])
        st.markdown("**Clubs:** " + " · ".join(clubs_in_cfg))

        col_act, col_del = st.columns([2, 1])
        with col_act:
            if not is_active:
                if st.button("Set as active bag", key=f"activate_{cfg['id']}", type="primary"):
                    set_active_equipment_config(int(cfg["id"]))
                    st.cache_data.clear()
                    st.success(f"'{cfg['name']}' is now the active bag.")
                    st.rerun()
            else:
                st.markdown("*Currently active*")
        with col_del:
            if not is_active:
                if st.button("Delete", key=f"del_{cfg['id']}"):
                    delete_equipment_config(int(cfg["id"]))
                    st.rerun()

st.markdown("---")

# ── Create new configuration ───────────────────────────────────────────────────
with st.expander("➕ Create new configuration"):
    cfg_name = st.text_input("Name", placeholder="e.g. Callaway Apex 5-PW")
    cfg_date = st.date_input("Effective from", value=date.today())
    cfg_notes = st.text_input("Notes (optional)")

    st.markdown("**Select clubs in bag:**")
    default_bag = json.loads(active["clubs"]) if active else list(CLUBS)
    selected = []
    cols = st.columns(4)
    for i, club in enumerate(CLUBS):
        if cols[i % 4].checkbox(club, value=(club in default_bag), key=f"newcfg_{club}"):
            selected.append(club)

    if st.button("Save configuration", type="primary"):
        if not cfg_name.strip():
            st.error("Name is required.")
        elif not selected:
            st.error("Select at least one club.")
        else:
            create_equipment_config(cfg_name.strip(), selected, str(cfg_date), cfg_notes)
            st.success("Configuration saved!")
            st.rerun()
