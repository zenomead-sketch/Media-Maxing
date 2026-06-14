@echo off
setlocal
cd /d "%~dp0"
python -m scripts.local_beta_launcher %*
endlocal
