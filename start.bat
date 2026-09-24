@echo off
REM Hedron launcher — pendrive transports, SSD runs. Double-click only.
set DRIVE=%~d0
set HERE=%~dp0
set DEST=C:\hedron
REM dev mode: bat sits next to app\ -> use repo paths, skip copy entirely
if exist "%HERE%app\server.py" (
  set "DEST=%HERE%"
  set HEDRON_DEV=1
)
if not defined HEDRON_DEV (
  if not exist "%DEST%\models\blobs" (
    if exist "%DRIVE%\hedron\models" (
      echo [hedron] First run: copying 14GB models to SSD, 4-6 min...
      xcopy "%DRIVE%\hedron\models" "%DEST%\models\" /E /J /Y
      xcopy "%DRIVE%\hedron\app" "%DEST%\app\" /E /Y
    ) else (
      echo [hedron] No pendrive models found, using system Ollama store.
    )
  )
)
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_KEEP_ALIVE=5m
set OLLAMA_NUM_CTX=4096
set OLLAMA_FLASH_ATTENTION=1
set HEDRON_RESIDENT_CAP=2
REM venue fallback if OOM: set HEDRON_FORCE_CPU=1 (CPU-only, slow but alive)
if defined HEDRON_DEV (
  set OLLAMA_MODELS=
  start "hedron-ollama" /min ollama serve
  timeout /t 6 >nul
  ollama list
  start "hedron-server" /min python "%DEST%\app\server.py"
) else (
  set OLLAMA_MODELS=%DEST%\models
  start "hedron-ollama" /min "%DRIVE%\hedron\bin\ollama.exe" serve
  timeout /t 6 >nul
  "%DRIVE%\hedron\bin\ollama.exe" list
  start "hedron-server" /min python "%DEST%\app\server.py"
)
python "%DEST%\app\desktop.py"
