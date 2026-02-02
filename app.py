# app.py
# Streamlit wagon fill calculator (ONLINE CALCULATOR ONLY)
#
# CURRENT RULES (as agreed):
# - 1 stillage holds MAX 14 doors
# - Only LARGE pallets (2.8m)
# - 1 stillage = 2.25 large pallets
#   => 1 large pallet = 1/2.25 = 0.444... stillage spaces
#
# This version REMOVES all Excel/.xlsm picker import logic.
# You enter door quantity and large pallet quantity directly in the app.

import math

import streamlit as st
import pandas as pd
import altair as alt


# -----------------------
# CONFIG / CONSTANTS
# -----------------------
DOORS_PER_STILLAGE_DEFAULT = 14
STILLAGE_TO_LARGE_PALLET = 2.25
LARGE_PALLET_TO_STILLAGE = 1 / STILLAGE_TO_LARGE_PALLET  # ~0.4444


# -----------------------
# HELPERS
# -----------------------
def ceil_div(a: float, b: float) -> int:
    if b == 0:
        return 0
    return int(math.ceil(a / b))


def traffic_label(util: float) -> str:
    if util <= 0.85:
        return "🟢 OK"
    if util <= 1.0:
        return "🟠 Tight"
    return "🔴 Over"


# -----------------------
# STREAMLIT UI
# -----------------------
st.set_page_config(page_title="Wagon Fill Calculator", layout="wide")
st.title("Wagon Fill Calculator (Online Calculator)")

st.caption(
    "Base unit = stillage space. Rules: 14 doors per stillage; only large pallets (2.8m); "
    "1 stillage = 2.25 large pallets."
)

# -----------------------
# VEHICLE RULES (EDIT THESE)
# IMPORTANT: pallet_cap now refers to LARGE PALLET (2.8m) capacity per vehicle
# stillage_cap = pallet_cap * (1/2.25)
# -----------------------
st.subheader("Vehicle definitions")

st.info(
    "Edit the vehicle table below so pallet_cap matches your **2.8m large pallet** capacity. "
    "Cube (m³) and payload (kg) should be your operational limits."
)

default_vehicles = pd.DataFrame(
    [
        {"vehicle": "3.5t", "pallet_cap": 2,  "cube_cap_m3": 15.0, "payload_kg": 1200,  "doors_upright_allowed": False},
        {"vehicle": "7.5t", "pallet_cap": 8,  "cube_cap_m3": 35.0, "payload_kg": 2500,  "doors_upright_allowed": False},
        {"vehicle": "18t",  "pallet_cap": 14, "cube_cap_m3": 45.0, "payload_kg": 9000,  "doors_upright_allowed": True},
        {"vehicle": "26t",  "pallet_cap": 16, "cube_cap_m3": 55.0, "payload_kg": 12000, "doors_upright_allowed": True},
        {"vehicle": "44t Artic", "pallet_cap": 26, "cube_cap_m3": 80.0, "payload_kg": 28000, "doors_upright_allowed": True},
    ]
)

vehicles = st.data_editor(
    default_vehicles,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True
).copy()

# Compute stillage capacity from large pallet capacity
vehicles["stillage_cap"] = vehicles["pallet_cap"].astype(float) * LARGE_PALLET_TO_STILLAGE

if vehicles.empty:
    st.error("Please enter at least one vehicle in the table above.")
    st.stop()

# -----------------------
# VEHICLE SELECTION
# -----------------------
st.subheader("Vehicle selection")
vehicle_name = st.selectbox("Choose vehicle", vehicles["vehicle"].tolist(), index=0)
veh = vehicles.loc[vehicles["vehicle"] == vehicle_name].iloc[0]

# -----------------------
# INPUTS (DOORS + LARGE PALLETS)
# -----------------------
st.subheader("Load inputs")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    doors_per_stillage = st.number_input("Doors per stillage", min_value=1, value=DOORS_PER_STILLAGE_DEFAULT, step=1)
    door_qty = st.number_input("Door quantity", min_value=0.0, value=0.0, step=1.0)
    doors_upright_required = st.checkbox("Doors require upright stillages", value=True)

with col2:
    large_pallet_qty = st.number_input("Large pallet quantity (2.8m)", min_value=0.0, value=0.0, step=1.0)

with col3:
    st.markdown("### Assumptions for weight & cube")
    door_stillage_weight = st.number_input("Weight per loaded door stillage (kg)", min_value=0.0, value=250.0, step=10.0)
    door_stillage_cube = st.number_input("Volume per loaded door stillage (m³)", min_value=0.0, value=1.6, step=0.1)

    large_pallet_weight = st.number_input("Weight per large pallet (kg)", min_value=0.0, value=600.0, step=10.0)
    large_pallet_cube = st.number_input("Volume per large pallet (m³)", min_value=0.0, value=2.2, step=0.1)

# -----------------------
# BUILD ORDER LINES
# -----------------------
# Doors -> stillages
door_stillages = int(math.ceil(float(door_qty) / float(doors_per_stillage))) if doors_per_stillage > 0 else 0

lines = pd.DataFrame(
    [
        {
            "item": "Doors",
            "qty": float(door_qty),
            "load_units": float(door_stillages),     # stillages
            "stillage_equiv": 1.0,                   # 1 stillage = 1 stillage space
            "weight_per_unit_kg": float(door_stillage_weight),
            "vol_per_unit_m3": float(door_stillage_cube),
            "upright_required": bool(doors_upright_required),
        },
        {
            "item": "Large pallets (2.8m)",
            "qty": float(large_pallet_qty),
            "load_units": float(large_pallet_qty),   # pallets
            "stillage_equiv": float(LARGE_PALLET_TO_STILLAGE),  # ~0.444 stillage spaces per pallet
            "weight_per_unit_kg": float(large_pallet_weight),
            "vol_per_unit_m3": float(large_pallet_cube),
            "upright_required": False,
        },
    ]
)

lines["total_stillage_spaces"] = lines["load_units"] * lines["stillage_equiv"]
lines["total_weight_kg"] = lines["load_units"] * lines["weight_per_unit_kg"]
lines["total_vol_m3"] = lines["load_units"] * lines["vol_per_unit_m3"]

total_stillage = float(lines["total_stillage_spaces"].sum())
total_weight = float(lines["total_weight_kg"].sum())
total_cube = float(lines["total_vol_m3"].sum())

needs_upright = bool((lines["upright_required"] & (lines["load_units"] > 0)).any())
upright_ok = (not needs_upright) or bool(veh.get("doors_upright_allowed", True))

# -----------------------
# UTILISATION
# -----------------------
stillage_cap = float(veh["stillage_cap"]) if float(veh["stillage_cap"]) else 0.0
cube_cap = float(veh["cube_cap_m3"]) if float(veh["cube_cap_m3"]) else 0.0
payload_cap = float(veh["payload_kg"]) if float(veh["payload_kg"]) else 0.0

stillage_util = (total_stillage / stillage_cap) if stillage_cap else 0.0
cube_util = (total_cube / cube_cap) if cube_cap else 0.0
weight_util = (total_weight / payload_cap) if payload_cap else 0.0

utils = {"Floor space (stillage)": stillage_util, "Cube": cube_util, "Weight": weight_util}
limiting = max(utils, key=utils.get)
overall = max(utils.values())

# -----------------------
# OUTPUTS / VISUALS
# -----------------------
st.subheader("Load utilisation")

c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])

with c1:
    st.metric("Overall utilisation (limiting)", f"{overall*100:.0f}%", f"Limiting: {limiting}")
    st.write(f"Status: **{traffic_label(overall)}**")
    if not upright_ok:
        st.error("Not allowed: this load requires upright door stillages, and this vehicle cannot take them.")

with c2:
    st.write("Floor space utilisation (stillage equivalent)")
    st.progress(min(stillage_util, 1.0))
    st.caption(f"{total_stillage:.2f} / {stillage_cap:.2f} stillage spaces ({stillage_util*100:.0f}%)")

with c3:
    st.write("Cube utilisation (m³)")
    st.progress(min(cube_util, 1.0))
    st.caption(f"{total_cube:.1f} / {cube_cap:.1f} m³ ({cube_util*100:.0f}%)")

with c4:
    st.write("Weight utilisation (kg)")
    st.progress(min(weight_util, 1.0))
    st.caption(f"{total_weight:.0f} / {payload_cap:.0f} kg ({weight_util*100:.0f}%)")

# Donut chart
chart_df = pd.DataFrame({"Constraint": list(utils.keys()), "Percent": [min(v * 100, 200) for v in utils.values()]})
donut = (
    alt.Chart(chart_df)
    .mark_arc(innerRadius=55)
    .encode(theta=alt.Theta(field="Percent", type="quantitative"), tooltip=["Constraint", "Percent"])
    .properties(height=230)
)
st.altair_chart(donut, use_container_width=True)

# Details
st.subheader("Converted load details")
st.dataframe(
    lines[
        [
            "item",
            "qty",
            "load_units",
            "stillage_equiv",
            "total_stillage_spaces",
            "total_weight_kg",
            "total_vol_m3",
        ]
    ],
    use_container_width=True,
)

st.subheader("Remaining capacity (negative = overloaded)")
rem_stillage = stillage_cap - total_stillage
rem_cube = cube_cap - total_cube
rem_weight = payload_cap - total_weight
st.write(
    {
        "stillage spaces remaining": round(rem_stillage, 2),
        "m3 remaining": round(rem_cube, 1),
        "kg remaining": round(rem_weight, 0),
    }
)

st.subheader("Estimated wagons needed (simple, constraint-based)")
wagons_by_space = ceil_div(total_stillage, stillage_cap)
wagons_by_cube = ceil_div(total_cube, cube_cap)
wagons_by_weight = ceil_div(total_weight, payload_cap)
st.write(
    {
        "by floor space (stillage)": wagons_by_space,
        "by cube": wagons_by_cube,
        "by weight": wagons_by_weight,
        "required (max)": max(wagons_by_space, wagons_by_cube, wagons_by_weight),
    }
)

st.info(
    "This version is an online calculator only (no Excel import). "
    "To deploy on Streamlit Cloud, save as app.py and add requirements.txt with: streamlit, pandas, altair."
)
