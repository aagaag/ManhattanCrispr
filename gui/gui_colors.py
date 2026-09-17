"""
gui_colors.py
--------------------------------------------------
Reusable color swatch widgets and safe color conversion.
"""

import tkinter as tk
from tkinter import ttk


def safe_color(v):
    v = str(v).strip()
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
        tk.Tk().winfo_rgb(v)
        return v
    except Exception:
        return "#808080"


def make_color_option(parent, label, var, row, command):
    ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky="e")
    e = ttk.Entry(parent, textvariable=var, width=25)
    e.grid(row=row, column=1, sticky="w")

    c = tk.Canvas(parent, width=24, height=20, relief="solid", bd=1)
    c.grid(row=row, column=2, padx=5)
    c.configure(bg=safe_color(var.get()))

    def _update_color(*_):
        c.configure(bg=safe_color(var.get()))
    var.trace_add("write", _update_color)

    ttk.Button(parent, text="Pick", command=command).grid(row=row, column=3, padx=3)
