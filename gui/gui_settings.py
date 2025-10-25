"""
gui_settings.py
--------------------------------------------------
Handles GUI state persistence (save/load settings),
default variable creation, and color picker helpers.
"""

import os
import json
import os, json, tkinter as tk
from tkinter import colorchooser

# ----------------------------------------------------------------------
# Path for settings file
# ----------------------------------------------------------------------

# Always store GUI settings inside the /gui directory
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "gui_settings.json")

# ----------------------------------------------------------------------
# Default variable setup
# ----------------------------------------------------------------------

def make_default_vars(mp):
    """Create Tkinter variables initialized from the manhattan_plot_core defaults."""
    return {
        # Basic paths and options
        "excel_path": tk.StringVar(),
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

        # Bands
        "BAND_OPACITY": tk.DoubleVar(value=mp.BAND_OPACITY),
        "BAND_COLOR_EVEN": tk.StringVar(value=str(mp.BAND_COLOR_EVEN)),
        "BAND_COLOR_ODD": tk.StringVar(value=str(mp.BAND_COLOR_ODD)),

        # Labels
        "LABEL_FONT_SIZE": tk.IntVar(value=mp.LABEL_FONT_SIZE),
        "LABEL_OFFSET": tk.DoubleVar(value=mp.LABEL_OFFSET),
        "LABEL_COLOR_HIT": tk.StringVar(value=mp.LABEL_COLOR_HIT),

        # Figure & layout
        "FIG_W": tk.DoubleVar(value=mp.FIG_SIZE[0]),
        "FIG_H": tk.DoubleVar(value=mp.FIG_SIZE[1]),
        "TITLE_FONT_SIZE": tk.IntVar(value=mp.TITLE_FONT_SIZE),
        "TITLE_PADDING": tk.IntVar(value=mp.TITLE_PADDING),

        # File paths & export options
        "SAVE_PATH": tk.StringVar(value=mp.SAVE_PATH),
        "PNG_W": tk.IntVar(value=1600),
        "PNG_H": tk.IntVar(value=1200),
        "EXPORT_FORMAT": tk.StringVar(value="png"),

        # Cache & log files (pointing to /data)
        "CACHE_FILE": tk.StringVar(value=mp.CACHE_FILE),
        "LOG_FILE": tk.StringVar(value=mp.LOG_FILE),
    }

# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------

def save_settings(vars_dict):
    """Save all Tk variable values to gui_settings.json."""
    data = {k: v.get() for k, v in vars_dict.items()}
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Settings saved to {SETTINGS_FILE}")
    except Exception as e:
        print(f"⚠️ Could not save settings: {e}")


def load_settings(vars_dict):
    """Load variable values from gui_settings.json if it exists."""
    if not os.path.exists(SETTINGS_FILE):
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
        print(f"⚠️ Could not load settings: {e}")

# ----------------------------------------------------------------------
# Color picker helpers
# ----------------------------------------------------------------------

def pick_color(var):
    """Open a color picker and store hex value in given variable."""
    rgb, hexval = colorchooser.askcolor(title="Choose color")
    if hexval:
        var.set(hexval)

def pick_band_color(var, opacity):
    """Pick RGB color for chromosome band background; append alpha from BAND_OPACITY."""
    rgb, _ = colorchooser.askcolor(title="Choose band color (RGB)")
    if rgb:
        r, g, b = [v / 255.0 for v in rgb]
        a = float(opacity.get())
        var.set(f"({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f})")
