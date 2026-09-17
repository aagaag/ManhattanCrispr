"""
manhattan_plot_core.py
--------------------------------------------------
Core backend for the Manhattan Plot Generator.

Responsibilities:
- Load and validate input data
- Fetch genomic coordinates from multiple databases
- Cache and log results in structured folders (/data, /log)
- Classify hits and render Manhattan-style plots
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from adjustText import adjust_text
import requests
from tqdm import tqdm
import time
import mygene

# ----------------------------------------------------------------------
# Folder structure setup
# ----------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
LOG_DIR = os.path.join(ROOT_DIR, "log")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

CACHE_FILE = os.path.join(DATA_DIR, "gene_coordinates_cache.csv")
LOG_FILE = os.path.join(LOG_DIR, "coordinate_fetch_log.txt")

# ----------------------------------------------------------------------
# Default parameters
# ----------------------------------------------------------------------
DEFAULT_LOG2FC_THRESHOLD = 0.3
DEFAULT_PVAL_THRESHOLD = 0.03
TEST_MODE = False
TEST_LIMIT = 50
USE_CACHE_ONLY = False

# Database flags (controlled by GUI)
USE_MYGENE = True
USE_ENSEMBL = True
USE_NCBI = True
USE_HGNC = True

# Plot styling
MARKER_SIZE = 40
MARKER_EDGE_ALPHA = 0.9
NON_HIT_COLOR = "#d9d9d9"
PARTIAL_HIT_COLOR = "lightgray"
EDGE_COLOR = "white"
BAND_OPACITY = 0.03
BAND_COLOR_EVEN = (0.0, 1.0, 0.0, BAND_OPACITY)
BAND_COLOR_ODD = (1.0, 0.0, 1.0, BAND_OPACITY)
LABEL_FONT_SIZE = 8
LABEL_OFFSET = 0.1
LABEL_COLOR_HIT = "black"
FIG_SIZE = (14, 7)
TITLE_FONT_SIZE = 12
TITLE_PADDING = 20
SAVE_PATH = "manhattan_plot_gui.png"

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
def log_write(msg: str):
    from datetime import datetime
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

# ----------------------------------------------------------------------
# Coordinate fetching
# ----------------------------------------------------------------------
def fetch_gene_coordinates(gene_list, species="human"):
    """
    Fetch coordinates using selected databases.
    Each gene is checked in cache first; if not found, queries selected APIs.
    """
    gene_list = [str(g).strip() for g in gene_list if isinstance(g, str) and g.strip()]
    if TEST_MODE and len(gene_list) > TEST_LIMIT:
        gene_list = gene_list[:TEST_LIMIT]
        print(f"🧪 TEST_MODE: limiting to first {TEST_LIMIT} genes")

    print(f"🔎 Total input genes: {len(gene_list)}")
    log_write(f"Fetching coordinates for {len(gene_list)} genes")

    cache = pd.DataFrame(columns=["gene", "chromosome", "start_position", "end_position"])
    if os.path.exists(CACHE_FILE):
        cache = pd.read_csv(CACHE_FILE)
    cache_genes = set(cache["gene"].astype(str))
    coords = cache.copy()
    missing = [g for g in gene_list if g not in cache_genes]

    if not missing:
        print("✅ All genes already cached.")
        return coords

    if USE_CACHE_ONLY:
        print("💾 CACHE-ONLY mode enabled, skipping queries.")
        return coords

    print(f"🧠 Databases: MyGene={USE_MYGENE}, Ensembl={USE_ENSEMBL}, NCBI={USE_NCBI}, HGNC={USE_HGNC}")
    log_write(f"Database flags: {USE_MYGENE=}, {USE_ENSEMBL=}, {USE_NCBI=}, {USE_HGNC=}")

    results, errors = [], []
    mg = mygene.MyGeneInfo() if USE_MYGENE else None
    headers = {"Accept": "application/json"}

    for gene in tqdm(missing, desc="Fetching genes", unit="gene"):
        record = None

        # MyGene.info
        if USE_MYGENE and not record:
            try:
                q = mg.query(gene, scopes="symbol", fields="genomic_pos", species=species)
                if q["hits"]:
                    pos = q["hits"][0].get("genomic_pos")
                    if isinstance(pos, list): pos = pos[0]
                    if isinstance(pos, dict):
                        record = {
                            "gene": gene,
                            "chromosome": pos.get("chr"),
                            "start_position": pos.get("start"),
                            "end_position": pos.get("end"),
                        }
            except Exception as e:
                errors.append((gene, f"MyGene error: {e}"))

        # Ensembl
        if USE_ENSEMBL and not record:
            try:
                url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}?content-type=application/json"
                r = requests.get(url, timeout=8)
                if r.ok:
                    d = r.json()
                    if "seq_region_name" in d:
                        record = {
                            "gene": gene,
                            "chromosome": str(d["seq_region_name"]),
                            "start_position": d.get("start"),
                            "end_position": d.get("end"),
                        }
            except Exception as e:
                errors.append((gene, f"Ensembl error: {e}"))

        # NCBI Entrez
        if USE_NCBI and not record:
            try:
                base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                q1 = requests.get(f"{base}esearch.fcgi?db=gene&term={gene}[sym]+AND+Homo+sapiens[orgn]&retmode=json", timeout=10)
                ids = q1.json().get("esearchresult", {}).get("idlist", [])
                if ids:
                    gid = ids[0]
                    q2 = requests.get(f"{base}esummary.fcgi?db=gene&id={gid}&retmode=json", timeout=10)
                    doc = q2.json().get("result", {}).get(gid, {})
                    chr_ = doc.get("chromosome")
                    gi = doc.get("genomicinfo")
                    if chr_ and gi:
                        start, end = gi[0].get("chrstart"), gi[0].get("chrstop")
                        record = {
                            "gene": gene,
                            "chromosome": str(chr_),
                            "start_position": start,
                            "end_position": end,
                        }
            except Exception as e:
                errors.append((gene, f"NCBI error: {e}"))

        # HGNC
        if USE_HGNC and not record:
            try:
                url = f"https://rest.genenames.org/fetch/symbol/{gene}"
                r = requests.get(url, headers=headers, timeout=10)
                if r.ok:
                    docs = r.json().get("response", {}).get("docs", [])
                    if docs:
                        d = docs[0]
                        record = {
                            "gene": gene,
                            "chromosome": str(d.get("chromosome", "Unknown")),
                            "start_position": None,
                            "end_position": None,
                        }
            except Exception as e:
                errors.append((gene, f"HGNC error: {e}"))

        if record:
            results.append(record)
            coords = pd.concat([coords, pd.DataFrame([record])], ignore_index=True)
            coords.drop_duplicates("gene", inplace=True)
            coords.to_csv(CACHE_FILE, index=False)
        else:
            errors.append((gene, "not found in selected databases"))
        time.sleep(0.05)

    print(f"✅ Fetched {len(results)} new, {len(errors)} unresolved.")
    if errors:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n--- Unresolved genes ---\n")
            for g, e in errors:
                f.write(f"{g}\t{e}\n")

    return coords

# ----------------------------------------------------------------------
# Data loading and normalization
# ----------------------------------------------------------------------
def normalize_column_names(columns):
    mapping = {
        "genesymbol": "gene", "symbol": "gene", "geneid": "gene", "genename": "gene",
        "log2ratio": "log2fc", "foldchange": "log2fc", "ratio": "log2fc",
        "pvalue": "p-value", "pval": "p-value", "p": "p-value"
    }
    normalized = []
    for col in columns:
        key = col.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
        normalized.append(mapping.get(key, key))
    return normalized


def load_data(file_path):
    """Load Excel input, normalize column names, and fetch coordinates."""
    df = pd.read_excel(file_path)
    df.columns = normalize_column_names(df.columns)
    required = {"gene", "log2fc", "p-value"}
    if not required.issubset(df.columns):
        raise ValueError("Excel must contain: gene/gene_symbol, log2FC/log2Ratio, p-value/pValue")

    # Drop 'control' genes
    mask = df["gene"].str.contains("control", case=False, na=False)
    n_controls = mask.sum()
    if n_controls:
        log_write(f"Ignored {n_controls} 'control' genes.")
        df = df[~mask]

    # Fetch coordinates if missing
    if not {"chromosome", "start_position"}.issubset(df.columns):
        print("⚙️ Missing genomic coordinates — fetching automatically...")
        coords = fetch_gene_coordinates(df["gene"].tolist())
        df = df.merge(coords, on="gene", how="left")

    chrom_order = [str(i) for i in range(1, 23)] + ["X", "Y", "MT", "Unknown"]
    df = df[["gene", "chromosome", "start_position", "log2fc", "p-value"]]
    df["chromosome"] = pd.Categorical(df["chromosome"].astype(str), categories=chrom_order, ordered=True)
    df = df.sort_values(["chromosome", "start_position"]).reset_index(drop=True)
    return df, chrom_order

# ----------------------------------------------------------------------
# Classification and plotting
# ----------------------------------------------------------------------
def classify_genes(df, log2fc_threshold, pval_threshold):
    full_hits = df[(df["p-value"] < pval_threshold) & (df["log2fc"].abs() > log2fc_threshold)]
    partial_hits = df[
        ((df["p-value"] < pval_threshold) & (df["log2fc"].abs() <= log2fc_threshold)) |
        ((df["p-value"] >= pval_threshold) & (df["log2fc"].abs() > log2fc_threshold))
    ]
    non_hits = df.drop(full_hits.index).drop(partial_hits.index)
    return full_hits, partial_hits, non_hits


def compute_chromosome_positions(df, chrom_order):
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

    ax.scatter(non_hits["x_pos"], non_hits["log2fc"], c=NON_HIT_COLOR,
               s=MARKER_SIZE, alpha=1.0, edgecolor=EDGE_COLOR, linewidths=0.5, zorder=1)
    ax.scatter(partial_hits["x_pos"], partial_hits["log2fc"], c=PARTIAL_HIT_COLOR,
               s=MARKER_SIZE, alpha=0.9, edgecolor=EDGE_COLOR, linewidths=0.5, zorder=2)
    if not full_hits.empty:
        ax.scatter(full_hits["x_pos"], full_hits["log2fc"], c=hit_colors,
                   s=MARKER_SIZE, alpha=MARKER_EDGE_ALPHA, edgecolor=EDGE_COLOR,
                   linewidths=0.5, zorder=3)

    texts = []
    for _, row in full_hits.iterrows():
        texts.append(ax.text(row["x_pos"], row["log2fc"] + LABEL_OFFSET, row["gene"],
                             fontsize=LABEL_FONT_SIZE, ha="center", va="bottom", color=LABEL_COLOR_HIT))
    if texts and len(texts) < 1000:
        adjust_text(texts, arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    ax.set_xticks(x_label_positions)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Effect Size (log2 Fold Change)")
    ax.set_title(
        f"Genome-wide Effect Sizes by Gene Location\n"
        f"Thresholds: |log2FC| > {log2fc_threshold}, p < {pval_threshold}\n{subtitle}",
        fontsize=TITLE_FONT_SIZE, pad=TITLE_PADDING
    )
    ax.grid(False)
    ax.legend(frameon=False, loc="upper right")

    if not full_hits.empty:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax)
        cbar.set_label("p-value (smaller = more significant)")

    fig.tight_layout()
    fig.savefig(SAVE_PATH, dpi=300)
    print(f"✅ Plot saved as '{SAVE_PATH}'")
    return fig
