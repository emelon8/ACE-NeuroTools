@echo off
REM ============================================================
REM  ACE-Neuro — Lab Computer Run Script
REM
REM  HOW TO USE:
REM    1. Edit lab_config.json (in the same folder as this file):
REM         • paths.project_path      — path to this folder
REM         • paths.data_path         — base directory for raw data
REM         • paths.output_dir        — where results will be saved
REM         • paths.calcium_signal_dir — where .npz files are saved/read
REM         • run.analyses            — which analyses to run
REM         • run.line_nums           — subjects (null = all)
REM    2. Activate the conda environment:
REM         conda activate caiman
REM    3. Double-click this file — or run it from a terminal
REM
REM  %~dp0 resolves to the directory containing this .bat file,
REM  so lab_config.json is found automatically regardless of where
REM  you run this script from.
REM ============================================================

ace-neuro --config "%~dp0lab_config.json"

echo.
pause
