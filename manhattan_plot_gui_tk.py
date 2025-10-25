#!/usr/bin/env python3
"""
manhattan_plot_gui_tk.py
--------------------------------------------------
Full-featured, thread-safe Tkinter GUI for the Manhattan Plot Generator.

Features
--------
- Automatic dependency installer (for non-savvy users)
- Tabbed & scrollable Advanced Settings (General, Markers, Bands, Labels, Figure, Paths)
- Color pickers for all colors (including RGBA band colors)
- PNG export size (default 1600×1200 px)
- Thread-safe plotting (no Tkinter race errors)
- Persistent settings (gui_settings.json)
- Matplotlib toolbar, color-coded console, progress & status bars
"""

# ======================================================================
# Dependency Auto-Installer
# ======================================================================

import importlib.util, subprocess, sys

required_packages = [
    "pandas", "matplotlib", "numpy", "adjustText", "openpyxl",
    "mygene", "requests", "tqdm", "tk", "Pillow"
]

for pkg in required_packages:
    if pkg == "tk":  # tkinter ships with Python
        continue
    if importlib.util.find_spec(pkg) is None:
        print(f"📦 Installing missing dependency: {pkg}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        except Exception as e:
            print(f"⚠️ Failed to install {pkg}: {e}")

# ======================================================================
# Imports
# ======================================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import threading, sys, os, json, shutil

import manhattan_plot_core as mp

SETTINGS_FILE = "gui_settings.json"

# ======================================================================
# Utility Classes
# ======================================================================

class ToolTip:
    """Simple tooltip helper."""
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip or not self.text: return
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self.text, background="#ffffe0",
            relief="solid", borderwidth=1, font=("Arial", 9)
        ).pack(ipadx=5, ipady=2)

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class RedirectText:
    """Redirect stdout/stderr to Tkinter Text widget."""
    def __init__(self, widget): self.widget = widget
    def write(self, s):
        tag = None
        if any(k in s for k in ("⚠️", "❌", "Error")): tag = "err"
        elif any(k in s for k in ("✅", "🧬", "💾", "🚀")): tag = "ok"
        if tag:
            self.widget.tag_config(tag, foreground=("red" if tag == "err" else "lime"))
            self.widget.insert(tk.END, s, tag)
        else:
            self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.update_idletasks()
    def flush(self): ...


class ScrollableFrame(ttk.Frame):
    """Scrollable frame used in each settings tab."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        self.scrollable_frame.bind("<Enter>", lambda e: self._bind_mousewheel(canvas))
        self.scrollable_frame.bind("<Leave>", lambda e: self._unbind_mousewheel(canvas))

    def _bind_mousewheel(self, canvas):
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all("<MouseWheel>")

# ======================================================================
# Main GUI
# ======================================================================

class ManhattanGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🧬 Manhattan Plot Generator")
        self.geometry("1320x900")
        self.resizable(True, True)

        self.vars = self._init_vars()
        self.status = tk.StringVar(value="Ready")
        self._load_settings()
        self._create_menu()
        self._create_layout()
        self._create_statusbar()

        sys.stdout = RedirectText(self.txt_log)
        sys.stderr = RedirectText(self.txt_log)

    # ------------------------------------------------------------------
    # Initialize Tk variables
    # ------------------------------------------------------------------
    def _init_vars(self):
        return {
            "excel_path": tk.StringVar(),
            "TEST_MODE": tk.BooleanVar(value=mp.TEST_MODE),
            "TEST_LIMIT": tk.IntVar(value=mp.TEST_LIMIT),
            "USE_CACHE_ONLY": tk.BooleanVar(value=mp.USE_CACHE_ONLY),
            "AUTO_SAVE": tk.BooleanVar(value=True),
            "log2fc": tk.DoubleVar(value=mp.DEFAULT_LOG2FC_THRESHOLD),
            "pval": tk.DoubleVar(value=mp.DEFAULT_PVAL_THRESHOLD),
            "MARKER_SIZE": tk.IntVar(value=mp.MARKER_SIZE),
            "MARKER_EDGE_ALPHA": tk.DoubleVar(value=mp.MARKER_EDGE_ALPHA),
            "NON_HIT_COLOR": tk.StringVar(value=mp.NON_HIT_COLOR),
            "PARTIAL_HIT_COLOR": tk.StringVar(value=mp.PARTIAL_HIT_COLOR),
            "EDGE_COLOR": tk.StringVar(value=mp.EDGE_COLOR),
            "BAND_OPACITY": tk.DoubleVar(value=mp.BAND_OPACITY),
            "BAND_COLOR_EVEN": tk.StringVar(value=str(mp.BAND_COLOR_EVEN)),
            "BAND_COLOR_ODD": tk.StringVar(value=str(mp.BAND_COLOR_ODD)),
            "LABEL_FONT_SIZE": tk.IntVar(value=mp.LABEL_FONT_SIZE),
            "LABEL_OFFSET": tk.DoubleVar(value=mp.LABEL_OFFSET),
            "LABEL_COLOR_HIT": tk.StringVar(value=mp.LABEL_COLOR_HIT),
            "FIG_W": tk.DoubleVar(value=mp.FIG_SIZE[0]),
            "FIG_H": tk.DoubleVar(value=mp.FIG_SIZE[1]),
            "TITLE_FONT_SIZE": tk.IntVar(value=mp.TITLE_FONT_SIZE),
            "TITLE_PADDING": tk.IntVar(value=mp.TITLE_PADDING),
            "SAVE_PATH": tk.StringVar(value=mp.SAVE_PATH),
            "PNG_W": tk.IntVar(value=1600),
            "PNG_H": tk.IntVar(value=1200),
            "CACHE_FILE": tk.StringVar(value=mp.CACHE_FILE),
            "LOG_FILE": tk.StringVar(value=mp.LOG_FILE),
        }

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

        h = tk.Menu(m, tearoff=0)
        h.add_command(label="About", command=lambda: messagebox.showinfo(
            "About",
            "Manhattan Plot Generator (GUI)\n"
            "Version 3.3 — Tabbed, scrollable, with color pickers and auto-installer."))
        m.add_cascade(label="Help", menu=h)

    # ------------------------------------------------------------------
    # Layout (including tabs)
    # ------------------------------------------------------------------
    def _create_layout(self):
        top = ttk.Frame(self, padding=10); top.pack(fill=tk.X, side=tk.TOP)
        ttk.Label(top, text="Excel File:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.vars["excel_path"], width=95).grid(row=0, column=1, padx=5)
        ttk.Button(top, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=5)

        ttk.Label(top, text="log2FC:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(top, textvariable=self.vars["log2fc"], width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(top, text="p-value:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(top, textvariable=self.vars["pval"], width=10).grid(row=2, column=1, sticky="w")

        ttk.Checkbutton(top, text="Test Mode", variable=self.vars["TEST_MODE"]).grid(row=3, column=0, sticky="w")
        ttk.Label(top, text="Test Limit:").grid(row=3, column=1, sticky="w")
        ttk.Entry(top, textvariable=self.vars["TEST_LIMIT"], width=8).grid(row=3, column=1, sticky="e")
        ttk.Checkbutton(top, text="Cache Only", variable=self.vars["USE_CACHE_ONLY"]).grid(row=3, column=2, sticky="w")
        ttk.Checkbutton(top, text="Auto-Save Plot", variable=self.vars["AUTO_SAVE"]).grid(row=3, column=3, sticky="w")

        nb = ttk.Notebook(self, height=300); nb.pack(fill=tk.X, padx=10, pady=6)
        tabs = {
            "General": self._tab_general,
            "Markers & Colors": self._tab_markers,
            "Bands": self._tab_bands,
            "Labels": self._tab_labels,
            "Figure": self._tab_figure,
            "Paths": self._tab_paths
        }

        for name, builder in tabs.items():
            sf = ScrollableFrame(nb)
            nb.add(sf, text=name)
            builder(sf.scrollable_frame)

        ttk.Button(self, text="Run Plot", command=self._thread_run).pack(pady=8)

        pf = ttk.Frame(self, padding=(10,0)); pf.pack(fill=tk.X)
        ttk.Label(pf, text="Progress:").pack(side=tk.LEFT)
        self.pb = ttk.Progressbar(pf, orient="horizontal", length=600, mode="determinate", maximum=100)
        self.pb.pack(side=tk.LEFT, padx=8)

        logf = ttk.Frame(self, padding=10); logf.pack(fill=tk.BOTH, expand=True)
        ttk.Label(logf, text="Progress / Log Output:").pack(anchor="w")
        self.txt_log = tk.Text(logf, wrap="word", height=10, bg="black", fg="white")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        self.plot_frame = ttk.Frame(self, padding=10)
        self.plot_frame.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Tab content builders
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
        self._color_row(f, "NON_HIT_COLOR", "Non-hit color:", 2)
        self._color_row(f, "PARTIAL_HIT_COLOR", "Partial-hit color:", 3)
        self._color_row(f, "EDGE_COLOR", "Edge color:", 4)
        self._color_row(f, "LABEL_COLOR_HIT", "Label color (hit):", 5)

    def _tab_bands(self, f):
        ttk.Label(f, text="BAND_OPACITY:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["BAND_OPACITY"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="Even Band (RGBA):").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["BAND_COLOR_EVEN"], width=24).grid(row=1, column=1, sticky="w")
        ttk.Button(f, text="Pick", command=lambda: self._pick_band_color("BAND_COLOR_EVEN")).grid(row=1, column=2, padx=5)
        ttk.Label(f, text="Odd Band (RGBA):").grid(row=2, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["BAND_COLOR_ODD"], width=24).grid(row=2, column=1, sticky="w")
        ttk.Button(f, text="Pick", command=lambda: self._pick_band_color("BAND_COLOR_ODD")).grid(row=2, column=2, padx=5)

    def _tab_labels(self, f):
        ttk.Label(f, text="LABEL_FONT_SIZE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LABEL_FONT_SIZE"], width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LABEL_OFFSET:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LABEL_OFFSET"], width=8).grid(row=1, column=1, sticky="w")
        self._color_row(f, "LABEL_COLOR_HIT", "Label color:", 2)

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
        ttk.Label(f, text="PNG export size (px):").grid(row=3, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["PNG_W"], width=8).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="×").grid(row=3, column=2, sticky="e")
        ttk.Entry(f, textvariable=self.vars["PNG_H"], width=8).grid(row=3, column=3, sticky="w")
        ttk.Label(f, text="Default 1600×1200 px").grid(row=3, column=4, sticky="w")

    def _tab_paths(self, f):
        ttk.Label(f, text="CACHE_FILE:").grid(row=0, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["CACHE_FILE"], width=50).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="LOG_FILE:").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars["LOG_FILE"], width=50).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="(No browse buttons by design)").grid(row=2, column=0, columnspan=2, sticky="w")

    # ------------------------------------------------------------------
    # Color Picker Helpers
    # ------------------------------------------------------------------
    def _color_row(self, f, key, label, row):
        ttk.Label(f, text=label).grid(row=row, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.vars[key], width=16).grid(row=row, column=1, sticky="w")
        ttk.Button(f, text="Pick", command=lambda: self._pick_color(key)).grid(row=row, column=2, padx=5)

    def _pick_color(self, key):
        rgb, hexval = colorchooser.askcolor(title=f"Choose {key}")
        if hexval:
            self.vars[key].set(hexval)

    def _pick_band_color(self, key):
        rgb, _ = colorchooser.askcolor(title=f"Choose {key} (RGB)")
        if rgb:
            r, g, b = [v/255.0 for v in rgb]
            a = float(self.vars["BAND_OPACITY"].get())
            self.vars[key].set(f"({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f})")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_statusbar(self):
        ttk.Label(self, textvariable=self.status, relief=tk.SUNKEN,
                  anchor="w", padding=5).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # File selection & settings persistence
    # ------------------------------------------------------------------
    def _browse_file(self):
        p = filedialog.askopenfilename(title="Select Excel file",
                                       filetypes=[("Excel Files","*.xlsx"),("All Files","*.*")])
        if p:
            self.vars["excel_path"].set(p)
            self._save_settings()

    def _save_settings(self):
        data = {k:v.get() for k,v in self.vars.items()}
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_settings(self):
        if not os.path.exists(SETTINGS_FILE): return
        try:
            data = json.load(open(SETTINGS_FILE, "r", encoding="utf-8"))
            for k,v in data.items():
                if k in self.vars:
                    try: self.vars[k].set(v)
                    except Exception: pass
        except Exception: pass

    # ------------------------------------------------------------------
    # Threaded plotting
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

            # plot on main thread
            def make_plot():
                self._set_status("Generating plot...", 60)
                mp.plt.close("all")
                fig = mp.plot_manhattan(
                    df, chrom_order,
                    self.vars["log2fc"].get(),
                    self.vars["pval"].get()
                )
                self._display_plot(fig)
                if self.vars["AUTO_SAVE"].get():
                    w_px = self.vars["PNG_W"].get()
                    h_px = self.vars["PNG_H"].get()
                    dpi = 100
                    fig.set_size_inches(w_px / dpi, h_px / dpi)
                    fig.savefig(mp.SAVE_PATH, dpi=dpi)
                    print(f"💾 Auto-saved plot to {mp.SAVE_PATH} ({w_px}×{h_px}px)")
                self._set_status("Plot complete.", 100)
                messagebox.showinfo("Success", "Manhattan plot generated successfully!")

            self.after(0, make_plot)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            print(f"❌ Error: {e}")
        finally:
            self.after(0, lambda: self._set_status("Ready", 0))

    # ------------------------------------------------------------------
    # Display plot
    # ------------------------------------------------------------------
    def _display_plot(self, fig):
        for w in self.plot_frame.winfo_children(): w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self.plot_frame)
        toolbar.update()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Backend sync
    # ------------------------------------------------------------------
    def _apply_to_backend(self):
        for k,v in self.vars.items():
            if hasattr(mp, k):
                try: setattr(mp, k, v.get())
                except Exception: pass
        mp.FIG_SIZE = (self.vars["FIG_W"].get(), self.vars["FIG_H"].get())
        mp.DEFAULT_LOG2FC_THRESHOLD = self.vars["log2fc"].get()
        mp.DEFAULT_PVAL_THRESHOLD = self.vars["pval"].get()
        self._save_settings()

    def _set_status(self, text, prog=None):
        self.after(0, lambda: self.status.set(text))
        if prog is not None:
            self.after(0, lambda: self.pb.config(value=prog))
        self.update_idletasks()

    # ------------------------------------------------------------------
    # File ops & quit
    # ------------------------------------------------------------------
    def _save_plot_as(self):
        if not mp.plt.get_fignums():
            messagebox.showwarning("No Plot","No plot available to save."); return
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG","*.png"),("PDF","*.pdf"),("SVG","*.svg")])
        if p:
            w_px = self.vars["PNG_W"].get()
            h_px = self.vars["PNG_H"].get()
            dpi = 100
            mp.plt.gcf().set_size_inches(w_px / dpi, h_px / dpi)
            mp.plt.gcf().savefig(p, dpi=dpi)
            print(f"💾 Plot saved to {p} ({w_px}×{h_px}px)")

    def _save_log_as(self):
        if not os.path.exists(mp.LOG_FILE):
            messagebox.showwarning("No Log","No log file found."); return
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("Text Files","*.txt"),("All Files","*.*")])
        if p:
            shutil.copy(mp.LOG_FILE, p)
            messagebox.showinfo("Saved", f"Log file saved to:\n{p}")

    def _quit(self):
        self._save_settings()
        self.destroy()

# ======================================================================
# Main
# ======================================================================
if __name__ == "__main__":
    app = ManhattanGUI()
    app.mainloop()
