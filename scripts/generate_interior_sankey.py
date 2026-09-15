"""Comprehensive Publication & Interactive Sankey Visualizations of Interior Ministry State Colonization (1957-2026).

Visualizes:
1. Panel A: Macro Infiltration Pipeline (Origin Corps -> Target Sector -> Power Lever Captured)
2. Panel B: Regime Reallocation Flow (Presidential Eras -> Target Sectors -> Gatekeeper Levers)
3. Panel C: The Governor Trampoline (Governors -> Destination Ministries -> Executive Power Offices)

Outputs:
- figures/fig_theory_08_interior_sankey.png (300 DPI)
- figures/fig_theory_08_interior_sankey.pdf (Vector)
- figures/fig_theory_08_interior_sankey_interactive.html (Interactive 4-View Plotly Dashboard)
"""

import os
import json
import shutil
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
ARTIFACT_DIR = Path("/Users/mohameddhiahammami/.gemini/antigravity/brain/99a2df6e-0c03-4b60-92f6-cae4ddbbee51")

os.environ["MPLCONFIGDIR"] = str(ROOT / ".matplotlib")
(ROOT / ".matplotlib").mkdir(exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
import matplotlib.patches as patches
import numpy as np
import pandas as pd

# Color Palette
PAPER = "#FCFCFB"
INK = "#1A1917"
MUTED = "#6C6D64"
RULE = "#D3D0C7"
LIGHT_BG = "#F4F3EF"

# Distinct Palettes
ORIGIN_COLORS = {
    "Central Interior Cadres": "#A03B2C",          # Crimson Red
    "Governors & Regional Execs": "#1B5FC1",       # Royal Blue
    "Delegates & Field Admin": "#B5852A",          # Ochre Gold
    "Police & Paramilitary": "#1E7E68",            # Emerald Teal
}

SECTOR_COLORS = {
    "Finance & Economy": "#2563EB",
    "Education & Higher Ed": "#0D9488",
    "Local Affairs & Envir.": "#16A34A",
    "Health & Social Affairs": "#D97706",
    "Prime Ministry / Kasbah": "#DC2626",
    "Transport & Public Works": "#9333EA",
    "Agriculture & Water": "#65A30D",
    "Foreign Affairs": "#0284C7",
    "Other Line Ministries": "#64748B",
}

ROLE_COLORS = {
    "Ministers & Cabinets": "#DC2626",
    "SG & DAF Gatekeepers": "#B5852A",
    "Central Directors Gen.": "#1B5FC1",
    "SOE Boards & PDGs": "#1E7E68",
    "Diplomatic Posts": "#6B46C1",
    "Operational Directors": "#94A3B8",
}

REGIME_COLORS = {
    "1. Bourguiba (1957–87)": "#A03B2C",
    "2. Ben Ali (1987–2011)": "#1B5FC1",
    "3. Transition (2011–14)": "#B5852A",
    "4. Essebsi (2014–19)": "#1E7E68",
    "5. Kais Saied (2019–26)": "#6B46C1",
}


def load_data():
    print("Loading spells data...")
    spells = pd.read_csv(PROC / "spells.csv.gz", low_memory=False)
    spells["start_dt"] = pd.to_datetime(spells["start_date"], errors="coerce")
    spells = spells[spells.start_dt.notna() & (spells.rank_score > 0)].sort_values(["person_id", "start_dt"]).reset_index(drop=True)

    def get_presidency(d):
        d_str = str(d)[:10]
        if d_str < "1987-11-07": return "1. Bourguiba (1957–87)"
        elif d_str < "2011-01-14": return "2. Ben Ali (1987–2011)"
        elif d_str < "2014-12-31": return "3. Transition (2011–14)"
        elif d_str < "2019-10-23": return "4. Essebsi (2014–19)"
        else: return "5. Kais Saied (2019–26)"

    spells["presidency"] = spells["start_date"].map(get_presidency)

    p_org = spells["parent_org_name"].fillna("").str.lower()
    org = spells["org_name"].fillna("").str.lower()
    pos = spells["position_clean"].fillna("").str.lower()

    is_interior = (
        p_org.str.contains(r"minist[eè]re de l\'int[eé]rieur|secr[eé]tariat d\'[eé]tat [aà] l\'int[eé]rieur|direction g[eé]n[eé]rale de la s[uû]ret[eé]|garde nationale|protection civile") |
        org.str.contains(r"minist[eè]re de l\'int[eé]rieur|direction g[eé]n[eé]rale de la s[uû]ret[eé]|garde nationale|protection civile|direction des services sp[eé]ciaux|direction de la s[eé]curit[eé] publique") |
        org.str.contains(r"\bgouvernorat de\b|\bd[eé]l[eé]gation de\b") |
        pos.str.contains(r"\bgouverneur\b|\bpremier d[eé]l[eé]gu[eé]\b|\bcommissaire de police\b|\bofficier de police\b")
    )
    spells["is_interior"] = is_interior.astype(int)

    def classify_origin(p, o, po):
        p, o, po = str(p).lower(), str(o).lower(), str(po).lower()
        if "gouverneur" in p or "gouvernorat" in o:
            return "Governors & Regional Execs"
        elif "délégué" in p or "delegue" in p or "délégation" in o or "delegation" in o:
            return "Delegates & Field Admin"
        elif "garde nationale" in po or "garde nationale" in o or "garde nationale" in p:
            return "Police & Paramilitary"
        elif "protection civile" in po or "protection civile" in o or "protection civile" in p:
            return "Police & Paramilitary"
        elif "police" in p or "sûreté" in po or "surete" in po or "sûreté" in o or "surete" in o or "commissaire" in p:
            return "Police & Paramilitary"
        else:
            return "Central Interior Cadres"

    int_spells = spells[spells.is_interior == 1]
    origin_map = int_spells.groupby("person_id").apply(lambda df: classify_origin(df.iloc[0]["position_clean"], df.iloc[0]["org_name"], df.iloc[0]["parent_org_name"])).to_dict()

    first_int_dt = int_spells.groupby("person_id")["start_dt"].min().to_dict()
    spells["first_int_dt"] = spells["person_id"].map(first_int_dt)
    spells["origin_corps"] = spells["person_id"].map(origin_map)

    outbound = spells[
        (spells.person_id.isin(first_int_dt.keys())) &
        (spells.start_dt > spells.first_int_dt) &
        (spells.is_interior == 0)
    ].copy()

    # Destination Sector
    def classify_dest_sector(row):
        p_org = str(row["parent_org_name"]).lower()
        org = str(row["org_name"]).lower()
        full = p_org + " " + org
        if "premier minist" in full or "gouvernement" in full or "kasbah" in full:
            return "Prime Ministry / Kasbah"
        elif "financ" in full or "domaine" in full or "plan" in full or "dév" in full:
            return "Finance & Economy"
        elif "local" in full or "environnement" in full or "collectivit" in full or "commun" in full:
            return "Local Affairs & Envir."
        elif "éduc" in full or "educ" in full or "enseign" in full or "universit" in full or "recherche" in full:
            return "Education & Higher Ed"
        elif "sant" in full or "social" in full or "affair" in full and ("social" in full):
            return "Health & Social Affairs"
        elif "transport" in full or "équip" in full or "equip" in full or "habitat" in full:
            return "Transport & Public Works"
        elif "agri" in full or "hydraul" in full:
            return "Agriculture & Water"
        elif "étrang" in full or "etrang" in full:
            return "Foreign Affairs"
        else:
            return "Other Line Ministries"

    outbound["dest_sector"] = outbound.apply(classify_dest_sector, axis=1)

    # Role Tier
    def classify_role_tier(row):
        pos = str(row["position_clean"]).lower()
        r = row["rank_score"]
        if r >= 90 or "ministre" in pos or "secrétaire d'etat" in pos:
            return "Ministers & Cabinets"
        elif "chef de cabinet" in pos or "charge de mission" in pos or "chargé de mission" in pos or "conseiller" in pos:
            return "Ministers & Cabinets"
        elif "secrétaire général" in pos or "secretaire general" in pos or "affaires administratives et financières" in pos or "daaf" in pos or "dgsc" in pos:
            return "SG & DAF Gatekeepers"
        elif "président-directeur" in pos or "pdg" in pos or ("directeur général" in pos and any(k in pos for k in ["société", "office", "agence", "banque"])):
            return "SOE Boards & PDGs"
        elif "administrateur représentant" in pos or "représentant de l'etat" in pos or "membre du conseil" in pos:
            return "SOE Boards & PDGs"
        elif "ambassadeur" in pos or "consul" in pos or "mission permanente" in pos:
            return "Diplomatic Posts"
        elif "directeur général" in pos or "directeur general" in pos or r >= 65:
            return "Central Directors Gen."
        else:
            return "Operational Directors"

    outbound["role_tier"] = outbound.apply(classify_role_tier, axis=1)

    return outbound


def draw_sankey_layer(ax, layers_nodes, flows, colors, x_coords=None, node_width=0.032, gap=2.2, total_height=92.0, alpha=0.35, text_fontsize=8.0):
    """
    Renders an exact, pristine multi-layer Sankey diagram with cubic Bézier ribbons and clean label spacing.
    """
    num_layers = len(layers_nodes)
    if x_coords is None:
        x_coords = np.linspace(0.12, 0.88, num_layers)

    # 1. Flow totals
    node_out_totals = {n: 0.0 for layer in layers_nodes for n in layer}
    node_in_totals = {n: 0.0 for layer in layers_nodes for n in layer}
    for (u, v), w in flows.items():
        if u in node_out_totals: node_out_totals[u] += w
        if v in node_in_totals: node_in_totals[v] += w

    node_totals = {}
    for layer_idx, layer in enumerate(layers_nodes):
        for n in layer:
            if layer_idx == 0:
                node_totals[n] = node_out_totals[n]
            elif layer_idx == num_layers - 1:
                node_totals[n] = node_in_totals[n]
            else:
                node_totals[n] = max(node_in_totals[n], node_out_totals[n])

    grand_total = sum(node_totals[n] for n in layers_nodes[0])

    # 2. Position nodes vertically
    node_pos = {} # n -> (x_l, x_r, y_b, y_t)
    for layer_idx, layer in enumerate(layers_nodes):
        x = x_coords[layer_idx]
        total_val = sum(node_totals[n] for n in layer)
        n_nodes = len(layer)
        avail_height = total_height - (n_nodes - 1) * gap
        scale = avail_height / total_val if total_val > 0 else 1.0

        current_y = 0.0
        # draw from bottom to top
        for n in reversed(layer):
            h = node_totals[n] * scale
            node_pos[n] = (x - node_width/2, x + node_width/2, current_y, current_y + h)
            current_y += h + gap

    # 3. Offsets for ribbons
    source_offsets = {n: node_pos[n][2] for layer in layers_nodes for n in layer}
    target_offsets = {n: node_pos[n][2] for layer in layers_nodes for n in layer}

    # Draw ribbons
    for layer_idx in range(num_layers - 1):
        curr_layer = layers_nodes[layer_idx]
        next_layer = layers_nodes[layer_idx + 1]

        layer_flows = []
        for u in reversed(curr_layer):
            for v in reversed(next_layer):
                if (u, v) in flows and flows[(u, v)] > 0:
                    layer_flows.append((u, v, flows[(u, v)]))

        for u, v, w in layer_flows:
            x0 = node_pos[u][1] # right edge of source
            x1 = node_pos[v][0] # left edge of target

            u_total = max(node_out_totals[u], 1e-9)
            u_node_h = node_pos[u][3] - node_pos[u][2]
            flow_h_u = (w / u_total) * u_node_h
            y0_bot = source_offsets[u]
            y0_top = y0_bot + flow_h_u
            source_offsets[u] = y0_top

            v_total = max(node_in_totals[v], 1e-9)
            v_node_h = node_pos[v][3] - node_pos[v][2]
            flow_h_v = (w / v_total) * v_node_h
            y1_bot = target_offsets[v]
            y1_top = y1_bot + flow_h_v
            target_offsets[v] = y1_top

            dx = x1 - x0
            verts = [
                (x0, y0_bot),
                (x0, y0_top),
                (x0 + 0.5 * dx, y0_top),
                (x1 - 0.5 * dx, y1_top),
                (x1, y1_top),
                (x1, y1_bot),
                (x1 - 0.5 * dx, y1_bot),
                (x0 + 0.5 * dx, y0_bot),
                (x0, y0_bot),
            ]
            codes = [
                MPath.MOVETO,
                MPath.LINETO,
                MPath.CURVE4,
                MPath.CURVE4,
                MPath.CURVE4,
                MPath.LINETO,
                MPath.CURVE4,
                MPath.CURVE4,
                MPath.CURVE4,
            ]
            path = MPath(verts, codes)
            ribbon_color = colors.get(u, colors.get(v, "#64748B"))
            patch = patches.PathPatch(path, facecolor=ribbon_color, edgecolor="none", alpha=alpha, zorder=2)
            ax.add_patch(patch)

    # 4. Draw nodes & labels
    for layer_idx, layer in enumerate(layers_nodes):
        x = x_coords[layer_idx]
        # Collect ideal label positions
        labels_info = []
        for n in layer:
            x_l, x_r, y_b, y_t = node_pos[n]
            node_h = y_t - y_b
            val = int(node_totals[n])
            pct = (val / grand_total) * 100 if grand_total > 0 else 0
            color = colors.get(n, "#4A5568")

            # Node rectangle
            rect = patches.Rectangle((x_l, y_b), x_r - x_l, node_h, facecolor=color, edgecolor=INK, linewidth=0.8, zorder=5)
            ax.add_patch(rect)

            mid_y = y_b + node_h / 2
            labels_info.append({
                "name": n,
                "val": val,
                "pct": pct,
                "mid_y": mid_y,
                "node_h": node_h,
                "x_l": x_l,
                "x_r": x_r,
                "color": color
            })

        # Smart label placement to prevent collisions
        min_dist = 6.2
        labels_info.sort(key=lambda item: item["mid_y"])
        adjusted_y = [item["mid_y"] for item in labels_info]
        
        # Forward pass: push overlapping labels upward
        for i in range(1, len(adjusted_y)):
            if adjusted_y[i] - adjusted_y[i-1] < min_dist:
                adjusted_y[i] = adjusted_y[i-1] + min_dist

        # Backward pass: if top labels exceed bounds, push downward
        max_allowed_y = total_height + 2.0
        if len(adjusted_y) > 0 and adjusted_y[-1] > max_allowed_y:
            excess = adjusted_y[-1] - max_allowed_y
            adjusted_y[-1] = max_allowed_y
            for i in range(len(adjusted_y) - 2, -1, -1):
                if adjusted_y[i+1] - adjusted_y[i] < min_dist:
                    adjusted_y[i] = adjusted_y[i+1] - min_dist

        for i, item in enumerate(labels_info):
            n = item["name"]
            val = item["val"]
            pct = item["pct"]
            orig_y = item["mid_y"]
            y_target = adjusted_y[i]

            if layer_idx == 0:
                # Left side
                ax.text(item["x_l"] - 0.016, y_target, f"{n}\n{val:,} ({pct:.1f}%)",
                        ha="right", va="center", fontsize=text_fontsize, fontweight="semibold", color=INK)
                if abs(y_target - orig_y) > 1.2:
                    ax.plot([item["x_l"] - 0.004, item["x_l"] - 0.014], [orig_y, y_target],
                            color=MUTED, linewidth=0.7, alpha=0.7, zorder=4)
            elif layer_idx == num_layers - 1:
                # Right side
                if item["node_h"] < 5.0 or text_fontsize < 7.5:
                    lbl = f"{n}: {val:,} ({pct:.1f}%)"
                else:
                    lbl = f"{n}\n{val:,} ({pct:.1f}%)"
                ax.text(item["x_r"] + 0.016, y_target, lbl,
                        ha="left", va="center", fontsize=text_fontsize, fontweight="semibold", color=INK)
                if abs(y_target - orig_y) > 0.8:
                    ax.plot([item["x_r"] + 0.004, item["x_r"] + 0.014], [orig_y, y_target],
                            color=MUTED, linewidth=0.7, alpha=0.7, zorder=4)
            else:
                # Middle column: label placed to the right or left
                label_txt = f"{n} ({val:,})"
                ax.text(item["x_r"] + 0.010, orig_y, label_txt,
                        ha="left", va="center", fontsize=text_fontsize - 0.7, color=INK, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", facecolor=PAPER, edgecolor="none", alpha=0.75))


def create_static_sankey_figure(outbound):
    print("Generating static publication figure...")
    fig = plt.figure(figsize=(17, 13), facecolor=PAPER)

    # Layout: Top Panel A (Macro Pipeline), Bottom Panels B & C
    gs = fig.add_gridspec(2, 2, height_ratios=[1.35, 1.0], hspace=0.34, wspace=0.25)
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])

    for ax in [ax_a, ax_b, ax_c]:
        ax.set_facecolor(PAPER)
        ax.axis("off")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-6, 106)

    # ==================== PANEL A: MACRO PIPELINE ====================
    layer0 = ["Central Interior Cadres", "Governors & Regional Execs", "Delegates & Field Admin", "Police & Paramilitary"]
    layer1 = [
        "Finance & Economy", "Education & Higher Ed", "Local Affairs & Envir.",
        "Health & Social Affairs", "Prime Ministry / Kasbah", "Transport & Public Works",
        "Agriculture & Water", "Foreign Affairs", "Other Line Ministries"
    ]
    layer2 = [
        "Operational Directors", "Ministers & Cabinets", "SG & DAF Gatekeepers",
        "Central Directors Gen.", "SOE Boards & PDGs", "Diplomatic Posts"
    ]

    flows_a = {}
    ct_01 = pd.crosstab(outbound["origin_corps"], outbound["dest_sector"])
    for u in layer0:
        for v in layer1:
            if u in ct_01.index and v in ct_01.columns:
                flows_a[(u, v)] = ct_01.loc[u, v]

    ct_12 = pd.crosstab(outbound["dest_sector"], outbound["role_tier"])
    for v in layer1:
        for w in layer2:
            if v in ct_12.index and w in ct_12.columns:
                flows_a[(v, w)] = ct_12.loc[v, w]

    palette_a = {}
    palette_a.update(ORIGIN_COLORS)
    palette_a.update(SECTOR_COLORS)
    palette_a.update(ROLE_COLORS)

    draw_sankey_layer(ax_a, [layer0, layer1, layer2], flows_a, palette_a,
                      x_coords=[0.19, 0.49, 0.81], node_width=0.024, gap=2.0, total_height=92.0, text_fontsize=8.0)

    # Stage Headers
    ax_a.text(0.19, 100, "STAGE 1: ORIGIN CORPS\nIN INTERIOR APPARATUS", ha="center", va="bottom", fontsize=8.8, fontweight="bold", color=INK)
    ax_a.text(0.49, 100, "STAGE 2: DESTINATION\nCIVILIAN DOMAIN / SECTOR", ha="center", va="bottom", fontsize=8.8, fontweight="bold", color=INK)
    ax_a.text(0.81, 100, "STAGE 3: HIERARCHICAL\nPOWER LEVER CAPTURED", ha="center", va="bottom", fontsize=8.8, fontweight="bold", color=INK)

    ax_a.set_title("A. The Macro Colonization Pipeline: From Interior Corps to Civilian Sectors & Power Levers (1957–2026)\n"
                   "   Tracing N = 11,255 outbound appointments held by 3,449 former Interior cadres across non-interior state institutions",
                   fontsize=11.2, fontweight="bold", pad=28, color=INK, loc="left")

    # ==================== PANEL B: REGIME REALLOCATION ====================
    layer_b0 = [
        "1. Bourguiba (1957–87)", "2. Ben Ali (1987–2011)", "3. Transition (2011–14)",
        "4. Essebsi (2014–19)", "5. Kais Saied (2019–26)"
    ]
    layer_b1 = [
        "Prime Ministry / Kasbah", "Finance & Economy", "Education & Higher Ed",
        "Local Affairs & Envir.", "Health & Social Affairs", "Other Line Ministries"
    ]
    def role_b_group(r):
        if r in ["Ministers & Cabinets", "SG & DAF Gatekeepers"]: return "Cabinets & Gatekeeper SGs"
        elif r in ["SOE Boards & PDGs", "Diplomatic Posts"]: return "SOE Boards & Diplomacy"
        elif r == "Central Directors Gen.": return "Central Directors General"
        else: return "Operational Line Directors"

    outbound["role_group_b"] = outbound["role_tier"].map(role_b_group)
    layer_b2 = [
        "Operational Line Directors", "Central Directors General",
        "Cabinets & Gatekeeper SGs", "SOE Boards & Diplomacy"
    ]

    flows_b = {}
    ct_b01 = pd.crosstab(outbound["presidency"], outbound["dest_sector"])
    for u in layer_b0:
        for v in layer_b1:
            if u in ct_b01.index and v in ct_b01.columns:
                flows_b[(u, v)] = ct_b01.loc[u, v]

    ct_b12 = pd.crosstab(outbound["dest_sector"], outbound["role_group_b"])
    for v in layer_b1:
        for w in layer_b2:
            if v in ct_b12.index and w in ct_b12.columns:
                flows_b[(v, w)] = ct_b12.loc[v, w]

    palette_b = {}
    palette_b.update(REGIME_COLORS)
    palette_b.update(SECTOR_COLORS)
    palette_b.update({
        "Cabinets & Gatekeeper SGs": "#DC2626",
        "Central Directors General": "#1B5FC1",
        "SOE Boards & Diplomacy": "#1E7E68",
        "Operational Line Directors": "#94A3B8",
    })

    draw_sankey_layer(ax_b, [layer_b0, layer_b1, layer_b2], flows_b, palette_b,
                      x_coords=[0.20, 0.50, 0.81], node_width=0.026, gap=2.3, total_height=90.0, text_fontsize=7.2)

    ax_b.text(0.20, 97, "REGIME ERA", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)
    ax_b.text(0.50, 97, "LANDING SECTOR", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)
    ax_b.text(0.81, 97, "STRATEGIC LEVER", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)

    ax_b.set_title("B. Regime Trajectory: From Bourguiba to Kais Saied (N = 11,255)\n"
                   "   Infiltration surges post-1987 and reaches all-time peak (17.4%) under Kais Saied",
                   fontsize=9.8, fontweight="bold", pad=20, color=INK, loc="left")

    # ==================== PANEL C: THE GOVERNOR TRAMPOLINE ====================
    gov_outbound = outbound[outbound["origin_corps"] == "Governors & Regional Execs"].copy()

    layer_c0 = ["Governors & Regional Execs"]
    layer_c1 = [
        "Finance & Economy", "Prime Ministry / Kasbah", "Education & Higher Ed",
        "Local Affairs & Envir.", "Health & Social Affairs", "Transport & Public Works",
        "Other Line Ministries"
    ]
    layer_c2 = [
        "Operational Directors", "Ministers & Cabinets", "Central Directors Gen.",
        "SG & DAF Gatekeepers", "SOE Boards & PDGs", "Diplomatic Posts"
    ]

    flows_c = {}
    ct_c01 = pd.crosstab(gov_outbound["origin_corps"], gov_outbound["dest_sector"])
    for u in layer_c0:
        for v in layer_c1:
            if u in ct_c01.index and v in ct_c01.columns:
                flows_c[(u, v)] = ct_c01.loc[u, v]

    ct_c12 = pd.crosstab(gov_outbound["dest_sector"], gov_outbound["role_tier"])
    for v in layer_c1:
        for w in layer_c2:
            if v in ct_c12.index and w in ct_c12.columns:
                flows_c[(v, w)] = ct_c12.loc[v, w]

    palette_c = {}
    palette_c.update(ORIGIN_COLORS)
    palette_c.update(SECTOR_COLORS)
    palette_c.update(ROLE_COLORS)

    draw_sankey_layer(ax_c, [layer_c0, layer_c1, layer_c2], flows_c, palette_c,
                      x_coords=[0.20, 0.50, 0.81], node_width=0.026, gap=2.3, total_height=90.0, text_fontsize=7.2)

    ax_c.text(0.20, 97, "ORIGIN CORPS", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)
    ax_c.text(0.50, 97, "TARGET SECTOR", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)
    ax_c.text(0.81, 97, "POWER LEVER", ha="center", va="bottom", fontsize=8.2, fontweight="bold", color=INK)

    ax_c.set_title("C. The Governor Trampoline: Redeployment of Regional Governors (N = 3,379)\n"
                   "   Provincial governors stepping into ministerial cabinets, DGs, and SOE boards",
                   fontsize=9.8, fontweight="bold", pad=20, color=INK, loc="left")

    # Footnote
    fig.text(0.04, 0.015,
             "Source: Journal Officiel de la République Tunisienne (1957–2026). N = 11,255 outbound appointments held by 3,449 former Interior cadres.\n"
             "Outbound spells are defined as appointments held in non-interior civilian institutions following prior service in the Ministry of Interior or Territorial Administration.",
             fontsize=7.5, color=MUTED)

    out_png = FIGS / "fig_theory_08_interior_sankey.png"
    out_pdf = FIGS / "fig_theory_08_interior_sankey.pdf"
    plt.savefig(out_png, dpi=300, bbox_inches="tight", facecolor=PAPER)
    plt.savefig(out_pdf, bbox_inches="tight", facecolor=PAPER)
    plt.close()
    print(f"Saved: {out_png}")
    print(f"Saved: {out_pdf}")

    shutil.copy(out_png, ARTIFACT_DIR / "fig_theory_08_interior_sankey.png")
    shutil.copy(out_pdf, ARTIFACT_DIR / "fig_theory_08_interior_sankey.pdf")
    print(f"Copied to artifact directory: {ARTIFACT_DIR}")


def create_interactive_sankey_html(outbound):
    print("Generating comprehensive interactive Plotly HTML dashboard...")
    
    # Generate data for 4 distinct interactive views
    views_data = {}

    # VIEW 1: Macro Pipeline (Origin -> Sector -> Role Tier)
    def build_sankey_data(df, col0, col1, col2, col_colors):
        nodes = []
        node_indices = {}
        def get_idx(name):
            if name not in node_indices:
                node_indices[name] = len(nodes)
                nodes.append({"name": name, "color": col_colors.get(name, "#4A5568")})
            return node_indices[name]

        sources, targets, values = [], [], []
        # col0 -> col1
        ct1 = pd.crosstab(df[col0], df[col1])
        for u in ct1.index:
            u_i = get_idx(u)
            for v in ct1.columns:
                w = ct1.loc[u, v]
                if w > 0:
                    v_i = get_idx(v)
                    sources.append(u_i)
                    targets.append(v_i)
                    values.append(int(w))
        # col1 -> col2
        ct2 = pd.crosstab(df[col1], df[col2])
        for v in ct2.index:
            v_i = get_idx(v)
            for w in ct2.columns:
                val = ct2.loc[v, w]
                if val > 0:
                    w_i = get_idx(w)
                    sources.append(v_i)
                    targets.append(w_i)
                    values.append(int(val))

        return {
            "node_labels": [n["name"] for n in nodes],
            "node_colors": [n["color"] for n in nodes],
            "sources": sources,
            "targets": targets,
            "values": values
        }

    all_colors = {}
    all_colors.update(ORIGIN_COLORS)
    all_colors.update(SECTOR_COLORS)
    all_colors.update(ROLE_COLORS)
    all_colors.update(REGIME_COLORS)

    views_data["macro"] = build_sankey_data(outbound, "origin_corps", "dest_sector", "role_tier", all_colors)
    views_data["regime"] = build_sankey_data(outbound, "presidency", "dest_sector", "role_tier", all_colors)
    
    gov_df = outbound[outbound["origin_corps"] == "Governors & Regional Execs"]
    views_data["governors"] = build_sankey_data(gov_df, "origin_corps", "dest_sector", "role_tier", all_colors)

    sec_df = outbound[outbound["origin_corps"] == "Police & Paramilitary"]
    views_data["police"] = build_sankey_data(sec_df, "origin_corps", "dest_sector", "role_tier", all_colors)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Interactive Sankey: Interior Ministry Colonization of the Tunisian State (1957–2026)</title>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #FCFCFB;
            color: #1A1917;
            margin: 0;
            padding: 24px;
        }}
        .header {{
            max-width: 1400px;
            margin: 0 auto 16px auto;
            border-bottom: 2px solid #D3D0C7;
            padding-bottom: 14px;
        }}
        h1 {{
            font-size: 23px;
            margin: 0 0 6px 0;
            color: #1A1917;
        }}
        p.subtitle {{
            font-size: 13.5px;
            color: #6C6D64;
            margin: 0;
            line-height: 1.5;
        }}
        .controls {{
            max-width: 1400px;
            margin: 0 auto 16px auto;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .btn {{
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            padding: 8px 14px;
            border-radius: 5px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
            color: #1A1917;
        }}
        .btn:hover {{
            background: #F4F3EF;
            border-color: #6C6D64;
        }}
        .btn.active {{
            background: #1B5FC1;
            color: #FFFFFF;
            border-color: #1B5FC1;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            max-width: 1400px;
            margin: 0 auto 18px auto;
        }}
        .card {{
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            border-radius: 6px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .card-num {{
            font-size: 20px;
            font-weight: bold;
            color: #A03B2C;
            margin-bottom: 3px;
        }}
        .card-label {{
            font-size: 11.5px;
            color: #6C6D64;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        #sankey-container {{
            max-width: 1400px;
            height: 720px;
            margin: 0 auto;
            background: #FFFFFF;
            border: 1px solid #D3D0C7;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }}
        .footer {{
            max-width: 1400px;
            margin: 16px auto;
            font-size: 12px;
            color: #6C6D64;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Colonization of the Civilian State Apparatus by Former Interior Employees (1957–2026)</h1>
        <p class="subtitle">Interactive Sankey Flow: Tracing N = 11,255 outbound appointments held by 3,449 former Interior cadres from Origin Corps to Target Ministries and Power Levers</p>
    </div>

    <div class="stats-grid">
        <div class="card">
            <div class="card-num">11,255</div>
            <div class="card-label">Outbound Civilian Spells</div>
        </div>
        <div class="card">
            <div class="card-num">3,449</div>
            <div class="card-label">Unique Former Interior Cadres</div>
        </div>
        <div class="card">
            <div class="card-num">17.43%</div>
            <div class="card-label">Peak Colonization Rate (Saied)</div>
        </div>
        <div class="card">
            <div class="card-num">3,379 (30.0%)</div>
            <div class="card-label">Governor-to-Center Spells</div>
        </div>
    </div>

    <div class="controls">
        <span style="font-size: 13px; font-weight: 600; color: #1A1917;">Select Sankey Flow:</span>
        <button class="btn active" onclick="switchView('macro')">1. Macro Infiltration Pipeline</button>
        <button class="btn" onclick="switchView('regime')">2. Regime Trajectory (Presidencies)</button>
        <button class="btn" onclick="switchView('governors')">3. The Governor Trampoline</button>
        <button class="btn" onclick="switchView('police')">4. Police & Paramilitary Security</button>
    </div>

    <div id="sankey-container"></div>

    <div class="footer">
        <strong>Methodological Grounding:</strong> Extracted from complete 70-year JORT gazette records (1957–2026). Outbound spells represent appointments held in civilian ministries, public establishments, and state enterprises by individuals who previously served in the Ministry of the Interior, national security directorates, or territorial administration.
    </div>

    <script>
        const viewsData = {json.dumps(views_data)};

        function renderSankey(viewKey) {{
            const d = viewsData[viewKey];
            const fig = {{
                type: "sankey",
                orientation: "h",
                node: {{
                    pad: 20,
                    thickness: 24,
                    line: {{ color: "#1A1917", width: 0.8 }},
                    label: d.node_labels,
                    color: d.node_colors
                }},
                link: {{
                    source: d.sources,
                    target: d.targets,
                    value: d.values,
                    color: d.sources.map(s => d.node_colors[s] + "55")
                }}
            }};

            const layout = {{
                font: {{
                    family: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                    size: 11.5,
                    color: "#1A1917"
                }},
                margin: {{ l: 30, r: 30, t: 25, b: 25 }},
                paper_bgcolor: "#FFFFFF",
                plot_bgcolor: "#FFFFFF"
            }};

            Plotly.newPlot("sankey-container", [fig], layout, {{ responsive: true }});
        }}

        function switchView(viewKey) {{
            document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            renderSankey(viewKey);
        }}

        renderSankey('macro');
    </script>
</body>
</html>
"""
    out_html = FIGS / "fig_theory_08_interior_sankey_interactive.html"
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved: {out_html}")
    shutil.copy(out_html, ARTIFACT_DIR / "fig_theory_08_interior_sankey_interactive.html")
    print(f"Copied to artifact directory: {ARTIFACT_DIR}")


def main():
    outbound = load_data()
    create_static_sankey_figure(outbound)
    create_interactive_sankey_html(outbound)
    print("All Sankey visualizations completed!")


if __name__ == "__main__":
    main()
