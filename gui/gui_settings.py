"""
gui_settings.py
--------------------------------------------------
Defines Tkinter variables for the ManhattanCrispr GUI
and handles saving/loading persistent user settings.
"""

import os, json, tkinter as tk
from tkinter import colorchooser

# ----------------------------------------------------------------------
# Default variable definitions
# ----------------------------------------------------------------------
def make_default_vars(mp):
    """Create a dictionary of Tkinter variables with sensible defaults."""
    vars = {
        # Core thresholds and file paths
        "excel_path": tk.StringVar(value=""),
        "TEST_MODE": tk.BooleanVar(value=mp.TEST_MODE),
        "TEST_LIMIT": tk.IntVar(value=mp.TEST_LIMIT),
        "USE_CACHE_ONLY": tk.BooleanVar(value=mp.USE_CACHE_ONLY),
        "AUTO_SAVE": tk.BooleanVar(value=True),

        # Thresholds
        "log2fc": tk.DoubleVar(value=mp.DEFAULT_LOG2FC_THRESHOLD),
        "pval": tk.DoubleVar(value=mp.DEFAULT_PVAL_THRESHOLD),

        # Marker appearance
        "MARKER_SIZE": tk.IntVar(value=mp.MARKER_SIZE),
        "MARKER_EDGE_ALPHA": tk.DoubleVar(value=mp.MARKER_EDGE_ALPHA),
        "NON_HIT_COLOR": tk.StringVar(value=mp.NON_HIT_COLOR),
        "PARTIAL_HIT_COLOR": tk.StringVar(value=mp.PARTIAL_HIT_COLOR),
        "EDGE_COLOR": tk.StringVar(value=mp.EDGE_COLOR),
        "LABEL_COLOR_HIT": tk.StringVar(value=mp.LABEL_COLOR_HIT),

        # Chromosome bands
        "BAND_OPACITY": tk.DoubleVar(value=mp.BAND_OPACITY),
        "BAND_COLOR_EVEN": tk.StringVar(value=str(mp.BAND_COLOR_EVEN)),
        "BAND_COLOR_ODD": tk.StringVar(value=str(mp.BAND_COLOR_ODD)),

        # Labels and figure
        "LABEL_FONT_SIZE": tk.IntVar(value=mp.LABEL_FONT_SIZE),
        "LABEL_OFFSET": tk.DoubleVar(value=mp.LABEL_OFFSET),
        "FIG_W": tk.DoubleVar(value=mp.FIG_SIZE[0]),
        "FIG_H": tk.DoubleVar(value=mp.FIG_SIZE[1]),
        "TITLE_FONT_SIZE": tk.IntVar(value=mp.TITLE_FONT_SIZE),
        "TITLE_PADDING": tk.IntVar(value=mp.TITLE_PADDING),
        "SAVE_PATH": tk.StringVar(value=mp.SAVE_PATH),
        "PNG_W": tk.IntVar(value=1600),
        "PNG_H": tk.IntVar(value=1200),
        "EXPORT_FORMAT": tk.StringVar(value="png"),

        # File paths
        "CACHE_FILE": tk.StringVar(value=mp.CACHE_FILE),
        "LOG_FILE": tk.StringVar(value=mp.LOG_FILE),

        # Database selection (NEW)
        "USE_MYGENE": tk.BooleanVar(value=mp.USE_MYGENE),
        "USE_ENSEMBL": tk.BooleanVar(value=mp.USE_ENSEMBL),
        "USE_NCBI": tk.BooleanVar(value=mp.USE_NCBI),
        "USE_HGNC": tk.BooleanVar(value=mp.USE_HGNC),
        "SAVE_DB_PREFS": tk.BooleanVar(value=True),
    }
    return vars

# ----------------------------------------------------------------------
# Save and load settings
# ----------------------------------------------------------------------

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "gui_settings.json")

def save_settings(vars_dict):
    """Save current GUI state to a JSON file."""
    data = {}
    for k, v in vars_dict.items():
        try:
            data[k] = v.get()
        except Exception:
            pass
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Settings saved to {SETTINGS_FILE}")

def load_settings(vars_dict):
    """Load saved GUI settings if available."""
    if not os.path.exists(SETTINGS_FILE):
        print("No saved settings found.")
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in vars_dict:
                try:
                    vars_dict[k].set(v)
                except Exception:
                    pass
        print(f"Settings loaded from {SETTINGS_FILE}")
    except Exception as e:
        print(f"⚠️ Failed to load settings: {e}")

# ----------------------------------------------------------------------
# Color picker helpers
# ----------------------------------------------------------------------
def pick_color(var):
    """Open a color chooser and update the variable with selected color."""
    rgb, hexval = colorchooser.askcolor(title="Choose Color")
    if hexval:
        var.set(hexval)

def pick_band_color(var, opacity_var):
    """Pick a color for chromosome band, store as RGBA tuple string."""
    rgb, _ = colorchooser.askcolor(title="Choose Band Color (RGB)")
    if rgb:
        r, g, b = [v/255.0 for v in rgb]
        a = float(opacity_var.get())
        var.set(f"({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f})")
