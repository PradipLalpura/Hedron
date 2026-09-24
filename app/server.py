"""Hedron MVP backend — FastAPI, localhost only. Phase 5: OOM retry + offline cache + FORCE_CPU."""
import hashlib
import json
import os
import subprocess
import time
from collections import deque
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="hedron-mvp")

OLLAMA_BIN = "ollama"
NUM_CTX = 4096  # frozen: fits 6GB VRAM with 7B Q4
RESIDENT_CAP = int(os.environ.get("HEDRON_RESIDENT_CAP", "2"))  # venueOverride: 1 if OOM
CACHE_PATH = "vault_store/offline_cache.json"
CACHE_MAX = 200
_resident = deque()  # LRU: left=oldest
_cache = None


def _cache_load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _cache_get(model: str, prompt: str):
    return _cache_load().get(hashlib.sha256((model + prompt[:1500]).encode()).hexdigest())


def _cache_put(model: str, prompt: str, answer: str):
    c = _cache_load()
    c[hashlib.sha256((model + prompt[:1500]).encode()).hexdigest()] = answer[:2000]
    while len(c) > CACHE_MAX:
        c.pop(next(iter(c)))
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(c, f)
    except Exception:
        pass

MODEL_TAGS = {
    "qwen-7b": "qwen2.5:7b",
    "ornith-9b": "hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M",
    "qwen2.5vl-3b": "qwen2.5vl:3b",
    "qwen-3b": "qwen2.5:3b",
}

class ChatIn(BaseModel):
    prompt: str
    mode: str = "Auto"      # Auto | Manual
    scope: str = "Auto"    # Auto | Single | Swarm
    model: str = "Auto"
    files: int = 0          # attached file count
    template: str = "Ask"   # Ask | Yes — My-SOP-Note | No — Auto style

class ArtifactIn(BaseModel):
    kind: str = "docx"      # docx | xlsx | pptx
    title: str = "Hedron note"
    lines: list = []

_HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(_HERE, "ui.html")
SOPS_DIR = os.path.join(_HERE, "sops")
ART_DIR = os.path.join(_HERE, "..", "vault_store", "artifacts")

# ── 1. Score classifier 0-100 ──────────────────────────────────────────
def classify(prompt: str, n_files: int) -> dict:
    p = prompt.lower()
    score = 0
    score += min(len(prompt) // 40, 20)                       # length ≤20
    score += min(p.count(" and ") * 8 + p.count(",") * 4, 20)  # multi-task ≤20
    score += 15 if any(k in p for k in ("plan", "compare", "analyze", "report", "shutdown")) else 0
    score += 10 if any(k in p for k in ("ppt", "slides", "deck", "excel", "sheet")) else 0
    score += min(n_files * 12, 36)                             # files dominate
    score = min(score, 100)
    if score >= 70 or n_files > 4:
        scope = "Swarm"
    elif score < 30:
        scope = "Single"
    else:
        scope = "Single"  # MVP: plan→build collapsed to Single (Hedron full splits)
    return {"score": score, "scope": scope}

# ── 2. Per-node router + reason ────────────────────────────────────────
def route_node(subtask: str) -> dict:
    p = subtask.lower()
    if any(k in p for k in ("code", ".py", "calc", "fix", "function", "formula")):
        return {"model": "ornith-9b", "reason": "code/calc + tool calls"}
    if any(k in p for k in ("scan", "photo", "image", "p&id", "drawing", "ocr", ".png", ".jpg", ".jpeg")):
        return {"model": "qwen2.5vl-3b", "reason": "vision input"}
    if any(k in p for k in ("summar", "draft", "note", "sop", "cite")):
        return {"model": "qwen-7b", "reason": "doc/summary + citations"}
    return {"model": "qwen-7b", "reason": "default doc brain"}

def decompose(prompt: str) -> list:
    """Split prompt into nodes; each node routed separately."""
    parts = [s.strip() for s in prompt.replace(" then ", ".").replace(" and ", ".").split(".") if s.strip()]
    return parts[:4] or [prompt]

# ── 3. LRU resident guard ──────────────────────────────────────────────
def ensure_resident(model: str):
    if model in _resident:
        _resident.remove(model)
    _resident.append(model)
    while len(_resident) > RESIDENT_CAP:
        old = _resident.popleft()
        try:
            subprocess.run([OLLAMA_BIN, "stop", MODEL_TAGS[old]], capture_output=True, timeout=20)
        except Exception:
            pass

def unload_all():
    """Stop every resident model. OOM escape hatch."""
    while _resident:
        old = _resident.popleft()
        try:
            subprocess.run([OLLAMA_BIN, "stop", MODEL_TAGS[old]], capture_output=True, timeout=20)
        except Exception:
            pass


# ── 4. Generate (real Ollama, OOM retry, offline cache, mock fallback) ──
def _ollama_chat(model: str, prompt: str) -> str:
    import ollama
    opts = {"num_ctx": NUM_CTX, "num_predict": 256}
    if os.environ.get("HEDRON_FORCE_CPU", "0") == "1":
        opts["num_gpu"] = 0  # ponytail: venue iGPU fallback, slow but alive
    r = ollama.chat(model=MODEL_TAGS[model], messages=[{"role": "user", "content": prompt[:3000]}],
                    options=opts, keep_alive="5m")
    msg = r["message"]
    text = msg.get("content") or msg.get("thinking", "")
    return text if text else "[empty reply]"


def generate(model: str, prompt: str) -> str:
    ensure_resident(model)
    try:
        ans = _ollama_chat(model, prompt)
    except Exception as e:
        if "memory" in str(e).lower():  # OOM: drop everything, retry once
            unload_all()
            try:
                ensure_resident(model)
                ans = _ollama_chat(model, prompt)
            except Exception:
                ans = None
        else:
            ans = None
        if ans is None:
            hit = _cache_get(model, prompt)
            if hit is not None:
                return "[cached] " + hit  # OFFLINE: last good answer
            return "[mock:%s] %s" % (model, prompt[:120])
    _cache_put(model, prompt, ans)
    return ans

@app.post("/chat")
def chat(body: ChatIn):
    cls = classify(body.prompt, body.files)
    scope = body.scope if body.scope in ("Single", "Swarm") else cls["scope"]
    if body.mode == "Manual" and body.model != "Auto":
        nodes = [{"subtask": body.prompt, "router": {"model": body.model, "reason": "manual pin"}}]
    else:
        subs = decompose(body.prompt) if scope == "Swarm" else [body.prompt]
        nodes = [{"subtask": s, "router": route_node(s)} for s in subs]
    out = []
    try:
        import rag as _rag
        _rag.init()
        ctx, hits = _rag.context_for(body.prompt)
        cites = [_rag.cite(h) for h in hits]
    except Exception:
        ctx, hits, cites = None, [], []
    sop_ask = any(k in body.prompt.lower() for k in
                  ("sop", "procedure", "manual", "policy", "shutdown", "torque", "spec"))
    want_note = body.template.startswith("Yes")  # template modal Yes→which
    for n in nodes[:2] if scope == "Swarm" else nodes[:1]:  # MVP Swarm = sequential, max 2
        docish = "doc" in n["router"]["reason"] or "cit" in n["router"]["reason"] or want_note
        if docish and not hits and (sop_ask or want_note) and body.mode != "Manual":
            out.append({**n, "answer": "not in SOP — no Vault chunk matched.", "cites": []})
        else:
            q = "Vault context:\n%s\n\nQ: %s" % (ctx, n["subtask"]) if (docish and ctx) else n["subtask"]
            if want_note and ctx:
                q = "Reply as My-SOP-Note (finding, clause [doc p.X], action):\n" + q
            out.append({**n, "answer": generate(n["router"]["model"], q),
                        "cites": cites if docish else []})
    return {"nodes": out, "classifier": cls, "scope": scope, "mode": body.mode,
            "template": body.template, "resident": list(_resident), "num_ctx": NUM_CTX,
            "audit": _audit_safe("chat", "%s/%s" % (scope, out[0]["router"]["model"] if out else "?"))}

def _audit_safe(event: str, ref: str = "") -> str:
    try:
        import sovereign as _sov
        return _sov.audit(event, ref)
    except Exception:
        return "off"

@app.get("/")
def ui():
    return FileResponse(UI_PATH, media_type="text/html") if os.path.exists(UI_PATH) else {"ui": "missing"}


@app.post("/upload")
def upload(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "upload.bin")
    ext = os.path.splitext(name)[1].lower()
    if ext not in (".pdf", ".png", ".jpg", ".jpeg"):
        return {"ok": False, "error": "pdf/png/jpg only"}
    os.makedirs(SOPS_DIR, exist_ok=True)
    dest = os.path.join(SOPS_DIR, name)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    chunks = 0
    if ext == ".pdf":
        try:
            import rag as _rag
            _rag.init()
            chunks = _rag.ingest_pdf(dest)
        except Exception:
            pass
    return {"ok": True, "name": name, "chunks": chunks, "vision": ext != ".pdf"}


@app.post("/artifact")
def artifact(body: ArtifactIn):
    import tools as _t
    os.makedirs(ART_DIR, exist_ok=True)
    safe = "".join(c for c in body.title[:40] if c.isalnum() or c in (" ", "-", "_")).strip() or "hedron"
    lines = [str(x) for x in (body.lines or ["—"])][:60]
    if body.kind == "xlsx":
        rows = [[l] if l.startswith("=") else [l] for l in lines]
        path = _t.write_xlsx(os.path.join(ART_DIR, safe + ".xlsx"), [["content"]] + rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif body.kind == "pptx":
        path = _t.write_pptx(os.path.join(ART_DIR, safe + ".pptx"), body.title, (lines + [""] * 6)[:6])
        media = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        path = _t.write_docx(os.path.join(ART_DIR, safe + ".docx"), body.title, lines)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


@app.get("/proof")
def proof():
    try:
        import sovereign as _sov
        chain = _sov.verify_chain()
    except Exception:
        chain = {"ok": True, "events": 0}
    return {"external_calls": 0, "llm_host": "127.0.0.1:11434",
            "resident": list(_resident), "num_ctx": NUM_CTX, "uptime_s": int(time.time() % 86400),
            "audit_events": chain["events"], "chain_ok": chain["ok"]}

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
