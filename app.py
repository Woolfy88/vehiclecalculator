# app.py
# Streamlit wagon fill calculator (ONLINE CALCULATOR ONLY)
#
# CURRENT RULES / BEHAVIOUR:
# - Focus is vehicle FLOOR SPACE using real footprints:
#     * Steel door stillage footprint: 1300mm x 1200mm (1.3m x 1.2m)
#     * Wood pallet footprint:        1200mm x 3000mm (1.2m x 3.0m)
# - Vehicle cube cap is computed from internal dimensions (L x W x H).
# - Floor utilisation is based on m² used vs USABLE vehicle floor area (L x usable_W).
# - Optional "Multi-drop hub delivery dead space" reduces usable width by 0.50m down full length.
# - Visual remains the APPROX pallet grid (as before), but capacity is derived from usable floor area.
# - Double-stack pallets option remains:
#     * Applies ONLY to pallets for FLOOR space and VISUAL footprint (ceil(pallets/2))
#     * Weight and cube remain based on full pallet count.
#
# Notes:
# - This is NOT a full packing optimiser; remaining capacity in pallets/stillages is area-based guidance.

import math
import pandas as pd
import streamlit as st


# -----------------------
# CONFIG / CONSTANTS
# -----------------------
DOORS_PER_STILLAGE = 14  # FIXED (hidden from UI)

# Footprints (metres) - UPDATED
STILLAGE_L, STILLAGE_W = 1.3, 1.2   # 1300 x 1200
PALLET_L, PALLET_W = 3.0, 1.2       # 3000 x 1200

STILLAGE_AREA_M2 = STILLAGE_L * STILLAGE_W   # 1.56
PALLET_AREA_M2 = PALLET_L * PALLET_W         # 3.60

# Dead space for hub multi-drops (metres)
DEAD_SPACE_GAP_M = 0.50  # 50cm continuous strip down full length

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
    pallet_cap_equiv: float,
    door_stillages: int,
    large_pallet_qty: float,
    columns_pallets: int = 2,
    fill_order: str = "Doors then pallets",
    double_stack_pallets: bool = False,
) -> str:
    """
    Rectangle/block visual using quarter-pallet units:
    - Floor grid units: 1 pallet = 4x4 quarters (16)
    - Pallet block: 4x4 quarters (1x1 pallet)
    - Door stillage block footprint (visual proxy):
        True ratio = STILLAGE_AREA / PALLET_AREA ≈ 1.56 / 3.60 ≈ 0.433 pallet
        Use 3x2 quarters = 6/16 = 0.375 pallet as a close proxy.

    Capacity:
    - pallet_cap_equiv is derived from usable floor area:
        usable_floor_area_m2 / PALLET_AREA_M2

    Double-stacking:
    - Visual/floor footprint ONLY: if enabled, floor pallets shown = ceil(pallet_count / 2)
    - Label shows stack count, e.g. P3×2 when representing 2 pallets.
    """
    # --- sizing in quarter units ---
    Q = 4  # quarters per pallet side (so 1 pallet = 4x4 quarters)
    floor_w = max(1, int(columns_pallets)) * Q

    cap_pallets = max(0.0, float(pallet_cap_equiv))
    # Safer to floor capacity (avoid rounding "extra" space into existence)
    cap_quarters = int(math.floor(cap_pallets * (Q * Q)))  # pallets * 16 quarters per pallet

    # Item counts (inputs)
    door_stillages = max(0, int(door_stillages))
    pallet_count = max(0, int(round(float(large_pallet_qty))))

    # Block footprints (in quarters)
    PAL_W, PAL_H = 4, 4         # Pallet: 1 x 1 pallet
    DOOR_W, DOOR_H = 3, 2       # Door stillage proxy: 6 quarters = 0.375 pallet

    # If double-stacking, convert pallets into "floor pallet stacks"
    pallet_stacks = []
    if double_stack_pallets and pallet_count > 0:
        stacks = int(math.ceil(pallet_count / 2))
        remaining = pallet_count
        for _ in range(stacks):
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
    cell_px = 18
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
    used_pallets_equiv = used_quarters / float(Q * Q)
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
      <b>Capacity (pallet-equiv):</b> {cap_pallets:.2f}
      &nbsp; | &nbsp; <b>Placed:</b> {used_pallets_equiv:.2f} (floor area)
      &nbsp; | &nbsp; <b>Overflow:</b> {overflow_pallets_equiv:.2f} (floor area)
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
      Visual uses an approximate pallet grid. Door stillage block is a close proxy to real footprint ratio.
      Width: {columns_pallets} pallet(s). {stacking_note}
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
    "Focus: vehicle FLOOR SPACE (m²) using real footprints. "
    "Rules: 14 doors per stillage; pallets are 1200×3000; stillages are 1300×1200. "
    "Online calculator (no Excel import)."
)

# -----------------------
# VEHICLE DEFINITIONS (computed from internal dimensions) - UPDATED
# -----------------------
vehicles = pd.DataFrame(
    [
        {"vehicle": "3.5t", "L_m": 3.66, "W_m": 2.00, "H_m": 1.75, "payload_kg": 1200,   "doors_upright_allowed": False},
        {"vehicle": "7.5t", "L_m": 5.49, "W_m": 2.40, "H_m": 2.20, "payload_kg": 2500,   "doors_upright_allowed": False},
        {"vehicle": "18t",  "L_m": 8.33, "W_m": 2.54, "H_m": 2.67, "payload_kg": 10000,  "doors_upright_allowed": True},
        # Per your update: 26t now uses 8.33m internal length (not 9.15m)
        {"vehicle": "26t",  "L_m": 8.33, "W_m": 2.54, "H_m": 2.80, "payload_kg": 15500,  "doors_upright_allowed": True},
        {"vehicle": "44t Artic & Trailer", "L_m": 13.5, "W_m": 2.48, "H_m": 2.77, "payload_kg": 28000, "doors_upright_allowed": True},
    ]
)

vehicles["cube_cap_m3"] = vehicles["L_m"] * vehicles["W_m"] * vehicles["H_m"]
vehicles["floor_area_m2"] = vehicles["L_m"] * vehicles["W_m"]  # raw (before hub dead-space)

# -----------------------
# VEHICLE SELECTION (top)
# -----------------------
st.subheader("Vehicle")
vehicle_name = st.selectbox("Choose vehicle", vehicles["vehicle"].tolist(), index=len(vehicles) - 1)
veh = vehicles.loc[vehicles["vehicle"] == vehicle_name].iloc[0]

# -----------------------
# DELIVERY MODE (hub dead space option)
# -----------------------
st.subheader("Delivery mode")

dead_space_enabled_default = vehicle_name in ["26t", "44t Artic & Trailer"]
dead_space_enabled = st.checkbox(
    "Multi-drop hub delivery (0.50m dead space down vehicle length)",
    value=dead_space_enabled_default,
)

usable_width_m = float(veh["W_m"]) - (DEAD_SPACE_GAP_M if dead_space_enabled else 0.0)
usable_width_m = max(0.0, usable_width_m)
usable_floor_area_m2 = float(veh["L_m"]) * usable_width_m

# -----------------------
# LOAD INPUTS
# -----------------------
st.subheader("Load inputs")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    door_qty = st.number_input("Door quantity", min_value=0.0, value=0.0, step=1.0)
    doors_upright_required = st.checkbox("Doors require upright stillages", value=True)

with col2:
    large_pallet_qty = st.number_input("Large pallet quantity (1200×3000)", min_value=0.0, value=0.0, step=1.0)

with col3:
    double_stack_pallets = st.checkbox("Double-stack pallets (2-high)", value=False)

# -----------------------
# CONVERT LOAD
# -----------------------
door_stillages = int(math.ceil(float(door_qty) / float(DOORS_PER_STILLAGE))) if DOORS_PER_STILLAGE > 0 else 0

# Floor pallets shown/used for floor space when stacking is enabled
pallet_floor_qty = float(large_pallet_qty)
if double_stack_pallets:
    pallet_floor_qty = float(math.ceil(pallet_floor_qty / 2.0))

# Separate floor-units so the detail table matches utilisation when stacking is ON
door_floor_units = float(door_stillages)
pallet_floor_units = float(pallet_floor_qty)

# Detail lines:
# - weight/cube on FULL pallet count
# - floor m² uses floor_units (stacking affects pallets only)
lines = pd.DataFrame(
    [
        {
            "item": "Doors (in stillages)",
            "qty": float(door_qty),
            "load_units": float(door_stillages),   # weight/cube units
            "floor_units": door_floor_units,       # floor-space units
            "unit_type": "stillage",
            "footprint_m2_per_unit": float(STILLAGE_AREA_M2),
            "weight_per_unit_kg": float(DOOR_STILLAGE_WEIGHT_KG),
            "vol_per_unit_m3": float(DOOR_STILLAGE_CUBE_M3),
            "upright_required": bool(doors_upright_required),
        },
        {
            "item": "Large pallets (1200×3000)",
            "qty": float(large_pallet_qty),
            "load_units": float(large_pallet_qty),  # full pallets for weight/cube
            "floor_units": pallet_floor_units,      # stacked floor footprint
            "unit_type": "pallet",
            "footprint_m2_per_unit": float(PALLET_AREA_M2),
            "weight_per_unit_kg": float(LARGE_PALLET_WEIGHT_KG),
            "vol_per_unit_m3": float(LARGE_PALLET_CUBE_M3),
            "upright_required": False,
        },
    ]
)

lines["total_floor_m2"] = lines["floor_units"] * lines["footprint_m2_per_unit"]
lines["total_weight_kg"] = lines["load_units"] * lines["weight_per_unit_kg"]
lines["total_vol_m3"] = lines["load_units"] * lines["vol_per_unit_m3"]

# Totals (weight/cube on full pallets)
total_weight = float(lines["total_weight_kg"].sum())
total_cube = float(lines["total_vol_m3"].sum())

needs_upright = bool((lines["upright_required"] & (lines["load_units"] > 0)).any())
upright_ok = (not needs_upright) or bool(veh.get("doors_upright_allowed", True))

# -----------------------
# UTILISATION (FLOOR SPACE FOCUS)
# -----------------------
floor_area_m2 = float(usable_floor_area_m2)  # usable (accounts for optional dead space)
cube_cap = float(veh["cube_cap_m3"]) if float(veh["cube_cap_m3"]) else 0.0
payload_cap = float(veh["payload_kg"]) if float(veh["payload_kg"]) else 0.0

# Floor used m² (stacking affects pallets only)
floor_used_m2 = float(door_stillages) * float(STILLAGE_AREA_M2) + float(pallet_floor_qty) * float(PALLET_AREA_M2)

floor_util = (floor_used_m2 / floor_area_m2) if floor_area_m2 else 0.0
cube_util = (total_cube / cube_cap) if cube_cap else 0.0
weight_util = (total_weight / payload_cap) if payload_cap else 0.0

utils = {"Floor space (m²)": floor_util, "Cube": cube_util, "Weight": weight_util}
limiting = max(utils, key=utils.get)
overall = max(utils.values())

# Remaining space (area-based guidance)
remaining_m2 = max(0.0, floor_area_m2 - floor_used_m2)
remaining_pallet_positions = int(math.floor(remaining_m2 / PALLET_AREA_M2)) if PALLET_AREA_M2 else 0
remaining_stillages = int(math.floor(remaining_m2 / STILLAGE_AREA_M2)) if STILLAGE_AREA_M2 else 0

# -----------------------
# OUTPUTS
# -----------------------
st.subheader("Load utilisation")

c1, c2, c3, c4 = st.columns([1.6, 1, 1, 1])

with c1:
    st.metric("Overall utilisation (limiting)", f"{overall*100:.0f}%", f"Limiting: {limiting}")
    st.write(f"Status: **{traffic_label(overall)}**")
    if not upright_ok:
        st.error("Not allowed: this load requires upright door stillages, and this vehicle cannot take them.")
    if double_stack_pallets and large_pallet_qty > 0:
        st.caption("Note: floor-space utilisation and visual reflect double-stacking pallets; weight/cube remain unstacked.")
    if dead_space_enabled:
        st.caption("Hub multi-drop mode: usable width reduced by 0.50m for dead space down the vehicle length.")

with c2:
    st.write("Floor space utilisation (m²)")
    st.progress(min(floor_util, 1.0))
    cap_line = f"{floor_used_m2:.1f} / {floor_area_m2:.1f} m² ({floor_util*100:.0f}%)"
    if dead_space_enabled:
        cap_line += f"  |  Usable width: {usable_width_m:.2f} m (−{DEAD_SPACE_GAP_M:.2f} m)"
    st.caption(cap_line)

    st.write("Remaining usable floor space")
    if double_stack_pallets:
        st.caption(
            f"{remaining_m2:.1f} m² remaining  |  ≈ {remaining_pallet_positions} pallet position(s) "
            f"(≈ up to {remaining_pallet_positions*2} pallets if 2-high) or {remaining_stillages} stillage(s)"
        )
    else:
        st.caption(
            f"{remaining_m2:.1f} m² remaining  |  ≈ {remaining_pallet_positions} pallet(s) or {remaining_stillages} stillage(s)"
        )

with c3:
    st.write("Cube utilisation (m³)")
    st.progress(min(cube_util, 1.0))
    st.caption(f"{total_cube:.1f} / {cube_cap:.1f} m³ ({cube_util*100:.0f}%)")

with c4:
    st.write("Weight utilisation (kg)")
    st.progress(min(weight_util, 1.0))
    st.caption(f"{total_weight:.0f} / {payload_cap:.0f} kg ({weight_util*100:.0f}%)")

# -----------------------
# WAGON FLOOR BLOCK VISUAL (approx pallet grid)
# -----------------------
st.subheader("Wagon floor layout")

vc1, vc2, vc3 = st.columns([1, 1, 2])
with vc1:
    width_pallets = st.selectbox("Wagon width (pallets)", [1, 2, 3], index=1)
with vc2:
    fill_order = st.selectbox("Fill order", ["Doors then pallets", "Pallets then doors"], index=0)
with vc3:
    st.caption("Block layout visual with labels (simple layout, not a full packing optimiser).")

# Visual capacity is pallet-equivalent derived from USABLE floor area (m²)
pallet_cap_equiv = (floor_area_m2 / PALLET_AREA_M2) if PALLET_AREA_M2 else 0.0

html = build_floor_blocks_html(
    pallet_cap_equiv=float(pallet_cap_equiv),
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
            "floor_units",
            "unit_type",
            "footprint_m2_per_unit",
            "total_floor_m2",
            "total_weight_kg",
            "total_vol_m3",
        ]
    ],
    use_container_width=True,
)

st.caption("Deployment: requirements.txt should contain `streamlit` and `pandas`.")
