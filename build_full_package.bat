@echo off
setlocal
chcp 65001 >nul
echo ============================================
echo   ManhattanCrispr_v1 Universal Build Script
echo ============================================

:: ------------------------------------------------------------
:: Verify Python installation
:: ------------------------------------------------------------
python --version >nul 2>&1 || (
    echo [ERROR] Python not found! Please install Python 3.9 or newer.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: Install / update PyInstaller
:: ------------------------------------------------------------
echo [INFO] Installing or updating PyInstaller...
python -m pip install --upgrade pip --no-warn-script-location >nul
python -m pip install pyinstaller --no-warn-script-location >nul

:: ------------------------------------------------------------
:: Clean previous builds
:: ------------------------------------------------------------
echo [INFO] Cleaning old build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist release rmdir /s /q release

:: ------------------------------------------------------------
:: Build Windows executable
:: ------------------------------------------------------------
echo [INFO] Building Windows executable...
python -m PyInstaller --onefile --windowed --name "ManhattanCrispr_v1" manhattan_plot_gui_tk.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Windows build failed!
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: Attempt to build macOS app (only succeeds on macOS)
:: ------------------------------------------------------------
echo [INFO] Building macOS app (will only succeed on macOS)...
python -m PyInstaller --onefile --windowed --name "ManhattanCrispr_v1_mac" manhattan_plot_gui_tk.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] macOS app build failed (expected on Windows).
)

:: ------------------------------------------------------------
:: Create README.md
:: ------------------------------------------------------------
echo [INFO] Creating README.md...
(
echo # ManhattanCrispr_v1
echo
echo **Developer:** Adriano Aguzzi
echo
echo A cross-platform desktop application for generating genome-wide Manhattan plots.
echo
echo ## Features
echo - Fully graphical Tkinter interface
echo - Automatic dependency installation
echo - Color pickers for all configurable colors
echo - Adjustable PNG export size \(default 1600×1200 px\)
echo - Thread-safe plotting \(no GUI freezes\)
echo - Caching and logging using MyGene/Ensembl coordinate fetching
echo
echo ## Requirements
echo - Python 3.9 or later
echo - Internet access for coordinate fetching \(optional\)
echo
echo ## Usage
echo 1. Run `python manhattan_plot_gui_tk.py`
echo 2. Select an Excel file with columns:
echo    ```
echo    Gene, log2FC, p-value
echo    ```
echo    Optional columns:
echo    ```
echo    Chromosome, start_position
echo    ```
echo 3. Adjust parameters and click **Run Plot**.
echo
echo ## Building Executables
echo
echo ### Windows
echo Run:
echo ```
echo build_executables.bat
echo ```
echo
echo ### macOS
echo Run in Terminal:
echo ```
echo chmod +x build_mac.sh
echo ./build_mac.sh
echo ```
echo
echo ## Package Contents
echo - manhattan_plot_core.py
echo - manhattan_plot_gui_tk.py
echo - ManhattanCrispr_v1.exe  \(Windows app\)
echo - ManhattanCrispr_v1_mac.exe  \(macOS placeholder built on Windows\)
echo - README.md
echo
echo ## Notes
echo - Dependencies install automatically on first launch.
echo - On macOS, right-click → *Open* to bypass Gatekeeper.
echo
echo ## Contact
echo Developed by **Adriano Aguzzi**, 2025.
) > README.md

:: ------------------------------------------------------------
:: Create ZIP package
:: ------------------------------------------------------------
echo [INFO] Creating ManhattanCrispr_v1.zip...
mkdir release >nul 2>&1

copy manhattan_plot_core.py release >nul
copy manhattan_plot_gui_tk.py release >nul
copy README.md release >nul
if exist dist\ManhattanCrispr_v1.exe copy dist\ManhattanCrispr_v1.exe release >nul
if exist dist\ManhattanCrispr_v1_mac.exe copy dist\ManhattanCrispr_v1_mac.exe release >nul

powershell -command "Compress-Archive -Path 'release\*' -DestinationPath 'ManhattanCrispr_v1.zip' -Force" >nul

echo [SUCCESS] Package created: ManhattanCrispr_v1.zip
echo Location: %cd%
pause
endlocal
