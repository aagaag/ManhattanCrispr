"""
gui_main.py
--------------------------------------------------
Main Tkinter application window for the Manhattan Plot Generator.

Features
--------
- Modular, tabbed, scrollable interface
- Detailed tooltips for all options
- RGBA-safe color swatches showing current selections
- Scalable plot preview window
- Export format selection (PNG/SVG/PDF/EPS)
- Persistent settings and dependency auto-installation
- Thread-safe plotting
"""

import os, threading, shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import manhattan_plot_core as mp
from .gui_utils import ScrollableFrame, RedirectText, ToolTip
from .gui_settings import make_default_vars, save_settings, load_settings, pick_color, pick_band_color


class ManhattanGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🧬 Manhattan Plot Generator")
        self.geometry("1300x900")
        self.resizable(True, True)

        # Initialize variables
        self.vars = make_default_vars(mp)
        self.status = tk.StringVar(value="Ready")

        # Load saved settings
        load_settings(self.vars)

        # Build interface
        self._create_menu()
        self._create_layout()
        self._create_statusbar()

        # Redirect stdout/stderr to GUI
        import sys
        sys.stdout = RedirectText(self.txt_log)
        sys.stderr = RedirectText(self.txt_log)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _create_menu(self):
        m = tk.Menu(self); self.config(menu=m)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Save Plot As...", command=self._save_plot_as)
        f.add_command(label="Save Log As...", command=self._save_log_as)
        f.add_separator()
        f.add_command(label="Exit", command=self._quit)
        m.add_cascade(label="File", menu=f)

    # ------------------------------------------------------------------
    # Layout (top + tabs + log)
    # ------------------------------------------------------------------
    def _create_layout(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X, side=tk.TOP)

        ttk.Label(top, text="Excel File:").grid(row=0, column=0, sticky="w")
        e = ttk.Entry(top, textvariable=self.vars["excel_path"], width=95)
        e.grid(row=0, column=1, padx=5)
        ToolTip(e, "Full path to the Excel (.xlsx) file containing gene data.")
        b = ttk.Button(top, text="Browse", command=self._browse_file)
        b.grid(row=0, column=2, padx=5)
        ToolTip(b, "Open a file dialog to select the Excel dataset.")

        ttk.Label(top, text="log2FC:").grid(row=1, column=0, sticky="w")
        fc = ttk.Entry(top, textvariable=self.vars["log2fc"], width=10)
        fc.grid(row=1, column=1, sticky="w")
        ToolTip(fc, "Absolute log2 fold-change threshold for calling a gene a hit.")

        ttk.Label(top, text="p-value:").grid(row=2, column=0, sticky="w")
        pv = ttk.Entry(top, textvariable=self.vars["pval"], width=10)
        pv.grid(row=2, column=1, sticky="w")
        ToolTip(pv, "Maximum p-value threshold for significance.")

        c1 = ttk.Checkbutton(top, text="Test Mode", variable=self.vars["TEST_MODE"])
        c1.grid(row=3, column=0, sticky="w")
        ToolTip(c1, "Process only a limited number of genes (defined by Test Limit).")

        c2 = ttk.Checkbutton(top, text="Cache Only", variable=self.vars["USE_CACHE_ONLY"])
        c2.grid(row=3, column=1, sticky="w")
        ToolTip(c2, "Use only cached coordinates in /data; skip online lookups.")

        c3 = ttk.Checkbutton(top, text="Auto-Save Plot", variable=self.vars["AUTO_SAVE"])
        c3.grid(row=3, column=2, sticky="w")
        ToolTip(c3, "Automatically save the generated plot when complete.")

        # Tabs
        nb = ttk.Notebook(self, height=350)
        nb.pack(fill=tk.X, padx=10, pady=6)

        for name, builder in {
            "General": self._tab_general,
            "Markers & Colors": self._tab_markers,
            "Bands": self._tab_bands,
            "Labels": self._tab_labels,
            "Figure": self._tab_figure,
            "Paths": self._tab_paths
        }.items():
            sf = ScrollableFrame(nb)
            nb.add(sf, text=name)
            builder(sf.scrollable_frame)

        # Run button + progress bar
        btn = ttk.Button(self, text="Run Plot", command=self._thread_run)
        btn.pack(pady=8)
        ToolTip(btn, "Start generating the Manhattan plot.")

        pf = ttk.Frame(self, padding=(10, 0))
        pf.pack(fill=tk.X)
        ttk.Label(pf, text="Progress:").pack(side=tk.LEFT)
        self.pb = ttk.Progressbar(pf, orient="horizontal", length=600, mode="determinate", maximum=100)
        self.pb.pack(side=tk.LEFT, padx=8)
        ToolTip(self.pb, "Displays progress during coordinate fetching and plotting.")

        # Log console
        logf = ttk.Frame(self, padding=10)
        logf.pack(fill=tk.BOTH, expand=True)
        ttk.Label(logf, text="Progress / Log Output:").pack(anchor="w")
        self.txt_log = tk.Text(logf, wrap="word", height=10, bg="black", fg="white")
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        ToolTip(self.txt_log, "Shows real-time log messages and warnings.")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_statusbar(self):
        bar = ttk.Label(self, textvariable=self.status, relief=tk.SUNKEN, anchor="w", padding=5)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # RGBA-safe color entry + swatch + picker helper
    # ------------------------------------------------------------------
    def _color_option(self, parent, label, var, row, command):
        """Create a labeled color entry with a live swatch and 'Pick' button."""
        ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky="e")
        e = ttk.Entry(parent, textvariable=var, width=25)
        e.grid(row=row, column=1, sticky="w")
        ToolTip(e, f"Hex (#RRGGBB) or RGBA (r,g,b,a) color for {label}.")

        def safe_color(v):
            """Convert RGBA tuple string to #RRGGBB for Tkinter."""
            v = v.strip()
            if v.startswith("(") and "," in v:
                try:
                    parts = [float(x) for x in v.strip("()").split(",")[:3]]
                    r, g, b = [int(max(0, min(1, p)) * 255) for p in parts]
                    return f"#{r:02x}{g:02x}{b:02x}"
                except Exception:
                    return "#808080"
            if v.startswith("#"):
                return v
            try:
                self.winfo_rgb(v)
                return v
            except Exception:
                return "#808080"

        c = tk.Canvas(parent, width=24, height=20, relief="solid", bd=1)
        c.grid(row=row, column=2, padx=5)
        c.configure(bg=safe_color(var.get()))
        ToolTip(c, f"Current color for {label} (alpha ignored).")

        def _update_color(*_):
            c.configure(bg=safe_color(var.get()))
        var.trace_add("write", _update_color)

        b = ttk.Button(parent, text="Pick", command=command)
        b.grid(row=row, column=3, padx=3)
        ToolTip(b, f"Choose a new color for {label}.")

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _tab_general(self, f):
        ttk.Checkbutton(f, text="Test Mode", variable=self.vars["TEST_MODE"]).grid(row=0, column=0, sticky="w")
        ttk.Label(f, text="Test Limit:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["TEST_LIMIT"], width=8).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(f, text="Cache Only", variable=self.vars["USE_CACHE_ONLY"]).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(f, text="Auto-Save Plot", variable=self.vars["AUTO_SAVE"]).grid(row=3, column=0, sticky="w")

    def _tab_markers(self, f):
        ttk.Label(f, text="MARKER_SIZE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["MARKER_SIZE"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="EDGE_ALPHA:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["MARKER_EDGE_ALPHA"], width=8).grid(row=1, column=1, sticky="w")

        # RGBA-safe color fields
        self._color_option(f, "NON_HIT_COLOR",     self.vars["NON_HIT_COLOR"],     2,
                           lambda: pick_color(self.vars["NON_HIT_COLOR"]))
        self._color_option(f, "PARTIAL_HIT_COLOR", self.vars["PARTIAL_HIT_COLOR"], 3,
                           lambda: pick_color(self.vars["PARTIAL_HIT_COLOR"]))
        self._color_option(f, "EDGE_COLOR",        self.vars["EDGE_COLOR"],        4,
                           lambda: pick_color(self.vars["EDGE_COLOR"]))
        self._color_option(f, "LABEL_COLOR_HIT",   self.vars["LABEL_COLOR_HIT"],   5,
                           lambda: pick_color(self.vars["LABEL_COLOR_HIT"]))

    def _tab_bands(self, f):
        ttk.Label(f, text="BAND_OPACITY:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["BAND_OPACITY"], width=8).grid(row=0, column=1, sticky="w")

        # RGBA-safe color fields
        self._color_option(f, "BAND_COLOR_EVEN", self.vars["BAND_COLOR_EVEN"], 1,
                           lambda: pick_band_color(self.vars["BAND_COLOR_EVEN"], self.vars["BAND_OPACITY"]))
        self._color_option(f, "BAND_COLOR_ODD",  self.vars["BAND_COLOR_ODD"],  2,
                           lambda: pick_band_color(self.vars["BAND_COLOR_ODD"],  self.vars["BAND_OPACITY"]))

    def _tab_labels(self, f):
        ttk.Label(f, text="LABEL_FONT_SIZE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LABEL_FONT_SIZE"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LABEL_OFFSET:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LABEL_OFFSET"], width=8).grid(row=1, column=1, sticky="w")

    def _tab_figure(self, f):
        ttk.Label(f, text="FIG_W:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["FIG_W"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="FIG_H:").grid(row=0, column=2, sticky="e")
        ttk.Entry(f, textvariable=self.vars["FIG_H"], width=8).grid(row=0, column=3, sticky="w")

        ttk.Label(f, text="TITLE_FONT_SIZE:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["TITLE_FONT_SIZE"], width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="TITLE_PADDING:").grid(row=1, column=2, sticky="e")
        ttk.Entry(f, textvariable=self.vars["TITLE_PADDING"], width=8).grid(row=1, column=3, sticky="w")

        ttk.Label(f, text="SAVE_PATH:").grid(row=2, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["SAVE_PATH"], width=50).grid(row=2, column=1, columnspan=3, sticky="w")

        ttk.Label(f, text="Export size (px):").grid(row=3, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["PNG_W"], width=8).grid(row=3, column=1, sticky="w")
        ttk.Entry(f, textvariable=self.vars["PNG_H"], width=8).grid(row=3, column=3, sticky="w")

        ttk.Label(f, text="Export format:").grid(row=4, column=0, sticky="e")
        formats = ["png", "svg", "pdf", "eps"]
        ttk.OptionMenu(f, self.vars["EXPORT_FORMAT"], self.vars["EXPORT_FORMAT"].get(), *formats).grid(row=4, column=1, sticky="w")

    def _tab_paths(self, f):
        ttk.Label(f, text="CACHE_FILE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["CACHE_FILE"], width=60).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LOG_FILE:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LOG_FILE"], width=60).grid(row=1, column=1, sticky="w")

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------
    def _browse_file(self):
        p = filedialog.askopenfilename(title="Select Excel file",
                                       filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")])
        if p:
            self.vars["excel_path"].set(p)
            save_settings(self.vars)

    # ------------------------------------------------------------------
    # Threaded plotting workflow
    # ------------------------------------------------------------------
    def _thread_run(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        self._set_status("Running...", 5)
        path = self.vars["excel_path"].get()
        if not path or not os.path.exists(path):
            self.after(0, lambda: messagebox.showerror("Error", "Please select a valid Excel file."))
            return
        self._apply_to_backend()
        try:
            self._set_status("Fetching coordinates...", 10)
            df, chrom_order = mp.load_data(path)
            self.after(0, lambda: self._make_plot(df, chrom_order))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.after(0, lambda: self._set_status("Ready", 0))

    # ------------------------------------------------------------------
    # Plotting + scalable preview window
    # ------------------------------------------------------------------
    def _make_plot(self, df, chrom_order):
        self._set_status("Generating plot...", 60)
        mp.plt.close("all")
        fig = mp.plot_manhattan(df, chrom_order,
                                self.vars["log2fc"].get(),
                                self.vars["pval"].get())
        self._display_plot(fig)

        if self.vars["AUTO_SAVE"].get():
            fmt = self.vars["EXPORT_FORMAT"].get().lower()
            w, h, dpi = self.vars["PNG_W"].get(), self.vars["PNG_H"].get(), 100
            fig.set_size_inches(w / dpi, h / dpi)
            base, _ = os.path.splitext(mp.SAVE_PATH)
            path = f"{base}.{fmt}"
            if fmt in ("svg", "pdf", "eps"):
                fig.savefig(path, format=fmt)
            else:
                fig.savefig(path, dpi=dpi)
            print(f"Auto-saved plot to {path} ({w}×{h}px @ {dpi} DPI)")
        self._set_status("Plot complete.", 100)

    def _display_plot(self, fig):
        win = tk.Toplevel(self)
        win.title("Manhattan Plot Preview")
        win.geometry("1000x800")
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)
        canvas = FigureCanvasTkAgg(fig, master=frame)
        toolbar = NavigationToolbar2Tk(canvas, frame)
        toolbar.update()
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        def _on_close():
            try:
                mp.plt.close(fig)
            except Exception:
                pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)
        win.lift()
        win.focus_force()

    # ------------------------------------------------------------------
    # Apply settings, save, status
    # ------------------------------------------------------------------
    def _apply_to_backend(self):
        for k, v in self.vars.items():
            if hasattr(mp, k):
                try:
                    setattr(mp, k, v.get())
                except Exception:
                    pass
        mp.FIG_SIZE = (self.vars["FIG_W"].get(), self.vars["FIG_H"].get())
        save_settings(self.vars)

    def _save_plot_as(self):
        p = filedialog.asksaveasfilename(
            defaultextension=f".{self.vars['EXPORT_FORMAT'].get()}",
            filetypes=[
                ("PNG image", "*.png"),
                ("SVG vector", "*.svg"),
                ("PDF document", "*.pdf"),
                ("EPS vector", "*.eps"),
                ("All files", "*.*"),
            ],
        )
        if p:
            ext = os.path.splitext(p)[1].lstrip(".").lower()
            fig = mp.plt.gcf()
            w, h, dpi = self.vars["PNG_W"].get(), self.vars["PNG_H"].get(), 100
            # PNG uses pixel size; vector ignores DPI
            if ext == "png":
                fig.set_size_inches(w / dpi, h / dpi)
                fig.savefig(p, dpi=dpi)
            else:
                fig.savefig(p, format=ext)
            print(f"Saved plot to {p}")

    def _save_log_as(self):
        if not os.path.exists(mp.LOG_FILE):
            messagebox.showwarning("No Log", "No log file found.")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")]
        )
        if p:
            shutil.copy(mp.LOG_FILE, p)
            messagebox.showinfo("Saved", f"Log file saved to:\n{p}")

    def _quit(self):
        save_settings(self.vars)
        self.destroy()

    def _set_status(self, text, prog=None):
        self.after(0, lambda: self.status.set(text))
        if prog is not None:
            self.after(0, lambda: self.pb.config(value=prog))
        self.update_idletasks()
