#!/usr/bin/env python3
"""
manhattan_plot_core.py
--------------------------------------------------
Core backend for the Manhattan Plot Generator.

Includes:
- Config defaults (editable from GUI)
- Dependency auto-install
- Coordinate fetching (cache → MyGene.info → Ensembl REST)
- Detailed logging
- Column normalization, control filtering
- Hit classification
- Publication-quality plotting (Matplotlib)
- Safe color parsing for RGBA values
"""

# ======================================================================
# Configuration defaults
# ======================================================================

DEFAULT_LOG2FC_THRESHOLD = 0.3
DEFAULT_PVAL_THRESHOLD   = 0.03

# Marker appearance
MARKER_SIZE       = 40
MARKER_EDGE_ALPHA = 0.9
NON_HIT_COLOR     = "#d9d9d9"
PARTIAL_HIT_COLOR = "lightgray"
EDGE_COLOR        = "white"

# Chromosome background bands
BAND_OPACITY     = 0.03
BAND_COLOR_EVEN  = (0.0, 1.0, 0.0, BAND_OPACITY)   # green 3%
BAND_COLOR_ODD   = (1.0, 0.0, 1.0, BAND_OPACITY)   # magenta 3%

# Labels
LABEL_FONT_SIZE  = 8
LABEL_OFFSET     = 0.1
LABEL_COLOR_HIT  = "black"

# Figure
FIG_SIZE        = (14, 7)
TITLE_FONT_SIZE = 12
TITLE_PADDING   = 20
SAVE_PATH       = "manhattan_plot_gui.png"

# Files
CACHE_FILE = "gene_coordinates_cache.csv"
LOG_FILE   = "coordinate_fetch_log.txt"

# Run modes
TEST_MODE      = False
TEST_LIMIT     = 50
USE_CACHE_ONLY = False

# ======================================================================
# Dependency auto-install
# ======================================================================

import subprocess, sys, importlib.util
_required = [
    "pandas", "matplotlib", "numpy", "adjustText",
    "openpyxl", "mygene", "requests", "tqdm", "tk"
]
for _pkg in _required:
    if _pkg == "tk":
        continue
    if importlib.util.find_spec(_pkg) is None:
        print(f"📦 Installing missing package: {_pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", _pkg])

# ======================================================================
# Imports
# ======================================================================

import os, time
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from adjustText import adjust_text
import mygene, requests
from tqdm import tqdm

__all__ = [
    "DEFAULT_LOG2FC_THRESHOLD", "DEFAULT_PVAL_THRESHOLD",
    "MARKER_SIZE", "MARKER_EDGE_ALPHA", "NON_HIT_COLOR", "PARTIAL_HIT_COLOR",
    "EDGE_COLOR", "BAND_OPACITY", "BAND_COLOR_EVEN", "BAND_COLOR_ODD",
    "LABEL_FONT_SIZE", "LABEL_OFFSET", "LABEL_COLOR_HIT", "FIG_SIZE",
    "TITLE_FONT_SIZE", "TITLE_PADDING", "SAVE_PATH", "CACHE_FILE", "LOG_FILE",
    "TEST_MODE", "TEST_LIMIT", "USE_CACHE_ONLY",
    "log_write", "normalize_column_names", "fetch_gene_coordinates",
    "load_data", "classify_genes", "compute_chromosome_positions",
    "plot_manhattan", "plt"
]

# ======================================================================
# Utilities
# ======================================================================

def log_write(message):
    """Append timestamped message to log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

def _parse_rgba(value):
    """Convert '0.1,0.2,0.3,0.4' or '(0.1,0.2,0.3,0.4)' → tuple."""
    if isinstance(value, str):
        try:
            return tuple(float(x.strip()) for x in value.strip("() ").split(","))
        except Exception:
            pass
    return value

# ======================================================================
# Column normalization
# ======================================================================

def normalize_column_names(columns):
    mapping = {
        "genesymbol": "gene", "symbol": "gene", "geneid": "gene", "genename": "gene",
        "log2ratio": "log2fc", "foldchange": "log2fc", "ratio": "log2fc", "log2foldchange": "log2fc",
        "pvalue": "p-value", "pval": "p-value", "p": "p-value"
    }
    norm = []
    for c in columns:
        key = c.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
        norm.append(mapping.get(key, key))
    return norm

# ======================================================================
# Coordinate fetching
# ======================================================================

def fetch_gene_coordinates(gene_list, species="human"):
    """Fetch genomic coordinates using cache → MyGene.info → Ensembl."""
    gene_list = [str(g).strip() for g in gene_list if isinstance(g, str) and g.strip()]

    if TEST_MODE and len(gene_list) > TEST_LIMIT:
        print(f"🧪 TEST MODE: Only retrieving first {TEST_LIMIT} genes.")
        gene_list = gene_list[:TEST_LIMIT]

    print(f"🔎 Total input genes: {len(gene_list)}")
    log_write(f"--- Fetching coordinates for {len(gene_list)} genes ---")

    cache = pd.DataFrame(columns=["gene","chromosome","start_position","end_position"])
    if os.path.exists(CACHE_FILE):
        cache = pd.read_csv(CACHE_FILE)
        cache["gene"] = cache["gene"].astype(str)
        print(f"📂 Loaded {len(cache)} cached coordinates from {CACHE_FILE}")
    cached = set(cache["gene"].unique())
    missing = [g for g in gene_list if g not in cached]
    coords = cache.copy()

    if USE_CACHE_ONLY:
        print("💾 CACHE-ONLY MODE: Skipping online queries.")
        log_write("CACHE-ONLY mode enabled.")
        if missing:
            print(f"⚠️ {len(missing)} genes not in cache.")
        return coords

    # MyGene.info
    mg_results, missing_summary = [], []
    duplicates = 0
    if missing:
        print(f"🧬 Querying MyGene.info for {len(missing)} genes...")
        mg = mygene.MyGeneInfo()
        try:
            res = mg.querymany(missing, scopes="symbol", fields="genomic_pos",
                               species=species, as_dataframe=False)
        except Exception as e:
            print(f"⚠️ MyGene.info query failed: {e}")
            res = []

        found = 0
        for e in res:
            gene = e.get("query")
            if e.get("notfound", False):
                missing_summary.append((gene, "not found"))
                continue
            pos = e.get("genomic_pos")
            if pos is None:
                missing_summary.append((gene, "no genomic_pos"))
                continue
            found += 1
            if isinstance(pos, list):
                duplicates += 1
                pos = pos[0]
            mg_results.append({
                "gene": gene,
                "chromosome": pos.get("chr"),
                "start_position": pos.get("start"),
                "end_position": pos.get("end")
            })

        df_mg = pd.DataFrame(mg_results).dropna()
        retrieved = set(df_mg["gene"].unique()) if not df_mg.empty else set()
        missing_after = [g for g in missing if g not in retrieved]
        print(f"✅ MyGene.info found {found} (duplicates: {duplicates}), {len(missing_after)} still missing.")
    else:
        df_mg = pd.DataFrame()
        missing_after = []

    # Ensembl fallback
    ensembl_coords = []
    if missing_after:
        print(f"🌐 Querying Ensembl REST API for {len(missing_after)} genes...")
        headers = {"Content-Type": "application/json"}
        for g in tqdm(missing_after, desc="Ensembl lookup", unit="gene"):
            url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{g}?content-type=application/json"
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.ok:
                    data = r.json()
                    if {"seq_region_name", "start", "end"} <= data.keys():
                        ensembl_coords.append({
                            "gene": g,
                            "chromosome": str(data["seq_region_name"]),
                            "start_position": data["start"],
                            "end_position": data["end"]
                        })
                    else:
                        missing_summary.append((g, "no coord fields"))
                else:
                    missing_summary.append((g, f"HTTP {r.status_code}"))
                time.sleep(0.05)
            except Exception as e:
                missing_summary.append((g, f"error: {e}"))
                continue

    df_ens = pd.DataFrame(ensembl_coords)
    if not df_ens.empty:
        print(f"🧠 Ensembl added {len(df_ens)} genes.")
    else:
        print("⚠️ Ensembl returned no coordinates.")

    # Merge and update cache
    df_new = pd.concat([df_mg, df_ens], ignore_index=True)
    coords = pd.concat([coords, df_new], ignore_index=True)
    coords.drop_duplicates(subset=["gene"], inplace=True)
    coords.to_csv(CACHE_FILE, index=False)
    return coords

# ======================================================================
# Data loading
# ======================================================================

def load_data(file_path):
    """Load Excel, normalize, remove 'control' genes, fetch coords if missing."""
    df = pd.read_excel(file_path)
    df.columns = normalize_column_names(df.columns)

    required = {"gene","log2fc","p-value"}
    if not required.issubset(df.columns):
        raise ValueError("Excel must contain: gene/log2FC/p-value")

    mask = df["gene"].str.contains("control", case=False, na=False)
    n_ctrl = int(mask.sum())
    if n_ctrl:
        log_write(f"Ignored {n_ctrl} control genes.")
        print(f"🧹 Ignoring {n_ctrl} 'control' genes.")
        df = df[~mask]

    if not {"chromosome","start_position"}.issubset(df.columns):
        print("⚙️ Missing coordinates — fetching automatically...")
        coords = fetch_gene_coordinates(list(df["gene"]))
        if coords.empty or "gene" not in coords.columns:
            print("⚠️ No coords retrieved. Using pseudo positions.")
            df["chromosome"] = "Unknown"
            df["start_position"] = np.arange(len(df))
        else:
            df = pd.merge(df, coords, on="gene", how="left")
            df.dropna(subset=["chromosome","start_position"], inplace=True)
            print(f"✅ Coordinates merged for {len(df)} genes.")

    chrom_order = [str(i) for i in range(1,23)] + ["X","Y","Unknown"]
    df = df[["gene","chromosome","start_position","log2fc","p-value"]]
    df["chromosome"] = pd.Categorical(df["chromosome"].astype(str),
                                      categories=chrom_order, ordered=True)
    df = df.sort_values(["chromosome","start_position"]).reset_index(drop=True)
    return df, chrom_order

# ======================================================================
# Classification and positioning
# ======================================================================

def classify_genes(df, log2fc_threshold, pval_threshold):
    full = df[(df["p-value"] < pval_threshold) & (df["log2fc"].abs() > log2fc_threshold)].copy()
    partial = df[
        ((df["p-value"] < pval_threshold) & (df["log2fc"].abs() <= log2fc_threshold)) |
        ((df["p-value"] >= pval_threshold) & (df["log2fc"].abs() > log2fc_threshold))
    ].copy()
    non = df.drop(full.index).drop(partial.index)
    return full, partial, non

def compute_chromosome_positions(df, chrom_order):
    last = 0; labels = []; positions = []; bounds = []
    for chrom in chrom_order:
        d = df[df["chromosome"] == chrom]
        if d.empty: continue
        n = len(d)
        x0, x1 = last, last + n
        bounds.append((x0, x1))
        labels.append(chrom)
        positions.append(x0 + n/2)
        last += n
    df["x_pos"] = np.arange(len(df))
    return df, labels, positions, bounds

# ======================================================================
# Plotting
# ======================================================================

def plot_manhattan(df, chrom_order, log2fc_threshold, pval_threshold):
    """Generate Manhattan-style Matplotlib figure with safe color parsing."""
    df, labels, positions, bounds = compute_chromosome_positions(df, chrom_order)
    full, partial, non = classify_genes(df, log2fc_threshold, pval_threshold)
    n_full, n_partial, n_non = len(full), len(partial), len(non)
    subtitle = f"Full hits: {n_full} | Partial: {n_partial} | Non-hits: {n_non} | Total: {len(df)}"

    # Safe color parsing
    even_color = _parse_rgba(BAND_COLOR_EVEN)
    odd_color  = _parse_rgba(BAND_COLOR_ODD)

    if not full.empty:
        full["p-value"] = full["p-value"].clip(lower=1e-10)
        norm = plt.Normalize(vmin=full["p-value"].min(), vmax=full["p-value"].max())
        cmap = plt.colormaps.get_cmap("Blues_r")
        hit_colors = cmap(norm(full["p-value"]))
    else:
        hit_colors, norm, cmap = [], None, None

    fig, ax = plt.subplots(figsize=FIG_SIZE)

    # Background bands
    for i, (xmin, xmax) in enumerate(bounds):
        color = even_color if i % 2 == 0 else odd_color
        ax.axvspan(xmin, xmax, facecolor=color, zorder=0)

    # Draw non-hits → partial → full
    ax.scatter(non["x_pos"], non["log2fc"], c=NON_HIT_COLOR,
               s=MARKER_SIZE, alpha=1.0, edgecolor=EDGE_COLOR,
               linewidths=0.5, zorder=1, label="Non-hits")
    ax.scatter(partial["x_pos"], partial["log2fc"], c=PARTIAL_HIT_COLOR,
               s=MARKER_SIZE, alpha=0.9, edgecolor=EDGE_COLOR,
               linewidths=0.5, zorder=2, label="Partial hits")
    if not full.empty:
        ax.scatter(full["x_pos"], full["log2fc"], c=hit_colors,
                   s=MARKER_SIZE, alpha=MARKER_EDGE_ALPHA,
                   edgecolor=EDGE_COLOR, linewidths=0.5,
                   zorder=3, label="Full hits")

    # Label significant hits
    texts = []
    if not full.empty:
        for _, row in full.iterrows():
            texts.append(ax.text(row["x_pos"], row["log2fc"] + LABEL_OFFSET,
                                 row["gene"], fontsize=LABEL_FONT_SIZE,
                                 ha="center", va="bottom", color=LABEL_COLOR_HIT))
    if texts and len(texts) < 1000:
        adjust_text(texts, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    # Axes & titles
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Effect Size (log2 Fold Change)")
    ax.set_title(
        f"Genome-wide Effect Sizes by Gene Location\n"
        f"Thresholds: |log2FC| > {log2fc_threshold}, p < {pval_threshold}\n{subtitle}",
        fontsize=TITLE_FONT_SIZE, pad=TITLE_PADDING
    )
    ax.legend(frameon=False, loc="upper right")
    ax.grid(False)

    if not full.empty:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax)
        cbar.set_label("p-value (smaller = more significant)")

    fig.tight_layout()
    fig.savefig(SAVE_PATH, dpi=300)
    print(f"✅ Plot saved as '{SAVE_PATH}'")
    return fig
