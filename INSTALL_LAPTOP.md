# HEDRON — LAPTOP SETUP (copy-paste runbook, ~25 min first time, ~7 min daily)

## 0. You need (one time, with internet)
- Python 3.12+ (tick ADD TO PATH): https://www.python.org/downloads/
- Ollama: https://ollama.com/download
- Tesseract 5.4 (UB-Mannheim): https://github.com/UB-Mannheim/tesseract/wiki
- This repo: `git clone https://github.com/PradipLalpura/Hedron.git`
- Models — pick ONE:
  - (a) Pendrive: copy `%USERPROFILE%\.ollama\models` (~16GB) → venue same path.
  - (b) No pendrive: `ollama pull qwen2.5:7b` + `ollama pull qwen2.5:3b` +
    `ollama pull qwen2.5vl:3b` + `ollama pull nomic-embed-text` +
    `ollama pull hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M`
    (~30-60 min on venue Wi-Fi — start first, do step 1 meanwhile).

## 1. Venue laptop, first time
```
cd Hedron
pip install -r app\requirements.txt
ollama serve                        :: leave running (window 1)
ollama run qwen2.5:7b hi            :: pre-warm, Ctrl+C after first reply
python app\server.py                :: window 2, check http://127.0.0.1:8000/health
python app\desktop.py               :: window 3, Hedron opens
```
Copy `hedron\models` into `%USERPROFILE%\.ollama\models` if models missing
(`ollama list` must show qwen2.5:7b, ornith, qwen2.5vl:3b, qwen2.5:3b, nomic-embed-text).

## 2. Daily / demo run (7 min)
Double-click `start.bat` → wait for Hedron window → ask Q1 once (loads model) →
**unplug LAN** → demo: cited answer, `not in SOP`, vision toast, chat-to-file download.

## 3. If something breaks
- `ollama list` empty → models not copied (step 1).
- `[mock:...]` answers → `ollama serve` not running.
- UI says backend offline → `python app\server.py` not running.
- OOM on 6GB VRAM → close window, `set HEDRON_FORCE_CPU=1`, rerun (slow but alive).
- Vault has my old uploads → delete files in `app\sops\` except the 4 originals,
  restart server (re-ingest is automatic per upload; built-ins ship clean).

## 4. What lives where (nothing leaves the laptop)
- `app\` code · `app\sops\` vault docs · `vault_store\` chunks/audit/cache (local only)
- Models: Ollama store · 100% localhost (`127.0.0.1:8000`, `127.0.0.1:11434`)
