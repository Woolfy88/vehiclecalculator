# app.py
# Streamlit wagon fill calculator (ONLINE CALCULATOR ONLY)
#
# CURRENT RULES (as agreed):
# - 1 stillage holds MAX 14 doors (FIXED, hidden from UI)
# - Only LARGE pallets (2.8m)
# - 1 stillage = 2.25 large pallets
# - Visual: rectangle blocks with labels (D1.. and P1..)
#
# This version:
# - Removes ALL Excel/.xlsm import logic
# - Fixed vehicles (no vehicle table UI)
# - Vehicle selection at top
# - Minimal UI (no hidden assumptions panel, no "doors per stillage" input)
# - Block/rectangle wagon floor visual (no mention of Goodloading)
# - Adds option to "Double-stack pallets" (reduces floor pallets by half, rounded up)
#
# Notes on double-stacking:
# - Applies ONLY to pallets (not door stillages).
# - If enabled: floor pallets shown = ceil(pallet_count / 2)
# - Weight and cube calculations remain based on FULL pallet count (you still carry them).
#   (If you want stacking to also reduce cube, say and I'll change it.)

import math

import pandas as pd
import streamlit as st


# -----------------------
# CONFIG / CONSTANTS
# -----------------------
DOORS_PER_STILLAGE = 14  # FIXED (hidden from UI)
STILLAGE_TO_LARGE_PALLET = 2.25
LARGE_PALLET_TO_STILLAGE = 1 / STILLAGE_TO_LARGE_PALLET  # ~0.4444

# Fixed assumptions (hidden from UI)
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


def build_floor_blocks_html(
    pallet_cap: float,
    door_stillages: int,
    large_pallet_qty: float,
    columns_pallets: int = 2,
    fill_order: str = "Doors then pallets",
    double_stack_pallets: bool = False,
) -> str:
    """
    Rectangle/block visual using quarter-pallet units:
    - Floor grid units: 1 pallet = 4x4 quarters
    - Pallet block: 4x4 quarters (1x1 pallet)
    - Door stillage block (Option A): 6x6 quarters (1.5x1.5 pallets) => 2.25 pallets exactly
    - Simple shelf packing: left-to-right, then new row
    - Overflow items shown in a separate overflow lane

    Double-stacking:
    - Visual/floor footprint ONLY: if enabled, floor pallets shown = ceil(pallet_count / 2)
    - Label shows stack count, e.g. P3×2 when representing 2 pallets.
    """
    # --- sizing in quarter units ---
    Q = 4  # quarters per pallet side (so 1 pallet = 4x4 quarters)
    floor_w = max(1, int(columns_pallets)) * Q

    cap_pallets = max(0.0, float(pallet_cap))
    cap_quarters = int(round(cap_pallets * (Q * Q)))  # pallets * 16 quarters per pallet

    # Item counts (inputs)
    door_stillages = max(0, int(door_stillages))
    pallet_count = max(0, int(round(float(large_pallet_qty))))

    # Block footprints (in quarters)
    DOOR_W, DOOR_H = 6, 6  # 1.5 x 1.5 pallets
    PAL_W, PAL_H = 4, 4    # 1 x 1 pallet

    # If double-stacking, convert pallets into "floor pallet stacks"
    # Each stack represents 2 pallets, except possibly the last which can be 1.
    pallet_stacks = []
    if double_stack_pallets and pallet_count > 0:
        stacks = int(math.ceil(pallet_count / 2))
        # Build stack sizes: mostly 2, last may be 1 if odd
        remaining = pallet_count
        for i in range(stacks):
            stack_n = 2 if remaining >= 2 else 1
            remaining -= stack_n
            pallet_stacks.append(stack_n)  # 1 or 2
    else:
        pallet_stacks = [1] * pallet_count

    # Build ordered item list (each "pallet stack" is one block)
    items = []

    def add_doors():
        for i in range(door_stillages):
            items.append(("door", f"D{i+1}", DOOR_W, DOOR_H))

    def add_pallets():
        for i, stack_n in enumerate(pallet_stacks):
            lbl = f"P{i+1}" if stack_n == 1 else f"P{i+1}×{stack_n}"
            items.append(("pallet", lbl, PAL_W, PAL_H))

    if fill_order == "Pallets then doors":
        add_pallets()
        add_doors()
    else:
        add_doors()
        add_pallets()

    # --- shelf pack on a grid (quarters) ---
    placed = []
    overflow = []

    x = 0
    y = 0
    shelf_h = 0
    used_quarters = 0

    for kind, label, w, h in items:
        if w > floor_w:
            overflow.append((kind, label, w, h))
            continue

        if x + w > floor_w:
            x = 0
            y += shelf_h
            shelf_h = 0

        # Tentatively place
        new_used = used_quarters + (w * h)
        if new_used > cap_quarters:
            overflow.append((kind, label, w, h))
            continue

        placed.append((kind, label, x, y, w, h))
        x += w
        shelf_h = max(shelf_h, h)
        used_quarters = new_used

    # Compute floor height from placements
    floor_h = 0
    if placed:
        floor_h = max(py + ph for _, _, _, py, _, ph in placed)
    floor_h = max(floor_h, Q)  # minimum height

    # Convert quarter-units to pixels
    cell_px = 18  # visual size per quarter cell
    floor_px_w = floor_w * cell_px
    floor_px_h = floor_h * cell_px

    # Overflow layout (simple row/rows)
    ov_blocks = []
    ov_x = 0
    ov_y = 0
    ov_row_h = 0
    ov_w_limit = floor_px_w

    for kind, label, w, h in overflow:
        bw = w * cell_px
        bh = h * cell_px
        if ov_x + bw > ov_w_limit:
            ov_x = 0
            ov_y += ov_row_h + 10
            ov_row_h = 0
        ov_blocks.append((label, ov_x, ov_y, bw, bh))
        ov_x += bw + 10
        ov_row_h = max(ov_row_h, bh)

    overflow_px_h = (ov_y + ov_row_h) if ov_blocks else 0

    # Stats (placed area in pallets)
    used_pallets_equiv = used_quarters / float(Q * Q)  # quarters / 16
    overflow_pallets_equiv = sum((w * h) for _, _, w, h in overflow) / float(Q * Q)

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

      .frame {{
        border: 2px solid #ddd;
        border-radius: 14px;
        background: #fafafa;
        padding: 10px;
      }}

      .floor {{
        position: relative;
        width: {floor_px_w}px;
        height: {floor_px_h}px;
        border-radius: 10px;
        border: 2px solid rgba(0,0,0,0.08);
        background:
          linear-gradient(to right, rgba(0,0,0,0.04) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(0,0,0,0.04) 1px, transparent 1px);
        background-size: {cell_px}px {cell_px}px;
        background-color: #ffffff;
        overflow: hidden;
      }}

      .block {{
        position: absolute;
        border-radius: 10px;
        border: 2px solid rgba(0,0,0,0.08);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        color: rgba(0,0,0,0.72);
        user-select: none;
        letter-spacing: 0.2px;
      }}
      .block.door {{ background: #6aa8ff; }}
      .block.pallet {{ background: #6be3a7; }}
      .block.overflow {{ background: #ff6b6b; }}

      .subtle {{
        margin-top: 8px;
        font-size: 0.85rem;
        color: rgba(0,0,0,0.6);
      }}

      .overflow-title {{
        margin-top: 10px;
        font-weight: 800;
      }}
      .overflow-area {{
        position: relative;
        width: {floor_px_w}px;
        height: {max(overflow_px_h, 0)}px;
        margin-top: 6px;
      }}
    </style>
    """

    legend = """
    <div class="legend">
      <div class="key"><span class="swatch door"></span>Door stillage</div>
      <div class="key"><span class="swatch pallet"></span>Large pallet</div>
      <div class="key"><span class="swatch overflow"></span>Overflow</div>
    </div>
    """

    stats = f"""
    <div style="margin:6px 0 10px 0; font-size:0.95rem;">
      <b>Capacity:</b> {cap_pallets:.0f} large pallets
      &nbsp; | &nbsp; <b>Placed:</b> {used_pallets_equiv:.2f} pallets
      &nbsp; | &nbsp; <b>Overflow:</b> {overflow_pallets_equiv:.2f} pallets
    </div>
    """

    blocks_html = ""
    for kind, label, bx, by, bw, bh in placed:
        left = bx * cell_px
        top = by * cell_px
        width = bw * cell_px
        height = bh * cell_px
        blocks_html += (
            f'<div class="block {kind}" style="left:{left}px; top:{top}px; width:{width}px; height:{height}px;">'
            f"{label}</div>"
        )

    overflow_html = ""
    if ov_blocks:
        overflow_html += '<div class="overflow-title">Overflow</div>'
        overflow_html += f'<div class="overflow-area" style="height:{max(overflow_px_h, 40)}px;">'
        for label, left, top, width, height in ov_blocks:
            overflow_html += (
                f'<div class="block overflow" style="left:{left}px; top:{top}px; width:{width}px; height:{height}px;">'
                f"{label}</div>"
            )
        overflow_html += "</div>"

    stacking_note = "Pallet stacking: ON (2-high where possible)." if double_stack_pallets else "Pallet stacking: OFF."
    hint = f"""
    <div class="subtle">
      Blocks: pallet = 1×1, stillage = 1.5×1.5 (2.25 pallets). Width: {columns_pallets} pallet(s). {stacking_note}
      This is a simple layout (not a full packing optimiser).
    </div>
    """

    return css + legend + stats + f'<div class="frame"><div class="floor">{blocks_html}</div>{overflow_html}{hint}</div>'


# -----------------------
# STREAMLIT UI
# -----------------------
st.set_page_config(page_title="Wagon Fill Calculator", layout="wide")
st.title("Wagon Fill Calculator")
st.caption(
    "Rules: 14 doors per stillage; only large pallets (2.8m); 1 stillage = 2.25 large pallets. "
    "Online calculator (no Excel import)."
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
# LOAD INPUTS
# -----------------------
st.subheader("Load inputs")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    door_qty = st.number_input("Door quantity", min_value=0.0, value=0.0, step=1.0)
    doors_upright_required = st.checkbox("Doors require upright stillages", value=True)

with col2:
    large_pallet_qty = st.number_input("Large pallet quantity (2.8m)", min_value=0.0, value=0.0, step=1.0)

with col3:
    double_stack_pallets = st.checkbox("Double-stack pallets (2-high)", value=False)

# -----------------------
# BUILD ORDER LINES
# -----------------------
door_stillages = int(math.ceil(float(door_qty) / float(DOORS_PER_STILLAGE))) if DOORS_PER_STILLAGE > 0 else 0

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
# UTILISATION (math stays the same)
# -----------------------
stillage_cap = float(veh["stillage_cap"]) if float(veh["stillage_cap"]) else 0.0
cube_cap = float(veh["cube_cap_m3"]) if float(veh["cube_cap_m3"]) else 0.0
payload_cap = float(veh["payload_kg"]) if float(veh["payload_kg"]) else 0.0

# Floor-space utilisation for pallets can optionally treat stacking as reduced footprint:
# - Doors (stillages) always consume floor space.
# - Pallets consume floor space at half rate if double-stacked.
pallet_floor_qty = float(large_pallet_qty)
if double_stack_pallets:
    pallet_floor_qty = float(math.ceil(pallet_floor_qty / 2.0))

# Recompute floor-space total with stacking applied (for floor-space only)
total_stillage_for_floor = float(door_stillages) + pallet_floor_qty * float(LARGE_PALLET_TO_STILLAGE)

stillage_util = (total_stillage_for_floor / stillage_cap) if stillage_cap else 0.0
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
    if double_stack_pallets and large_pallet_qty > 0:
        st.caption("Note: floor-space utilisation and visual reflect double-stacking pallets; weight/cube remain unstacked.")

with c2:
    st.write("Floor space utilisation (stillage equivalent)")
    st.progress(min(stillage_util, 1.0))
    st.caption(f"{total_stillage_for_floor:.2f} / {stillage_cap:.2f} stillage spaces ({stillage_util*100:.0f}%)")

with c3:
    st.write("Cube utilisation (m³)")
    st.progress(min(cube_util, 1.0))
    st.caption(f"{total_cube:.1f} / {cube_cap:.1f} m³ ({cube_util*100:.0f}%)")

with c4:
    st.write("Weight utilisation (kg)")
    st.progress(min(weight_util, 1.0))
    st.caption(f"{total_weight:.0f} / {payload_cap:.0f} kg ({weight_util*100:.0f}%)")

# -----------------------
# WAGON FLOOR BLOCK VISUAL
# -----------------------
st.subheader("Wagon floor layout")

vc1, vc2, vc3 = st.columns([1, 1, 2])
with vc1:
    width_pallets = st.selectbox("Wagon width (pallets)", [1, 2, 3], index=1)
with vc2:
    fill_order = st.selectbox("Fill order", ["Doors then pallets", "Pallets then doors"], index=0)
with vc3:
    st.caption("Block layout visual with labels (simple layout, not a full packing optimiser).")

html = build_floor_blocks_html(
    pallet_cap=float(veh["pallet_cap"]),
    door_stillages=int(door_stillages),
    large_pallet_qty=float(large_pallet_qty),
    columns_pallets=int(width_pallets),
    fill_order=str(fill_order),
    double_stack_pallets=bool(double_stack_pallets),
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
