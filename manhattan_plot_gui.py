#!/usr/bin/env python3
"""
manhattan_plot_gui.py

Interactive Manhattan-style plot generator for gene effect datasets.

Features
--------
- GUI file picker (Tkinter) to select an Excel .xlsx file
- Interactive threshold input (|log2FC| and p-value)
- Automatic dependency installation (first run only)
- Publication-ready styling with configurable parameters at the top
- Alternating 3% opacity chromosome background bands
- Classification: full hits (colored), partial hits (gray, labeled), non-hits (3% gray)
- Thin white outlines around all points for overlap visibility
- Auto-adjusted gene labels to avoid overlap
- Dynamic subtitle with counts
- Saves PNG and also shows an interactive window
- Auto-fetches genomic coordinates (chromosome, start, end) from MyGene.info and Ensembl
- Caches retrieved coordinates locally (gene_coordinates_cache.csv)
- Generates a detailed log file (coordinate_fetch_log.txt)
- Ignores genes containing “control” (case-insensitive), logs count
- Tolerant to column name variations (Gene_symbol, log2Ratio, pValue, etc.)
- TEST MODE: limit coordinate queries to the first N genes for quick testing

Author: Your Name
License: MIT
"""

# ======================================================================
#                          CONFIGURATION SECTION
# ======================================================================
# >>> USERS: MODIFY THESE PARAMETERS AS DESIRED <<<

# Threshold defaults
DEFAULT_LOG2FC_THRESHOLD = 0.3
DEFAULT_PVAL_THRESHOLD = 0.03

# Marker appearance
MARKER_SIZE = 40
MARKER_EDGE_ALPHA = 0.9
NON_HIT_COLOR = "#d9d9d9"       # ~3% darker gray
PARTIAL_HIT_COLOR = "lightgray"
EDGE_COLOR = "white"            # thin white outline for all points

# Chromosome background bands
BAND_OPACITY = 0.03
BAND_COLOR_EVEN = (0.0, 1.0, 0.0, BAND_OPACITY)  # 3% green
BAND_COLOR_ODD  = (1.0, 0.0, 1.0, BAND_OPACITY)  # 3% magenta

# Label styles
LABEL_FONT_SIZE = 8
LABEL_OFFSET     = 0.1
LABEL_COLOR_HIT  = "black"

# Figure layout
FIG_SIZE        = (14, 7)
TITLE_FONT_SIZE = 12
TITLE_PADDING   = 20
SAVE_PATH       = "manhattan_plot_gui.png"

# Cache and log files
CACHE_FILE = "gene_coordinates_cache.csv"
LOG_FILE   = "coordinate_fetch_log.txt"

# ---- TEST MODE SWITCH ------------------------------------------------
# When TEST_MODE = True, only the first TEST_LIMIT genes are queried for
# coordinates.  Useful for quick testing with large files.
TEST_MODE  = False
TEST_LIMIT = 50
# ----------------------------------------------------------------------

# ======================================================================
#                        DEPENDENCY CHECK AND IMPORTS
# ======================================================================

import subprocess
import sys
import importlib.util

# Required packages; automatically installed if missing
required_packages = [
    "pandas", "matplotlib", "numpy", "adjustText",
    "openpyxl", "mygene", "requests", "tqdm", "tk"
]

for pkg in required_packages:
    if pkg == "tk":  # Tkinter comes with Python; skip install
        continue
    if importlib.util.find_spec(pkg) is None:
        print(f"📦 Installing missing package: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Standard imports
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from adjustText import adjust_text
from tkinter import Tk, filedialog
import mygene
import requests
import time
import os
from tqdm import tqdm
from datetime import datetime

# ======================================================================
#                              FUNCTIONS
# ======================================================================

def log_write(message):
    """Append a line to the log file with timestamp."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")


def fetch_gene_coordinates(gene_list, species="human"):
    """
    Fetch genomic coordinates (chromosome, start, end) for each gene symbol.
    Uses cached data first, then MyGene.info, then Ensembl REST API fallback.
    Shows detailed debugging information and a progress bar for Ensembl queries.
    Writes diagnostic info to coordinate_fetch_log.txt.
    """
    gene_list = [str(g).strip() for g in gene_list if isinstance(g, str) and g.strip()]

    # Apply test limit if enabled
    if TEST_MODE and len(gene_list) > TEST_LIMIT:
        print(f"🧪 TEST MODE: Only retrieving coordinates for the first {TEST_LIMIT} genes.")
        gene_list = gene_list[:TEST_LIMIT]

    print(f"🔎 Total input genes: {len(gene_list)}")
    log_write(f"--- Coordinate fetch started for {len(gene_list)} genes ---")

    # ---- Load cache ---------------------------------------------------
    cache = pd.DataFrame(columns=["gene", "chromosome", "start_position", "end_position"])
    if os.path.exists(CACHE_FILE):
        cache = pd.read_csv(CACHE_FILE)
        cache["gene"] = cache["gene"].astype(str)
        print(f"📂 Loaded {len(cache)} cached coordinates from {CACHE_FILE}")
        log_write(f"Loaded {len(cache)} cached coordinates from cache file.")

    cached_genes = set(cache["gene"].unique())
    missing_genes = [g for g in gene_list if g not in cached_genes]
    coords = cache.copy()
    print(f"📊 Genes in cache: {len(cached_genes)} | Missing: {len(missing_genes)}")
    log_write(f"Genes in cache: {len(cached_genes)} | Missing: {len(missing_genes)}")

    mg_results = []
    missing_summary = []  # (gene, reason)
    duplicates = 0

    # ---- Query MyGene.info --------------------------------------------
    if missing_genes:
        print(f"🧬 Querying MyGene.info for {len(missing_genes)} genes...")
        log_write(f"Querying MyGene.info for {len(missing_genes)} genes...")
        mg = mygene.MyGeneInfo()
        try:
            query_result = mg.querymany(
                missing_genes,
                scopes="symbol",
                fields="genomic_pos",
                species=species,
                as_dataframe=False
            )
        except Exception as e:
            print(f"⚠️ MyGene.info query failed: {e}")
            log_write(f"MyGene.info query failed: {e}")
            query_result = []

        found = 0
        for entry in query_result:
            gene = entry.get("query")
            if "notfound" in entry and entry["notfound"]:
                missing_summary.append((gene, "not found"))
                continue
            if "genomic_pos" in entry:
                found += 1
                pos = entry["genomic_pos"]
                if isinstance(pos, list):
                    duplicates += 1
                    pos = pos[0]
                mg_results.append({
                    "gene": gene,
                    "chromosome": pos.get("chr"),
                    "start_position": pos.get("start"),
                    "end_position": pos.get("end")
                })
            else:
                missing_summary.append((gene, "no genomic_pos field"))

        df_mg = pd.DataFrame(mg_results).dropna()
        retrieved = set(df_mg["gene"].unique()) if not df_mg.empty else set()
        missing_after_mg = [g for g in missing_genes if g not in retrieved]

        print(f"✅ MyGene.info found {found} genes (duplicates: {duplicates}), {len(missing_after_mg)} still missing.")
        log_write(f"MyGene.info found {found} genes (duplicates: {duplicates}), {len(missing_after_mg)} still missing.")
    else:
        df_mg = pd.DataFrame()
        missing_after_mg = []

    # ---- Ensembl fallback ---------------------------------------------
    ensembl_coords = []
    headers = {"Content-Type": "application/json"}
    if missing_after_mg:
        print(f"🌐 Querying Ensembl REST API for {len(missing_after_mg)} remaining genes...")
        log_write(f"Querying Ensembl REST API for {len(missing_after_mg)} remaining genes...")
        for gene in tqdm(missing_after_mg, desc="Ensembl lookup", unit="gene"):
            url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}?content-type=application/json"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.ok:
                    data = response.json()
                    if "seq_region_name" in data and "start" in data and "end" in data:
                        ensembl_coords.append({
                            "gene": gene,
                            "chromosome": str(data["seq_region_name"]),
                            "start_position": data["start"],
                            "end_position": data["end"]
                        })
                    else:
                        missing_summary.append((gene, "no coordinate fields"))
                else:
                    missing_summary.append((gene, f"HTTP {response.status_code}"))
                time.sleep(0.05)
            except Exception as e:
                missing_summary.append((gene, f"error: {e}"))
                continue

    df_ens = pd.DataFrame(ensembl_coords)
    if not df_ens.empty:
        print(f"🧠 Ensembl added {len(df_ens)} more genes.")
        log_write(f"Ensembl added {len(df_ens)} more genes.")
    else:
        print("⚠️ Ensembl fallback did not return any coordinates.")
        log_write("Ensembl fallback did not return any coordinates.")

    # ---- Merge & update cache -----------------------------------------
    df_new = pd.concat([df_mg, df_ens], ignore_index=True)
    coords = pd.concat([coords, df_new], ignore_index=True)
    coords.drop_duplicates(subset=["gene"], inplace=True)
    coords.to_csv(CACHE_FILE, index=False)

    # ---- Final summary ------------------------------------------------
    retrieved_total = len(df_new)
    missing_total = len([g for g in gene_list if g not in set(coords["gene"].unique())])
    print("\n===== Coordinate Fetch Summary =====")
    print(f"Total genes requested: {len(gene_list)}")
    print(f"Already in cache:      {len(cached_genes)}")
    print(f"Newly retrieved:       {retrieved_total}")
    print(f"Duplicates (MyGene):   {duplicates}")
    print(f"Not found total:       {missing_total}")
    log_write(f"Summary: {retrieved_total} new, {duplicates} duplicates, {missing_total} missing")

    if missing_summary:
        print("\nList of missing or problematic genes (up to 50):")
        for g, reason in missing_summary[:50]:
            print(f"   • {g}: {reason}")
        if len(missing_summary) > 50:
            print(f"   ... {len(missing_summary)-50} more not shown.")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n--- Missing or problematic genes ---\n")
            for g, reason in missing_summary:
                f.write(f"{g}\t{reason}\n")

    print("====================================\n")
    log_write("Coordinate fetching complete.\n")
    return coords


def pick_excel_file():
    """Open a GUI dialog to select an Excel (.xlsx) file and return its path."""
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    print("📂 Please select your Excel (.xlsx) file...")
    file_path = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")]
    )
    if not file_path:
        print("❌ No file selected. Exiting.")
        sys.exit(1)
    print(f"✅ Selected file: {file_path}\n")
    return file_path


def normalize_column_names(columns):
    """Normalize column names to consistent lower-case identifiers."""
    mapping = {
        "genesymbol": "gene",
        "symbol": "gene",
        "geneid": "gene",
        "genename": "gene",
        "log2ratio": "log2fc",
        "foldchange": "log2fc",
        "ratio": "log2fc",
        "log2foldchange": "log2fc",
        "pvalue": "p-value",
        "pval": "p-value",
        "p": "p-value"
    }
    normalized = []
    for col in columns:
        key = col.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
        normalized.append(mapping.get(key, key))
    return normalized


def load_data(file_path):
    """Load and validate Excel file. Returns (dataframe, chrom_order)."""
    df = pd.read_excel(file_path)
    df.columns = normalize_column_names(df.columns)

    required_basic = {"gene", "log2fc", "p-value"}
    if not required_basic.issubset(df.columns):
        raise ValueError("Excel must contain: gene/gene_symbol, log2FC/log2Ratio, p-value/pValue")

    # Filter out control genes
    control_mask = df["gene"].str.contains("control", case=False, na=False)
    n_controls = control_mask.sum()
    if n_controls > 0:
        log_write(f"Ignored {n_controls} genes containing 'control'")
        print(f"🧹 Ignoring {n_controls} 'control' genes.")
        df = df[~control_mask]

    # Fetch coordinates if missing
    if not {"chromosome", "start_position"}.issubset(df.columns):
        print("⚙️ Missing genomic coordinates — fetching automatically...")
        coords = fetch_gene_coordinates(list(df["gene"]))
        if coords.empty or "gene" not in coords.columns:
            print("⚠️ No coordinates retrieved. Using pseudo-positions.")
            df["chromosome"] = "Unknown"
            df["start_position"] = np.arange(len(df))
        else:
            df = pd.merge(df, coords, on="gene", how="left")
            df.dropna(subset=["chromosome", "start_position"], inplace=True)
            print(f"✅ Coordinates merged for {len(df)} genes.")

    chrom_order = [str(i) for i in range(1, 23)] + ["X", "Y", "Unknown"]
    df = df[["gene", "chromosome", "start_position", "log2fc", "p-value"]]
    df["chromosome"] = pd.Categorical(df["chromosome"].astype(str), categories=chrom_order, ordered=True)
    df = df.sort_values(["chromosome", "start_position"]).reset_index(drop=True)
    return df, chrom_order


def classify_genes(df, log2fc_threshold, pval_threshold):
    """Split dataframe into full_hits, partial_hits, and non_hits."""
    full_hits = df[(df["p-value"] < pval_threshold) & (df["log2fc"].abs() > log2fc_threshold)].copy()
    partial_hits = df[
        ((df["p-value"] < pval_threshold) & (df["log2fc"].abs() <= log2fc_threshold)) |
        ((df["p-value"] >= pval_threshold) & (df["log2fc"].abs() > log2fc_threshold))
    ].copy()
    non_hits = df.drop(full_hits.index).drop(partial_hits.index)
    return full_hits, partial_hits, non_hits


def compute_chromosome_positions(df, chrom_order):
    """Compute continuous x positions and band boundaries for plotting."""
    last_base = 0
    x_labels, x_label_positions, x_bounds = [], [], []
    for chrom in chrom_order:
        chrom_df = df[df["chromosome"] == chrom]
        if chrom_df.empty:
            continue
        n = len(chrom_df)
        x_min, x_max = last_base, last_base + n
        x_bounds.append((x_min, x_max))
        x_labels.append(chrom)
        x_label_positions.append(x_min + n / 2)
        last_base += n
    df["x_pos"] = np.arange(len(df))
    return df, x_labels, x_label_positions, x_bounds


def plot_manhattan(df, chrom_order, log2fc_threshold, pval_threshold):
    """Render the Manhattan-style plot."""
    df, x_labels, x_label_positions, x_bounds = compute_chromosome_positions(df, chrom_order)
    full_hits, partial_hits, non_hits = classify_genes(df, log2fc_threshold, pval_threshold)
    n_full, n_partial, n_non = len(full_hits), len(partial_hits), len(non_hits)
    subtitle = f"Full hits: {n_full} | Partial: {n_partial} | Non-hits: {n_non} | Total: {len(df)}"

    if not full_hits.empty:
        full_hits["p-value"] = full_hits["p-value"].clip(lower=1e-10)
        norm = plt.Normalize(vmin=full_hits["p-value"].min(), vmax=full_hits["p-value"].max())
        cmap = plt.colormaps.get_cmap("Blues_r")
        hit_colors = cmap(norm(full_hits["p-value"]))
    else:
        hit_colors, norm, cmap = [], None, None

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    for i, (xmin, xmax) in enumerate(x_bounds):
        color = BAND_COLOR_EVEN if i % 2 == 0 else BAND_COLOR_ODD
        ax.axvspan(xmin, xmax, facecolor=color, zorder=0)

    # Draw non-hits, then partials, then full hits
    ax.scatter(non_hits["x_pos"], non_hits["log2fc"],
               c=NON_HIT_COLOR, s=MARKER_SIZE, alpha=1.0, edgecolor=EDGE_COLOR, linewidths=0.5, zorder=1)
    ax.scatter(partial_hits["x_pos"], partial_hits["log2fc"],
               c=PARTIAL_HIT_COLOR, s=MARKER_SIZE, alpha=0.9, edgecolor=EDGE_COLOR, linewidths=0.5, zorder=2)
    if not full_hits.empty:
        ax.scatter(full_hits["x_pos"], full_hits["log2fc"],
                   c=hit_colors, s=MARKER_SIZE, alpha=MARKER_EDGE_ALPHA,
                   edgecolor=EDGE_COLOR, linewidths=0.5, zorder=3)

    texts = []
    if not full_hits.empty:
        print(f"🧬 Labeling {len(full_hits)} significant genes...")
        for _, row in full_hits.iterrows():
            texts.append(ax.text(row["x_pos"], row["log2fc"] + LABEL_OFFSET, row["gene"],
                                 fontsize=LABEL_FONT_SIZE, ha="center", va="bottom", color=LABEL_COLOR_HIT))
    if texts and len(texts) < 1000:
        print("🧩 Adjusting label positions to avoid overlaps...")
        adjust_text(texts, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    ax.set_xticks(x_label_positions)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Effect Size (log2 Fold Change)")
    ax.set_title(f"Genome-wide Effect Sizes by Gene Location\n"
                 f"Thresholds: |log2FC| > {log2fc_threshold}, p < {pval_threshold}\n{subtitle}",
                 fontsize=TITLE_FONT_SIZE, pad=TITLE_PADDING)
    ax.grid(False)
    ax.legend(frameon=False, loc="upper right")

    if not full_hits.empty:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax)
        cbar.set_label("p-value (smaller = more significant)")

    fig.tight_layout()
    fig.savefig(SAVE_PATH, dpi=300)
    print(f"\n✅ Plot saved as '{SAVE_PATH}'")
    plt.show()


# ======================================================================
#                              MAIN EXECUTION
# ======================================================================

if __name__ == "__main__":
    print("=== Manhattan Plot Generator (GUI Version) ===\n")
    excel_path = pick_excel_file()
    df, chrom_order = load_data(excel_path)

    try:
        user_fc = input(f"Enter minimal absolute log2FC (default ±{DEFAULT_LOG2FC_THRESHOLD}): ").strip()
        log2fc_threshold = float(user_fc) if user_fc else DEFAULT_LOG2FC_THRESHOLD
    except ValueError:
        log2fc_threshold = DEFAULT_LOG2FC_THRESHOLD

    try:
        user_pval = input(f"Enter maximal p-value (default {DEFAULT_PVAL_THRESHOLD}): ").strip()
        pval_threshold = float(user_pval) if user_pval else DEFAULT_PVAL_THRESHOLD
    except ValueError:
        pval_threshold = DEFAULT_PVAL_THRESHOLD

    print(f"\nUsing thresholds: |log2FC| > {log2fc_threshold}, p < {pval_threshold}\n")
    plot_manhattan(df, chrom_order, log2fc_threshold, pval_threshold)
