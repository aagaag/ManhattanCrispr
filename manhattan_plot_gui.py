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
- Classification: full hits (colored), partial hits (gray, labeled), non-hits (faint gray)
- Auto-adjusted gene labels to avoid overlap
- Dynamic subtitle with counts
- Saves PNG and also shows an interactive window
- Auto-fetches genomic coordinates (chromosome, start, end) from MyGene.info if missing
- Tolerant to column name variations like Gene_symbol, log2Ratio, pValue, etc.

Input data columns (case-insensitive)
-------------------------------------
gene/gene_symbol, log2FC/log2Ratio, p-value/pValue
Optionally: chromosome, start_position, end_position

Author: Your Name
License: MIT
"""

# ======================================================================
#                          CONFIGURATION SECTION
# ======================================================================
# >>> USERS: MODIFY THESE PARAMETERS AS DESIRED <<<

DEFAULT_LOG2FC_THRESHOLD = 0.3
DEFAULT_PVAL_THRESHOLD = 0.03
MARKER_SIZE = 40
MARKER_EDGE_ALPHA = 0.9
NON_HIT_COLOR = "#f2f2f2"
PARTIAL_HIT_COLOR = "lightgray"
BAND_OPACITY = 0.03
BAND_COLOR_EVEN = (0.0, 1.0, 0.0, BAND_OPACITY)
BAND_COLOR_ODD = (1.0, 0.0, 1.0, BAND_OPACITY)
LABEL_FONT_SIZE = 8
LABEL_OFFSET = 0.1
LABEL_COLOR_HIT = "black"
LABEL_COLOR_PARTIAL = "gray"
FIG_SIZE = (14, 7)
TITLE_FONT_SIZE = 12
TITLE_PADDING = 20
SAVE_PATH = "manhattan_plot_gui.png"

# ======================================================================
#                        DEPENDENCY CHECK AND IMPORTS
# ======================================================================

import subprocess
import sys
import importlib.util

required_packages = ["pandas", "matplotlib", "numpy", "adjustText", "openpyxl", "mygene", "tk"]
for pkg in required_packages:
    if pkg == "tk":
        continue
    if importlib.util.find_spec(pkg) is None:
        print(f"📦 Installing missing package: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from adjustText import adjust_text
from tkinter import Tk, filedialog
import mygene

# ======================================================================
#                              FUNCTIONS
# ======================================================================

def fetch_gene_coordinates(gene_list, species="human"):
    """Fetch chromosome, start, and end coordinates for each gene symbol using MyGene.info."""
    mg = mygene.MyGeneInfo()
    print(f"🔎 Fetching genomic coordinates for {len(gene_list)} genes from MyGene.info...")
    try:
        query_result = mg.querymany(
            gene_list,
            scopes="symbol",
            fields="genomic_pos",
            species=species,
            as_dataframe=True
        )
    except Exception as e:
        print(f"⚠️ MyGene.info query failed: {e}")
        return pd.DataFrame()

    query_result.reset_index(inplace=True)
    query_result.rename(columns={"query": "gene"}, inplace=True)
    coords = []
    for _, row in query_result.iterrows():
        pos = row.get("genomic_pos")
        if isinstance(pos, dict):
            coords.append({
                "gene": row["gene"],
                "chromosome": pos.get("chr"),
                "start_position": pos.get("start"),
                "end_position": pos.get("end"),
            })
    df_coords = pd.DataFrame(coords).dropna()
    print(f"✅ Retrieved coordinates for {len(df_coords)} genes.")
    return df_coords


def pick_excel_file():
    """Open a GUI dialog to select an Excel (.xlsx) file and return its path."""
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    print("📂 Please select your Excel (.xlsx) file...")
    file_path = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
    )
    if not file_path:
        print("❌ No file selected. Exiting.")
        sys.exit(1)
    print(f"✅ Selected file: {file_path}\n")
    return file_path


def normalize_column_names(columns):
    """
    Normalize column names: lowercase, remove spaces/underscores/hyphens,
    and map common aliases to canonical names.
    Supports: Gene_symbol, Gene Symbol, log2Ratio, log2 Ratio, pValue, etc.
    """
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
        key = (
            col.strip()
               .lower()
               .replace("_", "")
               .replace("-", "")
               .replace(" ", "")
        )
        normalized.append(mapping.get(key, key))
    return normalized


def load_data(file_path):
    """Load and validate Excel file. Returns (dataframe, chrom_order)."""
    df = pd.read_excel(file_path)
    df.columns = normalize_column_names(df.columns)

    required_basic = {'gene', 'log2fc', 'p-value'}
    if not required_basic.issubset(df.columns):
        raise ValueError(
            "Excel file must contain at least: gene/gene_symbol, log2FC/log2Ratio, and p-value/pValue"
        )

    # Fetch coordinates if missing
    if not {'chromosome', 'start_position'}.issubset(df.columns):
        print("⚙️ Missing genomic coordinates — fetching automatically...")
        coords = fetch_gene_coordinates(list(df['gene']))
        if coords.empty or "gene" not in coords.columns:
            print("⚠️ Warning: No coordinates retrieved from MyGene.info. "
                  "Proceeding without genomic locations (using pseudo-positions).")
            # Create placeholder chromosome and start positions
            df["chromosome"] = "Unknown"
            df["start_position"] = np.arange(len(df))
        else:
            df = pd.merge(df, coords, on="gene", how="left")
            df.dropna(subset=["chromosome", "start_position"], inplace=True)
            print(f"✅ Coordinates added for {len(df)} genes.")

    chrom_order = [str(i) for i in range(1, 23)] + ['X', 'Y', 'Unknown']
    if not {"chromosome", "start_position"}.issubset(df.columns):
        raise ValueError("No usable genomic coordinates were found or fetched.")

    df = df[['gene', 'chromosome', 'start_position', 'log2fc', 'p-value']]
    df['chromosome'] = pd.Categorical(df['chromosome'].astype(str), categories=chrom_order, ordered=True)
    df = df.sort_values(['chromosome', 'start_position']).reset_index(drop=True)
    return df, chrom_order


def classify_genes(df, log2fc_threshold, pval_threshold):
    """Return dataframes: full_hits, partial_hits, non_hits."""
    full_hits = df[(df['p-value'] < pval_threshold) & (df['log2fc'].abs() > log2fc_threshold)].copy()
    partial_hits = df[
        ((df['p-value'] < pval_threshold) & (df['log2fc'].abs() <= log2fc_threshold)) |
        ((df['p-value'] >= pval_threshold) & (df['log2fc'].abs() > log2fc_threshold))
    ].copy()
    non_hits = df.drop(full_hits.index).drop(partial_hits.index)
    return full_hits, partial_hits, non_hits


def compute_chromosome_positions(df, chrom_order):
    """Compute continuous x positions, x tick labels/positions, and chromosome band bounds."""
    last_base = 0
    x_labels, x_label_positions, x_bounds = [], [], []
    for chrom in chrom_order:
        chrom_df = df[df['chromosome'] == chrom]
        if chrom_df.empty:
            continue
        n = len(chrom_df)
        x_min, x_max = last_base, last_base + n
        x_bounds.append((x_min, x_max))
        x_labels.append(chrom)
        x_label_positions.append(x_min + n / 2)
        last_base += n

    df['x_pos'] = np.arange(len(df))
    return df, x_labels, x_label_positions, x_bounds


def plot_manhattan(df, chrom_order, log2fc_threshold, pval_threshold):
    """Render the Manhattan-style plot with classification, labels, bands, and colorbar."""
    df, x_labels, x_label_positions, x_bounds = compute_chromosome_positions(df, chrom_order)
    full_hits, partial_hits, non_hits = classify_genes(df, log2fc_threshold, pval_threshold)
    n_full, n_partial, n_non = len(full_hits), len(partial_hits), len(non_hits)
    subtitle = f"Full hits: {n_full} | Partial: {n_partial} | Non-hits: {n_non} | Total: {len(df)}"

    if not full_hits.empty:
        full_hits['p-value'] = full_hits['p-value'].clip(lower=1e-10)
        norm = plt.Normalize(vmin=full_hits['p-value'].min(), vmax=full_hits['p-value'].max())
        cmap = plt.colormaps.get_cmap('Blues_r')
        hit_colors = cmap(norm(full_hits['p-value']))
    else:
        hit_colors, norm, cmap = [], None, None

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    for i, (xmin, xmax) in enumerate(x_bounds):
        color = BAND_COLOR_EVEN if i % 2 == 0 else BAND_COLOR_ODD
        ax.axvspan(xmin, xmax, facecolor=color, zorder=0)

    ax.scatter(non_hits['x_pos'], non_hits['log2fc'], c=NON_HIT_COLOR, s=MARKER_SIZE,
               alpha=1.0, edgecolor='none',
               label=f"Non-hits (|log2FC| ≤ {log2fc_threshold}, p ≥ {pval_threshold})")
    ax.scatter(partial_hits['x_pos'], partial_hits['log2fc'], c=PARTIAL_HIT_COLOR, s=MARKER_SIZE,
               alpha=0.8, edgecolor='none', label="Partial hits (one threshold met)")
    if not full_hits.empty:
        ax.scatter(full_hits['x_pos'], full_hits['log2fc'], c=hit_colors, s=MARKER_SIZE,
                   alpha=MARKER_EDGE_ALPHA, edgecolor='none',
                   label=f"Full hits (|log2FC| > {log2fc_threshold}, p < {pval_threshold})")

    texts = []
    for _, row in full_hits.iterrows():
        texts.append(ax.text(row['x_pos'], row['log2fc'] + LABEL_OFFSET, row['gene'],
                             fontsize=LABEL_FONT_SIZE, ha='center', va='bottom',
                             color=LABEL_COLOR_HIT))
    for _, row in partial_hits.iterrows():
        texts.append(ax.text(row['x_pos'], row['log2fc'] + LABEL_OFFSET, row['gene'],
                             fontsize=LABEL_FONT_SIZE, ha='center', va='bottom',
                             color=LABEL_COLOR_PARTIAL))
    if texts:
        print("🧩 Adjusting label positions to avoid overlaps...")
        adjust_text(texts, arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))

    ax.set_xticks(x_label_positions)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Effect Size (log2 Fold Change)")
    ax.set_title(
        f"Genome-wide Effect Sizes by Gene Location\n"
        f"Thresholds: |log2FC| > {log2fc_threshold}, p-value < {pval_threshold}\n{subtitle}",
        fontsize=TITLE_FONT_SIZE, pad=TITLE_PADDING)
    ax.grid(False)
    ax.legend(frameon=False, loc='upper right')

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
