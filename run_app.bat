@echo off
rem ============================================================
rem  Lanceur MK_A.A 2026 - Debits d'air admis en conduites AEP
rem  Utilise Python 3.14 (deja present dans le PATH).
rem ============================================================
cd /d "%~dp0"
py -3.14 main.py
if errorlevel 1 (
  echo.
  echo [ERREUR] Impossible de lancer avec Python 3.14.
  echo Veuillez installer Python 3.14 ou verifier votre PATH.
  pause
)
