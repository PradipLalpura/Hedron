@echo off
REM Hedron MVP launcher — pendrive transports, SSD runs. Double-click only.
set DRIVE=%~d0
set DEST=C:\hedron
if not exist "%DEST%\models\blobs" (
  echo [hedron] First run: copying 14GB models to SSD, 4-6 min...
  xcopy "%DRIVE%\hedron\models" "%DEST%\models\" /E /J /Y
  xcopy "%DRIVE%\hedron\app" "%DEST%\app\" /E /Y
)
set OLLAMA_MODELS=%DEST%\models
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_KEEP_ALIVE=5m
set OLLAMA_NUM_CTX=4096
set OLLAMA_FLASH_ATTENTION=1
start /min "%DRIVE%\hedron\bin\ollama.exe" serve
timeout /t 6 >nul
"%DRIVE%\hedron\bin\ollama.exe" list
start /min python "%DEST%\app\server.py"
python -m streamlit run "%DEST%\app\app.py" --server.headless true
