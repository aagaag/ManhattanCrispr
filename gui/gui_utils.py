"""
gui_utils.py
--------------------------------------------------
Shared GUI utility widgets and helpers for the Manhattan Plot Generator.
Includes:
- Dependency auto-installer
- ScrollableFrame
- RedirectText
- ToolTip
"""

import importlib.util
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

# ----------------------------------------------------------------------
# Dependency auto-installer
# ----------------------------------------------------------------------

required_packages = [
    "pandas", "matplotlib", "numpy", "adjustText", "openpyxl",
    "mygene", "requests", "tqdm", "tk", "Pillow"
]

for pkg in required_packages:
    if pkg == "tk":  # Tkinter ships with Python
        continue
    if importlib.util.find_spec(pkg) is None:
        print(f"Installing missing dependency: {pkg}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        except Exception as e:
            print(f"⚠️ Could not install {pkg}: {e}")

# ----------------------------------------------------------------------
# Scrollable Frame
# ----------------------------------------------------------------------

class ScrollableFrame(ttk.Frame):
    """A scrollable frame widget that adds a vertical scrollbar."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scroll binding
        self.scrollable_frame.bind("<Enter>", lambda e: self._bind_mousewheel(canvas))
        self.scrollable_frame.bind("<Leave>", lambda e: self._unbind_mousewheel(canvas))

    def _bind_mousewheel(self, canvas):
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _unbind_mousewheel(self, canvas):
        canvas.unbind_all("<MouseWheel>")

# ----------------------------------------------------------------------
# RedirectText
# ----------------------------------------------------------------------

class RedirectText:
    """Redirect stdout/stderr to a Tkinter Text widget."""
    def __init__(self, widget): self.widget = widget
    def write(self, s):
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.update_idletasks()
    def flush(self): ...

# ----------------------------------------------------------------------
# ToolTip
# ----------------------------------------------------------------------

class ToolTip:
    """Attach descriptive tooltips to any Tkinter widget."""
    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, _=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tip or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=350
        )
        label.pack(ipadx=6, ipady=2)

    def _hide(self, _=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        if self.tip:
            self.tip.destroy()
            self.tip = None
