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

Input data columns (case-insensitive)
-------------------------------------
gene, chromosome, start_position, log2FC, p-value

Author: Your Name
License: MIT
"""

# ======================================================================
#                          CONFIGURATION SECTION
# ======================================================================
# >>> USERS: MODIFY THESE PARAMETERS AS DESIRED <<<

# Visual thresholds for classification (used if user skips input)
DEFAULT_LOG2FC_THRESHOLD = 0.3
DEFAULT_PVAL_THRESHOLD = 0.03

# Marker appearance
MARKER_SIZE = 40
MARKER_EDGE_ALPHA = 0.9
NON_HIT_COLOR = "#f2f2f2"       # 5% gray for non-hits
PARTIAL_HIT_COLOR = "lightgray" # 10% gray for partial hits

# Chromosome background bands
BAND_OPACITY = 0.03
BAND_COLOR_EVEN = (0.0, 1.0, 0.0, BAND_OPACITY)  # 3% green
BAND_COLOR_ODD = (1.0, 0.0, 1.0, BAND_OPACITY)   # 3% magenta

# Label styles
LABEL_FONT_SIZE = 8
LABEL_OFFSET = 0.1
LABEL_COLOR_HIT = "black"
LABEL_COLOR_PARTIAL = "gray"

# Figure settings
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

required_packages = ["pandas", "matplotlib", "numpy", "adjustText", "openpyxl", "tk"]
for pkg in required_packages:
    # tkinter is built-in in most Python distributions; skip attempting pip install
    if pkg == "tk":
        continue
    if importlib.util.find_spec(pkg) is None:
        print(f"📦 Installing missing package: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Imports after ensuring dependencies
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from adjustText import adjust_text
from tkinter import Tk, filedialog

# ======================================================================
#                              FUNCTIONS
# ======================================================================

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


def load_data(file_path):
    """Load and validate Excel file. Returns (dataframe, chrom_order)."""
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.lower()
    required = {'gene', 'chromosome', 'start_position', 'log2fc', 'p-value'}
    if not required.issubset(df.columns):
        raise ValueError(f"Excel file must contain these columns: {required}")

    chrom_order = [str(i) for i in range(1, 23)] + ['X', 'Y']
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
    # Layout
    df, x_labels, x_label_positions, x_bounds = compute_chromosome_positions(df, chrom_order)

    # Classes
    full_hits, partial_hits, non_hits = classify_genes(df, log2fc_threshold, pval_threshold)

    # Counts (subtitle)
    n_full, n_partial, n_non = len(full_hits), len(partial_hits), len(non_hits)
    subtitle = f"Full hits: {n_full} | Partial: {n_partial} | Non-hits: {n_non} | Total: {len(df)}"

    # Color mapping for full hits
    if not full_hits.empty:
        full_hits['p-value'] = full_hits['p-value'].clip(lower=1e-10)
        norm = plt.Normalize(vmin=full_hits['p-value'].min(), vmax=full_hits['p-value'].max())
        cmap = plt.colormaps.get_cmap('Blues_r')
        hit_colors = cmap(norm(full_hits['p-value']))
    else:
        hit_colors, norm, cmap = [], None, None

    # Figure
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    # Bands
    for i, (xmin, xmax) in enumerate(x_bounds):
        color = BAND_COLOR_EVEN if i % 2 == 0 else BAND_COLOR_ODD
        ax.axvspan(xmin, xmax, facecolor=color, zorder=0)

    # Non-hits
    ax.scatter(non_hits['x_pos'], non_hits['log2fc'],
               c=NON_HIT_COLOR, s=MARKER_SIZE, alpha=1.0, edgecolor='none',
               label=f"Non-hits (|log2FC| ≤ {log2fc_threshold}, p ≥ {pval_threshold})")

    # Partial hits
    ax.scatter(partial_hits['x_pos'], partial_hits['log2fc'],
               c=PARTIAL_HIT_COLOR, s=MARKER_SIZE, alpha=0.8, edgecolor='none',
               label="Partial hits (one threshold met)")

    # Full hits
    if not full_hits.empty:
        ax.scatter(full_hits['x_pos'], full_hits['log2fc'],
                   c=hit_colors, s=MARKER_SIZE, alpha=MARKER_EDGE_ALPHA, edgecolor='none',
                   label=f"Full hits (|log2FC| > {log2fc_threshold}, p < {pval_threshold})")

    # Labels
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
        from adjustText import adjust_text
        print("🧩 Adjusting label positions to avoid overlaps...")
        adjust_text(texts, arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))

    # Axes / title / legend
    ax.set_xticks(x_label_positions)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Effect Size (log2 Fold Change)")
    ax.set_title(
        f"Genome-wide Effect Sizes by Gene Location\n"
        f"Thresholds: |log2FC| > {log2fc_threshold}, p-value < {pval_threshold}\n{subtitle}",
        fontsize=TITLE_FONT_SIZE, pad=TITLE_PADDING
    )
    ax.grid(False)
    ax.legend(frameon=False, loc='upper right')

    # Colorbar
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

    # thresholds
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
