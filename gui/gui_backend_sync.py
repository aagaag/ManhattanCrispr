"""
gui_backend_sync.py
--------------------------------------------------
Handles synchronization between GUI variables and
the core backend (manhattan_plot_core).
Also manages saving/loading settings and restoring defaults.
"""

from .gui_settings import save_settings, make_default_vars
from core import manhattan_plot_core as mp


def apply_to_backend(vars):
    """Transfer GUI variable values to backend settings."""
    mp.USE_CACHE_ONLY = vars["USE_CACHE_ONLY"].get()
    mp.USE_MYGENE = vars["USE_MYGENE"].get()
    mp.USE_ENSEMBL = vars["USE_ENSEMBL"].get()
    mp.USE_NCBI = vars["USE_NCBI"].get()
    mp.USE_HGNC = vars["USE_HGNC"].get()
    mp.FIG_SIZE = (vars["FIG_W"].get(), vars["FIG_H"].get())
    mp.DEFAULT_LOG2FC_THRESHOLD = vars["log2fc"].get()
    mp.DEFAULT_PVAL_THRESHOLD = vars["pval"].get()
    if vars["SAVE_DB_PREFS"].get():
        save_settings(vars)


def restore_defaults(app):
    """
    Restore all GUI settings to defaults.
    Recreates Tk variables and applies them to the current GUI.
    """
    print("🔄 Restoring default settings...")
    defaults = make_default_vars(mp)
    for k, v in defaults.items():
        if k in app.vars:
            try:
                app.vars[k].set(v.get())
            except Exception:
                pass
    save_settings(app.vars)
    app.status.set("Defaults restored.")
    print("✅ All defaults restored.")
