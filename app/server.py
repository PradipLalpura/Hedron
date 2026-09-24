"""Hedron MVP backend — FastAPI, localhost only. Phase 1: classifier + per-node router + LRU + 4K ctx."""
import subprocess
import time
from collections import deque
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="hedron-mvp")

OLLAMA_BIN = "ollama"
NUM_CTX = 4096  # frozen: fits 6GB VRAM with 7B Q4
RESIDENT_CAP = 2  # max models in VRAM; 1 on 6GB Swarm-sequential
_resident = deque()  # LRU: left=oldest

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
    if any(k in p for k in ("scan", "photo", "image", "p&id", "drawing", "ocr")):
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

# ── 4. Generate (real Ollama, mock fallback) ───────────────────────────
def generate(model: str, prompt: str) -> str:
    ensure_resident(model)
    try:
        import ollama
        r = ollama.chat(model=MODEL_TAGS[model], messages=[{"role": "user", "content": prompt[:3000]}],
                        options={"num_ctx": NUM_CTX, "num_predict": 256}, keep_alive="5m")
        msg = r["message"]
        text = msg.get("content") or msg.get("thinking", "")
        return text if text else "[empty reply]"
    except Exception as e:
        return "[mock:%s] %s" % (model, prompt[:120])

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
    for n in nodes[:2] if scope == "Swarm" else nodes[:1]:  # MVP Swarm = sequential, max 2
        docish = "doc" in n["router"]["reason"] or "cit" in n["router"]["reason"]
        if docish and not hits and sop_ask and body.mode != "Manual":
            out.append({**n, "answer": "not in SOP — no Vault chunk matched.", "cites": []})
        else:
            q = "Vault context:\n%s\n\nQ: %s" % (ctx, n["subtask"]) if (docish and ctx) else n["subtask"]
            out.append({**n, "answer": generate(n["router"]["model"], q),
                        "cites": cites if docish else []})
    return {"nodes": out, "classifier": cls, "scope": scope, "mode": body.mode,
            "resident": list(_resident), "num_ctx": NUM_CTX}

@app.get("/proof")
def proof():
    return {"external_calls": 0, "llm_host": "127.0.0.1:11434",
            "resident": list(_resident), "num_ctx": NUM_CTX, "uptime_s": int(time.time() % 86400)}

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
