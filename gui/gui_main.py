"""
gui_main.py
--------------------------------------------------
Main controller for the Manhattan Plot Generator GUI.
This file now handles only:
  • Window creation
  • Layout and tab loading
  • Thread management and plotting
  • File I/O (saving plots/logs)
All detailed UI logic (tabs, color pickers, backend sync) lives in
dedicated submodules inside the `gui` package.
"""

import os, threading, shutil, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# --- internal imports
from .gui_utils import RedirectText
from .gui_settings import make_default_vars, save_settings, load_settings
from .gui_tabs import TabsBuilder
from .gui_backend_sync import apply_to_backend
from core import manhattan_plot_core as mp


class ManhattanGUI(tk.Tk):
    """Main GUI application window."""

    def __init__(self):
        super().__init__()
        self.title("🧬 Manhattan Plot Generator")
        self.geometry("1300x900")
        self.resizable(True, True)

        # Initialize app state
        self.vars = make_default_vars(mp)
        self.status = tk.StringVar(value="Ready")
        load_settings(self.vars)

        # Build interface
        self._create_menu()
        self._create_layout()
        self._create_statusbar()

        # Redirect stdout/stderr to GUI text box
        import sys
        sys.stdout = RedirectText(self.txt_log)
        sys.stderr = RedirectText(self.txt_log)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Plot As...", command=self._save_plot_as)
        file_menu.add_command(label="Save Log As...", command=self._save_log_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._quit)
        menubar.add_cascade(label="File", menu=file_menu)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _create_layout(self):
        """Builds the top controls, notebook tabs, and log console."""
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X, side=tk.TOP)

        # --- File selection
        ttk.Label(top, text="Excel File:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.vars["excel_path"], width=95).grid(row=0, column=1, padx=5)
        ttk.Button(top, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=5)

        # --- Thresholds
        ttk.Label(top, text="log2FC:").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.vars["log2fc"], width=10).grid(row=1, column=1, sticky="w")
        ttk.Label(top, text="p-value:").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.vars["pval"], width=10).grid(row=2, column=1, sticky="w")

        # --- Tabs
        notebook = ttk.Notebook(self, height=350)
        notebook.pack(fill=tk.X, padx=10, pady=6)
        self.tabs = TabsBuilder(self)
        self.tabs.build_tabs(notebook)

        # --- Run button and progress bar
        ttk.Button(self, text="Run Plot", command=self._thread_run).pack(pady=8)

        progress_frame = ttk.Frame(self, padding=(10, 0))
        progress_frame.pack(fill=tk.X)
        ttk.Label(progress_frame, text="Progress:").pack(side=tk.LEFT)
        self.pb = ttk.Progressbar(progress_frame, orient="horizontal",
                                  length=600, mode="determinate", maximum=100)
        self.pb.pack(side=tk.LEFT, padx=8)

        # --- Log box
        self.txt_log = tk.Text(self, wrap="word", height=10, bg="black", fg="white")
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_statusbar(self):
        """Simple status bar at bottom of window."""
        ttk.Label(self, textvariable=self.status,
                  relief=tk.SUNKEN, anchor="w", padding=5).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------
    def _browse_file(self):
        """Open file dialog to select Excel file."""
        path = filedialog.askopenfilename(
            title="Select Excel file",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")]
        )
        if path:
            self.vars["excel_path"].set(path)
            save_settings(self.vars)

    # ------------------------------------------------------------------
    # Plot execution (threaded)
    # ------------------------------------------------------------------
    def _thread_run(self):
        """Run the analysis and plotting in a worker thread."""
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        """Background job to load data, run analysis, and update UI."""
        self._set_status("Running...", 10)
        path = self.vars["excel_path"].get()

        if not path or not os.path.exists(path):
            messagebox.showerror("Error", "Please select a valid Excel file.")
            return

        # Sync GUI vars to backend config
        apply_to_backend(self.vars)

        try:
            self._set_status("Loading data...", 20)
            df, chrom_order = mp.load_data(path)
            self._set_status("Plotting...", 70)
            self._make_plot(df, chrom_order)
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self._set_status("Ready", 0)

    # ------------------------------------------------------------------
    # Plot rendering
    # ------------------------------------------------------------------
    def _make_plot(self, df, chrom_order):
        """Generate and display the Manhattan plot in a separate window."""
        fig = mp.plot_manhattan(df, chrom_order,
                                self.vars["log2fc"].get(),
                                self.vars["pval"].get())

        win = tk.Toplevel(self)
        win.title("Manhattan Plot Preview")
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)

        canvas = FigureCanvasTkAgg(fig, master=frame)
        toolbar = NavigationToolbar2Tk(canvas, frame)
        toolbar.update()
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def _save_plot_as(self):
        """Save current figure to user-chosen format."""
        p = filedialog.asksaveasfilename(
            defaultextension=f".{self.vars['EXPORT_FORMAT'].get()}",
            filetypes=[
                ("PNG Image", "*.png"),
                ("SVG Vector", "*.svg"),
                ("PDF Document", "*.pdf"),
                ("EPS Vector", "*.eps"),
                ("All Files", "*.*"),
            ],
        )
        if not p:
            return
        fig = mp.plt.gcf()
        ext = os.path.splitext(p)[1].lstrip(".").lower()
        fig.savefig(p, format=ext)
        print(f"💾 Plot saved to {p}")

    def _save_log_as(self):
        """Save coordinate fetch log to another location."""
        if not os.path.exists(mp.LOG_FILE):
            messagebox.showwarning("No Log", "No log file found.")
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if dest:
            shutil.copy(mp.LOG_FILE, dest)
            messagebox.showinfo("Saved", f"Log file saved to:\n{dest}")

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def _quit(self):
        """Save settings and close the app."""
        save_settings(self.vars)
        self.destroy()

    def _set_status(self, text, progress=None):
        """Update status bar and progress bar."""
        self.status.set(text)
        if progress is not None:
            self.pb.config(value=progress)
        self.update_idletasks()
