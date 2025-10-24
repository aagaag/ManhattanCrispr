# 🧬 Manhattan Plot Generator (GUI Version)

A Python tool for visualizing genome-wide gene effects (e.g., log2 fold change vs. p-value)
in a Manhattan-style plot. It features an interactive GUI file picker, dynamic thresholds,
and publication-ready graphics.

## ✨ Features
- GUI file picker (no hard-coded paths)
- Interactive user prompts for |log2FC| and p-value thresholds
- Automatic dependency installation (first run only)
- Classification of genes into full hits, partial hits, and non-hits
- Alternating 3% green/magenta chromosome background bands
- Auto-adjusted gene labels to avoid overlap
- Publication-quality PNG output

## 📁 Input Format
Excel file (.xlsx) with columns (case-insensitive):
`gene`, `chromosome`, `start_position`, `log2FC`, `p-value`

## 🚀 Quick Start
```bash
python3 manhattan_plot_gui.py
```
1) A file picker opens — choose your .xlsx file.
2) Enter thresholds (defaults: |log2FC|>0.3, p<0.03).
3) The plot appears and is saved as `manhattan_plot_gui.png`.

## 🧰 Requirements
Python ≥ 3.9. Install manually if desired:
```bash
pip install -r requirements.txt
```

## 📊 Example Output
![Example plot](screenshots/example_plot.png)

## 📜 License
MIT License © 2025 Your Name

## 🧠 Citation
If you use this tool in your research, please cite:
> Your Name, *Manhattan Plot Generator (v1.0)*, GitHub repository, 2025.
