# app.py
# Streamlit "Wagon / Stillage" calculator with Altair fill visualisation
# - No file picker (online calculator only)
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
# Altair visualisations
# -----------------------------
def fill_bar_chart(result: CalcResult) -> alt.Chart:
    """Single horizontal bar split into Used / Remaining (or Over capacity)."""
    cap = result.wagon_capacity_pallets
    used = result.pallets_used

    if cap <= 0:
        df = pd.DataFrame(
            [
                {"part": "Used", "value": used, "note": "Set a wagon capacity to see utilisation."},
            ]
        )
        return (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("value:Q", title="Large pallets equivalent"),
                y=alt.Y("part:N", title=None),
                tooltip=["part:N", alt.Tooltip("value:Q", format=".2f"), "note:N"],
            )
            .properties(height=70)
        )

    if used <= cap:
        df = pd.DataFrame(
            [
                {"part": "Used", "value": used},
                {"part": "Remaining", "value": cap - used},
            ]
        )
        domain = ["Used", "Remaining"]
    else:
        # Over capacity: show capacity as "Capacity" plus "Over"
        df = pd.DataFrame(
            [
                {"part": "Capacity", "value": cap},
                {"part": "Over", "value": used - cap},
            ]
        )
        domain = ["Capacity", "Over"]

    # Stacked horizontal bar
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", stack="zero", title="Large pallets equivalent"),
            y=alt.Y(alt.value(0), axis=None),
            color=alt.Color(
                "part:N",
                scale=alt.Scale(domain=domain),
                legend=alt.Legend(title=None, orient="bottom"),
            ),
            tooltip=["part:N", alt.Tooltip("value:Q", format=".2f")],
        )
        .properties(height=55)
    )


def gauge_chart(result: CalcResult) -> alt.Chart:
    """Compact 'utilisation gauge' from 0 to 100% (clamped) with a marker for actual % (can exceed 100)."""
    pct = result.load_pct
    clamped = min(max(pct, 0.0), 100.0)

    base = pd.DataFrame([{"label": "Utilisation", "start": 0, "end": 100}])
    fill = pd.DataFrame([{"label": "Utilisation", "start": 0, "end": clamped}])
    marker = pd.DataFrame([{"label": "Utilisation", "pct": clamped}])

    bar_bg = (
        alt.Chart(base)
        .mark_bar()
        .encode(
            x=alt.X("start:Q", title=None, scale=alt.Scale(domain=[0, 100])),
            x2="end:Q",
            y=alt.Y("label:N", title=None),
            tooltip=[alt.value("0–100% scale")],
        )
    )

    bar_fill = (
        alt.Chart(fill)
        .mark_bar()
        .encode(
            x="start:Q",
            x2="end:Q",
            y="label:N",
            tooltip=[alt.Tooltip("end:Q", title="Utilisation (clamped)", format=".1f")],
        )
    )

    rule = (
        alt.Chart(marker)
        .mark_rule()
        .encode(
            x=alt.X("pct:Q"),
            y="label:N",
            tooltip=[alt.Tooltip("pct:Q", title="Marker (clamped)", format=".1f")],
        )
    )

    text = (
        alt.Chart(pd.DataFrame([{"text": f"{pct:.1f}%"}]))
        .mark_text(align="left", dx=6)
        .encode(x=alt.value(0), y=alt.value(0), text="text:N")
    )

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
        k4.metric("Capacity remaining", f"{result.pallets_remaining:.2f}", delta=f"{100 - result.load_pct:.1f}% free")
    else:
        k4.metric("Over capacity", f"{abs(result.pallets_remaining):.2f}", delta=f"{result.load_pct - 100:.1f}% over")
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
    st.caption("Gauge clamps at 100% but the KPI shows true % (can exceed 100%).")

# Explanation / output breakdown
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
                    "No standard pallets: everything expressed in large-pallet equivalents.",
                ],
            }
        )
