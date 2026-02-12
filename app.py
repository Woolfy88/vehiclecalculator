# app.py
# Streamlit wagon fill calculator (ONLINE CALCULATOR ONLY)
#
# CURRENT RULES (as agreed):
# - 1 stillage holds MAX 14 doors
# - Only LARGE pallets (2.8m)
# - 1 stillage = 2.25 large pallets
#   => 1 large pallet = 1/2.25 = 0.444... stillage spaces
#
# This version:
# - Removes ALL Excel/.xlsm import logic
# - Removes vehicle definitions table (fixed vehicles)
# - Moves vehicle selection to the very top
# - Removes constraint comparison chart
# - Removes "Assumptions for weight & cube" input section from the UI
# - Includes a Goodloading-style wagon floor fill visual using Streamlit + HTML/CSS only

import math

import pandas as pd
import streamlit as st


# -----------------------
# CONFIG / CONSTANTS
# -----------------------
DOORS_PER_STILLAGE_DEFAULT = 14
STILLAGE_TO_LARGE_PALLET = 2.25
LARGE_PALLET_TO_STILLAGE = 1 / STILLAGE_TO_LARGE_PALLET  # ~0.4444

# Fixed assumptions (previous UI inputs are now hard-coded)
DOOR_STILLAGE_WEIGHT_KG = 250.0
DOOR_STILLAGE_CUBE_M3 = 1.6
LARGE_PALLET_WEIGHT_KG = 600.0
LARGE_PALLET_CUBE_M3 = 2.2


# -----------------------
# HELPERS
# -----------------------
def traffic_label(util: float) -> str:
    if util <= 0.85:
        return "🟢 OK"
    if util <= 1.0:
        return "🟠 Tight"
    return "🔴 Over"


def build_floor_fill_html(
    pallet_cap: float,
    door_stillages: int,
    large_pallet_qty: float,
    columns_pallets: int = 2,
    fill_order: str = "Doors then pallets",
) -> str:
    """
    Goodloading-style simple fill:
    - Wagon capacity is pallet_cap (large pallets)
    - Render as quarter-pallet cells so stillage 2.25 pallets becomes 9 cells
    - Fill order: doors then pallets (default) or pallets then doors
    - Anything beyond capacity is shown as overflow (red)
    """
    cells_per_pallet = 4  # quarter-pallet resolution

    cap_pallets = max(0.0, float(pallet_cap))
    cap_cells = int(round(cap_pallets * cells_per_pallet))

    door_stillages = max(0, int(door_stillages))
    large_pallet_qty = max(0.0, float(large_pallet_qty))

    door_cells_each = int(round(STILLAGE_TO_LARGE_PALLET * cells_per_pallet))  # 2.25*4 = 9
    pallet_cells_each = cells_per_pallet  # 1 pallet = 4 quarter-cells

    used_door_cells = door_stillages * door_cells_each
    used_pallet_cells = int(round(large_pallet_qty * pallet_cells_each))

    used_cells = used_door_cells + used_pallet_cells
    overflow_cells = max(0, used_cells - cap_cells)

    # Grid sizing
    cols = max(1, int(columns_pallets) * cells_per_pallet)  # e.g., 2 pallets wide => 8 quarter-cells wide
    rows = int(math.ceil(max(cap_cells, used_cells, 1) / cols))
    total_cells_drawn = rows * cols

    # Build in fill order
    cells = []
    if fill_order == "Pallets then doors":
        cells += ["pallet"] * used_pallet_cells
        cells += ["door"] * used_door_cells
    else:
        cells += ["door"] * used_door_cells
        cells += ["pallet"] * used_pallet_cells

    # Pad out to full grid
    if len(cells) < total_cells_drawn:
        cells += ["empty"] * (total_cells_drawn - len(cells))
    else:
        cells = cells[:total_cells_drawn]

    # Mark overflow region (anything beyond cap_cells is overflow)
    for i in range(min(total_cells_drawn, cap_cells), total_cells_drawn):
        if cells[i] != "empty":
            cells[i] = "overflow"

    css = f"""
    <style>
      .legend {{
        display:flex; gap:12px; align-items:center; flex-wrap:wrap;
        margin: 6px 0 10px 0; font-size: 0.9rem;
      }}
      .key {{ display:flex; gap:6px; align-items:center; }}
      .swatch {{
        width: 14px; height: 14px; border-radius: 3px;
        border: 1px solid rgba(0,0,0,0.1);
      }}
      .swatch.door {{ background: #6aa8ff; }}
      .swatch.pallet {{ background: #6be3a7; }}
      .swatch.overflow {{ background: #ff6b6b; }}
      .swatch.empty {{ background: #ffffff; }}

      .wagon-frame {{
        border: 2px solid #ddd;
        border-radius: 14px;
        background: #fafafa;
        padding: 10px;
      }}

      .wagon-wrap {{
        display: grid;
        grid-template-columns: repeat({cols}, 1fr);
        gap: 3px;
      }}

      .cell {{
        width: 100%;
        aspect-ratio: 1 / 1;
        border-radius: 4px;
        border: 1px solid rgba(0,0,0,0.06);
      }}
      .cell.empty {{ background: #ffffff; }}
      .cell.door {{ background: #6aa8ff; }}
      .cell.pallet {{ background: #6be3a7; }}
      .cell.overflow {{ background: #ff6b6b; }}

      .hint {{
        margin-top: 8px;
        font-size: 0.85rem;
        color: rgba(0,0,0,0.6);
      }}
    </style>
    """

    legend = """
    <div class="legend">
      <div class="key"><span class="swatch door"></span>Door stillage</div>
      <div class="key"><span class="swatch pallet"></span>Large pallet</div>
      <div class="key"><span class="swatch overflow"></span>Overflow</div>
      <div class="key"><span class="swatch empty"></span>Empty</div>
    </div>
    """

    stats = f"""
    <div style="margin:6px 0 10px 0; font-size:0.95rem;">
      <b>Capacity:</b> {cap_pallets:.0f} large pallets ({cap_cells} quarter-cells)
      &nbsp; | &nbsp; <b>Used:</b> {(used_cells / cells_per_pallet):.2f} pallets
      &nbsp; | &nbsp; <b>Overflow:</b> {(overflow_cells / cells_per_pallet):.2f} pallets
    </div>
    """

    html_cells = "".join([f'<div class="cell {c}"></div>' for c in cells])

    hint = f"""
    <div class="hint">
      Visual resolution: 1 pallet = 4 cells. 1 door stillage = 2.25 pallets = 9 cells.
      Wagon width: {columns_pallets} pallet(s) ({cols} cells).
    </div>
    """

    return css + legend + stats + f'<div class="wagon-frame"><div class="wagon-wrap">{html_cells}</div>{hint}</div>'


# -----------------------
# STREAMLIT UI
# -----------------------
st.set_page_config(page_title="Wagon Fill Calculator", layout="wide")
st.title("Wagon Fill Calculator")
st.caption(
    "Rules: 14 doors per stillage; only large pallets (2.8m); 1 stillage = 2.25 large pallets. "
    "This is an online calculator (no Excel import)."
)

# -----------------------
# FIXED VEHICLE DEFINITIONS (not editable)
# -----------------------
vehicles = pd.DataFrame(
    [
        {"vehicle": "3.5t", "pallet_cap": 2, "cube_cap_m3": 15.0, "payload_kg": 1200, "doors_upright_allowed": False},
        {"vehicle": "7.5t", "pallet_cap": 8, "cube_cap_m3": 35.0, "payload_kg": 2500, "doors_upright_allowed": False},
        {"vehicle": "18t", "pallet_cap": 14, "cube_cap_m3": 45.0, "payload_kg": 9000, "doors_upright_allowed": True},
        {"vehicle": "26t", "pallet_cap": 16, "cube_cap_m3": 55.0, "payload_kg": 12000, "doors_upright_allowed": True},
        {"vehicle": "44t Artic", "pallet_cap": 26, "cube_cap_m3": 80.0, "payload_kg": 28000, "doors_upright_allowed": True},
    ]
)
vehicles["stillage_cap"] = vehicles["pallet_cap"].astype(float) * LARGE_PALLET_TO_STILLAGE

# -----------------------
# VEHICLE SELECTION (top)
# -----------------------
st.subheader("Vehicle")
vehicle_name = st.selectbox("Choose vehicle", vehicles["vehicle"].tolist(), index=4)
veh = vehicles.loc[vehicles["vehicle"] == vehicle_name].iloc[0]

# -----------------------
# LOAD INPUTS (ONLY)
# -----------------------
st.subheader("Load inputs")

col1, col2 = st.columns([1, 1])

with col1:
    doors_per_stillage = st.number_input("Doors per stillage", min_value=1, value=DOORS_PER_STILLAGE_DEFAULT, step=1)
    door_qty = st.number_input("Door quantity", min_value=0.0, value=0.0, step=1.0)
    doors_upright_required = st.checkbox("Doors require upright stillages", value=True)

with col2:
    large_pallet_qty = st.number_input("Large pallet quantity (2.8m)", min_value=0.0, value=0.0, step=1.0)

# -----------------------
# BUILD ORDER LINES
# -----------------------
door_stillages = int(math.ceil(float(door_qty) / float(doors_per_stillage))) if doors_per_stillage > 0 else 0

lines = pd.DataFrame(
    [
        {
            "item": "Doors",
            "qty": float(door_qty),
            "load_units": float(door_stillages),  # stillages
            "stillage_equiv": 1.0,
            "weight_per_unit_kg": float(DOOR_STILLAGE_WEIGHT_KG),
            "vol_per_unit_m3": float(DOOR_STILLAGE_CUBE_M3),
            "upright_required": bool(doors_upright_required),
        },
        {
            "item": "Large pallets (2.8m)",
            "qty": float(large_pallet_qty),
            "load_units": float(large_pallet_qty),  # pallets
            "stillage_equiv": float(LARGE_PALLET_TO_STILLAGE),
            "weight_per_unit_kg": float(LARGE_PALLET_WEIGHT_KG),
            "vol_per_unit_m3": float(LARGE_PALLET_CUBE_M3),
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
# OUTPUTS
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

# -----------------------
# WAGON FLOOR FILL VISUAL
# -----------------------
st.subheader("Wagon floor fill (visual)")

vc1, vc2, vc3 = st.columns([1, 1, 2])
with vc1:
    width_pallets = st.selectbox("Wagon width (pallets)", [1, 2, 3], index=1)
with vc2:
    fill_order = st.selectbox("Fill order", ["Doors then pallets", "Pallets then doors"], index=0)
with vc3:
    st.caption("Goodloading-style visual using quarter-pallet cells (simple fill, not an optimiser).")

html = build_floor_fill_html(
    pallet_cap=float(veh["pallet_cap"]),
    door_stillages=int(door_stillages),
    large_pallet_qty=float(large_pallet_qty),
    columns_pallets=int(width_pallets),
    fill_order=str(fill_order),
)
st.markdown(html, unsafe_allow_html=True)

# -----------------------
# DETAILS
# -----------------------
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

st.caption("Deployment: requirements.txt should contain `streamlit` and `pandas`.")
