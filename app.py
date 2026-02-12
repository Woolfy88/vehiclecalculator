# app.py
# Streamlit "Wagon / Stillage" calculator with Altair fill visualisation
# - Online calculator only (no file picker)
# - Doors pack into stillages (max 14 doors per stillage)
# - 1 stillage = 2.25 large pallets
# - Wagon capacity expressed in "large pallets" (2.8m pallets)
#
# Run:
#   streamlit run app.py

from __future__ import annotations

import math
from dataclasses import dataclass

import altair as alt
import pandas as pd
import streamlit as st


# -----------------------------
# Config / constants
# -----------------------------
DOORS_PER_STILLAGE_MAX = 14
PALLETS_PER_STILLAGE = 2.25  # large pallets equivalent per stillage


# -----------------------------
# Core logic
# -----------------------------
@dataclass
class CalcResult:
    doors: int
    doors_per_stillage_max: int
    stillages_needed: int
    pallets_per_stillage: float
    wagon_capacity_pallets: float
    pallets_used: float
    pallets_remaining: float
    load_pct: float


def calculate(doors: int, wagon_capacity_pallets: float) -> CalcResult:
    doors = max(0, int(doors))
    wagon_capacity_pallets = max(0.0, float(wagon_capacity_pallets))

    stillages_needed = math.ceil(doors / DOORS_PER_STILLAGE_MAX) if doors > 0 else 0
    pallets_used = stillages_needed * PALLETS_PER_STILLAGE
    pallets_remaining = wagon_capacity_pallets - pallets_used
    load_pct = 0.0 if wagon_capacity_pallets <= 0 else (pallets_used / wagon_capacity_pallets) * 100.0

    return CalcResult(
        doors=doors,
        doors_per_stillage_max=DOORS_PER_STILLAGE_MAX,
        stillages_needed=stillages_needed,
        pallets_per_stillage=PALLETS_PER_STILLAGE,
        wagon_capacity_pallets=wagon_capacity_pallets,
        pallets_used=pallets_used,
        pallets_remaining=pallets_remaining,
        load_pct=load_pct,
    )


# -----------------------------
# Altair visualisations (Schema-safe)
# -----------------------------
def fill_bar_chart(result: CalcResult) -> alt.Chart:
    """Single horizontal bar split into Used / Remaining (or Over capacity)."""
    cap = float(result.wagon_capacity_pallets)
    used = float(result.pallets_used)

    if cap <= 0:
        df = pd.DataFrame([{"row": "Wagon", "part": "Used", "value": used}])
        return (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title="Large pallets equivalent"),
                y=alt.Y("row:N", title=None, axis=None),
                color=alt.Color("part:N", legend=alt.Legend(title=None, orient="bottom")),
                tooltip=["part:N", alt.Tooltip("value:Q", format=".2f")],
            )
            .properties(height=60)
        )

    if used <= cap:
        df = pd.DataFrame(
            [
                {"row": "Wagon", "part": "Used", "value": used},
                {"row": "Wagon", "part": "Remaining", "value": cap - used},
            ]
        )
        domain = ["Used", "Remaining"]
    else:
        df = pd.DataFrame(
            [
                {"row": "Wagon", "part": "Capacity", "value": cap},
                {"row": "Wagon", "part": "Over", "value": used - cap},
            ]
        )
        domain = ["Capacity", "Over"]

    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", stack="zero", title="Large pallets equivalent"),
            y=alt.Y("row:N", title=None, axis=None),
            color=alt.Color(
                "part:N",
                scale=alt.Scale(domain=domain),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
            tooltip=["part:N", alt.Tooltip("value:Q", format=".2f")],
        )
        .properties(height=60)
    )


def gauge_chart(result: CalcResult) -> alt.Chart:
    """
    0–100% utilisation gauge (marker clamped).
    NOTE: This chart avoids alt.value(...) in tooltip/encodings to satisfy strict schema validation.
    """
    pct = float(result.load_pct)
    clamped = max(0.0, min(pct, 100.0))

    # Background bar 0->100
    base = pd.DataFrame([{"row": "Utilisation", "start": 0.0, "end": 100.0}])
    # Fill bar 0->clamped
    fill = pd.DataFrame([{"row": "Utilisation", "start": 0.0, "end": clamped, "pct": clamped}])
    # Marker line at clamped
    marker = pd.DataFrame([{"row": "Utilisation", "pct": clamped}])
    # Text label (show true pct, even if > 100)
    label = pd.DataFrame([{"row": "Utilisation", "label": f"{pct:.1f}%"}])

    bar_bg = (
        alt.Chart(base)
        .mark_bar()
        .encode(
            x=alt.X("start:Q", title=None, scale=alt.Scale(domain=[0, 100])),
            x2="end:Q",
            y=alt.Y("row:N", title=None, axis=None),
        )
    )

    bar_fill = (
        alt.Chart(fill)
        .mark_bar()
        .encode(
            x="start:Q",
            x2="end:Q",
            y=alt.Y("row:N", axis=None),
            tooltip=[alt.Tooltip("pct:Q", title="Utilisation (clamped)", format=".1f")],
        )
    )

    rule = (
        alt.Chart(marker)
        .mark_rule()
        .encode(
            x=alt.X("pct:Q"),
            y=alt.Y("row:N", axis=None),
            tooltip=[alt.Tooltip("pct:Q", title="Marker (clamped)", format=".1f")],
        )
    )

    text = (
        alt.Chart(label)
        .mark_text(align="left", dx=6)
        .encode(
            x=alt.value(0),   # <-- this is OK for mark_text positioning in Altair/vega-lite
            y=alt.value(0),
            text="label:N",
        )
    )

    # Some environments are stricter even with alt.value in mark_text.
    # If you still get validation errors, remove the text layer (comment out "+ text" below).
    return (
        (bar_bg + bar_fill + rule)
        .properties(height=55)
        .configure_axis(grid=False, ticks=False, labels=False)
        .configure_view(strokeWidth=0)
    )


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Wagon Calculator", layout="wide")
st.title("Wagon Calculator (Stillage → Large Pallets)")

with st.sidebar:
    st.header("Inputs")
    doors = st.number_input("Total doors", min_value=0, value=0, step=1)
    wagon_capacity = st.number_input(
        "Wagon capacity (large pallets)",
        min_value=0.0,
        value=26.0,
        step=1.0,
        help="Enter capacity in 2.8m large pallets (equivalent units).",
    )

    st.divider()
    st.caption("Rules")
    st.write(f"- Max {DOORS_PER_STILLAGE_MAX} doors per stillage")
    st.write(f"- 1 stillage = {PALLETS_PER_STILLAGE} large pallets")
    show_debug = st.checkbox("Show debug", value=False)

result = calculate(doors=doors, wagon_capacity_pallets=wagon_capacity)

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Doors", f"{result.doors}")
k2.metric("Stillages needed", f"{result.stillages_needed}")
k3.metric("Large pallets used", f"{result.pallets_used:.2f}")

if result.wagon_capacity_pallets > 0:
    if result.pallets_used <= result.wagon_capacity_pallets:
        k4.metric(
            "Capacity remaining",
            f"{result.pallets_remaining:.2f}",
            delta=f"{100 - result.load_pct:.1f}% free",
        )
    else:
        k4.metric(
            "Over capacity",
            f"{abs(result.pallets_remaining):.2f}",
            delta=f"{result.load_pct - 100:.1f}% over",
        )
else:
    k4.metric("Capacity remaining", "—")

st.divider()

# Charts
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader("Wagon fill (large pallets equivalent)")
    st.altair_chart(fill_bar_chart(result), use_container_width=True)

with c2:
    st.subheader("Utilisation")
    st.altair_chart(gauge_chart(result), use_container_width=True)
    st.caption("Gauge marker clamps at 100%, but KPI shows true utilisation (can exceed 100%).")

# Breakdown
st.subheader("Breakdown")
st.write(
    f"""
- **Stillages needed** = ceil({result.doors} ÷ {result.doors_per_stillage_max}) = **{result.stillages_needed}**
- **Large pallets used** = {result.stillages_needed} × {result.pallets_per_stillage} = **{result.pallets_used:.2f}**
- **Capacity** = **{result.wagon_capacity_pallets:.2f}** large pallets
"""
)

if result.wagon_capacity_pallets > 0 and result.pallets_used > result.wagon_capacity_pallets:
    st.error(
        f"Over capacity by **{abs(result.pallets_remaining):.2f}** large pallets "
        f"({result.load_pct:.1f}% utilised)."
    )
elif result.wagon_capacity_pallets > 0:
    st.success(
        f"Within capacity. Remaining **{result.pallets_remaining:.2f}** large pallets "
        f"({result.load_pct:.1f}% utilised)."
    )
else:
    st.info("Set a wagon capacity to see remaining space / utilisation.")

if show_debug:
    with st.expander("Debug"):
        st.json(
            {
                "doors": result.doors,
                "doors_per_stillage_max": result.doors_per_stillage_max,
                "stillages_needed": result.stillages_needed,
                "pallets_per_stillage": result.pallets_per_stillage,
                "wagon_capacity_pallets": result.wagon_capacity_pallets,
                "pallets_used": result.pallets_used,
                "pallets_remaining": result.pallets_remaining,
                "load_pct": result.load_pct,
                "notes": [
                    "Doors pack into stillages up to 14 each (ceil).",
                    "Everything is expressed in large-pallet equivalents (no standard pallets).",
                ],
            }
        )
