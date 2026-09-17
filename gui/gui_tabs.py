"""
gui_tabs.py
--------------------------------------------------
Defines all GUI tab layouts for the ManhattanCrispr app.
"""

from tkinter import ttk
from .gui_colors import make_color_option
from .gui_utils import ScrollableFrame
from .gui_settings import pick_color, pick_band_color
from .gui_backend_sync import restore_defaults


class TabsBuilder:
    def __init__(self, app):
        self.app = app

    def build_tabs(self, notebook):
        tabs = {
            "General": self.tab_general,
            "Markers & Colors": self.tab_markers,
            "Bands": self.tab_bands,
            "Labels": self.tab_labels,
            "Figure": self.tab_figure,
            "Paths": self.tab_paths,
            "Databases": self.tab_databases,
        }
        for name, func in tabs.items():
            sf = ScrollableFrame(notebook)
            notebook.add(sf, text=name)
            func(sf.scrollable_frame)

    def tab_general(self, f):
        ttk.Checkbutton(f, text="Test Mode", variable=self.app.vars["TEST_MODE"]).grid(row=0, column=0, sticky="w")
        ttk.Label(f, text="Test Limit:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["TEST_LIMIT"], width=8).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(f, text="Cache Only", variable=self.app.vars["USE_CACHE_ONLY"]).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(f, text="Auto-Save Plot", variable=self.app.vars["AUTO_SAVE"]).grid(row=3, column=0, sticky="w")

        # Restore defaults button
        ttk.Button(f, text="Restore Defaults", command=lambda: restore_defaults(self.app)).grid(row=4, column=0, pady=(10, 0), sticky="w")

    def tab_markers(self, f):
        make_color_option(f, "NON_HIT_COLOR", self.app.vars["NON_HIT_COLOR"], 2, lambda: pick_color(self.app.vars["NON_HIT_COLOR"]))
        make_color_option(f, "PARTIAL_HIT_COLOR", self.app.vars["PARTIAL_HIT_COLOR"], 3, lambda: pick_color(self.app.vars["PARTIAL_HIT_COLOR"]))
        make_color_option(f, "EDGE_COLOR", self.app.vars["EDGE_COLOR"], 4, lambda: pick_color(self.app.vars["EDGE_COLOR"]))
        make_color_option(f, "LABEL_COLOR_HIT", self.app.vars["LABEL_COLOR_HIT"], 5, lambda: pick_color(self.app.vars["LABEL_COLOR_HIT"]))

    def tab_bands(self, f):
        make_color_option(f, "BAND_COLOR_EVEN", self.app.vars["BAND_COLOR_EVEN"], 1,
                          lambda: pick_band_color(self.app.vars["BAND_COLOR_EVEN"], self.app.vars["BAND_OPACITY"]))
        make_color_option(f, "BAND_COLOR_ODD", self.app.vars["BAND_COLOR_ODD"], 2,
                          lambda: pick_band_color(self.app.vars["BAND_COLOR_ODD"], self.app.vars["BAND_OPACITY"]))

    def tab_labels(self, f):
        ttk.Label(f, text="LABEL_FONT_SIZE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["LABEL_FONT_SIZE"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LABEL_OFFSET:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["LABEL_OFFSET"], width=8).grid(row=1, column=1, sticky="w")

    def tab_figure(self, f):
        ttk.Label(f, text="FIG_W:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["FIG_W"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="FIG_H:").grid(row=0, column=2, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["FIG_H"], width=8).grid(row=0, column=3, sticky="w")

    def tab_paths(self, f):
        ttk.Label(f, text="CACHE_FILE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["CACHE_FILE"], width=60).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LOG_FILE:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.app.vars["LOG_FILE"], width=60).grid(row=1, column=1, sticky="w")

    def tab_databases(self, f):
        ttk.Label(f, text="Select databases to use:").grid(row=0, column=0, sticky="w")
        for i, (name, var) in enumerate([
            ("MyGene.info", "USE_MYGENE"),
            ("Ensembl REST", "USE_ENSEMBL"),
            ("NCBI Entrez", "USE_NCBI"),
            ("HGNC", "USE_HGNC")
        ]):
            ttk.Checkbutton(f, text=name, variable=self.app.vars[var]).grid(row=i + 1, column=0, sticky="w")
        ttk.Checkbutton(f, text="Save preferences as default", variable=self.app.vars["SAVE_DB_PREFS"]).grid(row=5, column=0, sticky="w")
