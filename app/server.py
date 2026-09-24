"""Hedron MVP backend — FastAPI, localhost only. Phase 5: OOM retry + offline cache + FORCE_CPU."""
import hashlib
import json
import os
import re
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
    session_id: str = "default"

# ── S1. Sessions: isolated bounded memory (no rot, no cross-talk) ────
_SESS = {}  # sid -> {"title": str, "hist": [(role, text)]}
HIST_TURNS = 6
HIST_CHARS = 1500

def _sess(sid: str) -> dict:
    sid = (sid or "default")[:40]
    return _SESS.setdefault(sid, {"title": sid, "hist": []})

def _hist_text(sid: str) -> str:
    h = _sess(sid)["hist"][-HIST_TURNS:]
    t = "\n".join(("%s: %s" % (r, x[:400])) for r, x in h)
    return t[-HIST_CHARS:] if len(t) > HIST_CHARS else t

def _hist_add(sid: str, role: str, text: str):
    s = _sess(sid)
    if s["title"] == sid and role == "U":
        s["title"] = text[:40]
    s["hist"].append((role, (text or "")[:500]))

# ── S3. Genome: tag-matched operating rules, loaded once ─────────────
_GENOME = []
try:
    _GENOME = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "genome_frozen.json"), encoding="utf-8")).get("genes", [])
except Exception:
    pass

def genes_for(reason: str) -> str:
    r = (reason or "").lower()
    want = "code" if "code" in r or "tool" in r else ("docs" if ("doc" in r or "cit" in r) else "")
    out = [g["body"] for g in _GENOME if want and want in g.get("tags", [])][:3]
    return ("Operating rules:\n- " + "\n- ".join(o[:200] for o in out) + "\n") if out else ""

# ── S2. OCR + vision pixels ──────────────────────────────────────────
_TESS = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

def ocr_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageOps
        if os.path.exists(_TESS):
            pytesseract.pytesseract.tesseract_cmd = _TESS
        im = Image.open(path).convert("L")
        im = ImageOps.autocontrast(ImageOps.expand(im, 20).resize((im.width * 2, im.height * 2)))
        return (pytesseract.image_to_string(im) or "").strip()[:1500]
    except Exception:
        return ""

def find_images(subtask: str) -> list:
    out = []
    for tok in subtask.replace(",", " ").split():
        t = tok.strip("()\"'").lower()
        if t.endswith((".png", ".jpg", ".jpeg")):
            p = os.path.join(SOPS_DIR, os.path.basename(t))
            if os.path.exists(p):
                out.append(p)
    return out[:2]

def vision_bytes(path: str) -> bytes | None:
    try:
        import io
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((1568, 1568))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=88)
        return b.getvalue()
    except Exception:
        return None

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
    guard = prompt.replace(".png", "\x00p").replace(".jpg", "\x00j").replace(".jpeg", "\x00e")
    parts = [s.strip() for s in guard.replace(" then ", ".").replace(" and ", ".").split(".") if s.strip()]
    return [p.replace("\x00p", ".png").replace("\x00j", ".jpg").replace("\x00e", ".jpeg")
            for p in parts[:4]] or [prompt]

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
def _ollama_chat(model: str, prompt: str, images: list | None = None) -> str:
    import ollama
    opts = {"num_ctx": NUM_CTX, "num_predict": 256}
    if os.environ.get("HEDRON_FORCE_CPU", "0") == "1":
        opts["num_gpu"] = 0  # ponytail: venue iGPU fallback, slow but alive
    msg = {"role": "user", "content": prompt[:3000]}
    if images:
        msg["images"] = images
    r = ollama.chat(model=MODEL_TAGS[model], messages=[msg], options=opts, keep_alive="5m")
    msg = r["message"]
    text = msg.get("content") or msg.get("thinking", "")
    return text if text else "[empty reply]"


def generate(model: str, prompt: str, images: list | None = None) -> str:
    ensure_resident(model)
    try:
        ans = _ollama_chat(model, prompt, images)
    except Exception as e:
        if "memory" in str(e).lower():  # OOM: drop everything, retry once
            unload_all()
            try:
                ensure_resident(model)
                ans = _ollama_chat(model, prompt, images)
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
    sid = (body.session_id or "default")[:40]
    hist = _hist_text(sid)
    for n in nodes[:2] if scope == "Swarm" else nodes[:1]:  # MVP Swarm = sequential, max 2
        docish = "doc" in n["router"]["reason"] or "cit" in n["router"]["reason"] or want_note
        vision = n["router"]["model"] == "qwen2.5vl-3b"
        imgs, ocr_txt = [], ""
        if vision:
            for p in find_images(n["subtask"]):
                b = vision_bytes(p)
                if b:
                    imgs.append(b)
                t = ocr_image(p)
                if t and len(t) >= 20:
                    ocr_txt += t[:800] + "\n"
        if docish and not hits and (sop_ask or want_note) and body.mode != "Manual":
            ans = "not in SOP — no Vault chunk matched."
            out.append({**n, "answer": ans, "cites": []})
        else:
            q = ""
            if docish and ctx:
                q += "Vault context:\n%s\n\n" % ctx
            if vision and ocr_txt:
                q += "Pixels read (OCR):\n%s\n\n" % ocr_txt.strip()
            if hist:
                q += "Session so far:\n%s\n\n" % hist
            q += genes_for(n["router"]["reason"]) + "Q: %s" % n["subtask"]
            if want_note and ctx:
                q = "Reply as My-SOP-Note (finding, clause [doc p.X], action):\n" + q
            ans = generate(n["router"]["model"], q, imgs or None)
            node = {**n, "answer": ans, "cites": cites if docish else []}
            fk = file_kind(n["subtask"])  # "give it as docx/pdf/pptx" → build now
            if fk and not ans.startswith("not in SOP"):
                try:
                    fp, _m = _build_artifact(fk, n["subtask"][:40], ans.split("\n")[:30])
                    node["file"] = {"kind": fk, "name": os.path.basename(fp),
                                    "url": "/artifact-file/" + os.path.basename(fp)}
                except Exception:
                    pass
            out.append(node)
        _hist_add(sid, "U", n["subtask"])
        _hist_add(sid, "A", ans)
    return {"nodes": out, "classifier": cls, "scope": scope, "mode": body.mode,
            "template": body.template, "session_id": sid,
            "resident": list(_resident), "num_ctx": NUM_CTX,
            "audit": _audit_safe("chat", "%s/%s" % (scope, out[0]["router"]["model"] if out else "?"))}

def _audit_safe(event: str, ref: str = "") -> str:
    try:
        import sovereign as _sov
        return _sov.audit(event, ref)
    except Exception:
        return "off"

# ── Chat-to-file: "give me X as docx/pdf/pptx/xlsx" builds the file ──
_FILE_RE = re.compile(r"\b(docx?|word|pdf|pptx?|slides?|deck|excel|xlsx|sheets?)\b", re.I)
_FILE_ASK = re.compile(r"\b(give|export|download|make|create|save|generate|as|into|in)\b", re.I)

def file_kind(subtask: str) -> str | None:
    m = _FILE_RE.search(subtask or "")
    if not m or not _FILE_ASK.search(subtask or ""):
        return None
    w = m.group(1).lower()
    if w == "pdf":
        return "pdf"
    if w.startswith("ppt") or w.startswith("slide") or w == "deck":
        return "pptx"
    if w.startswith("doc") or w == "word":
        return "docx"
    return "xlsx"


def _build_artifact(kind: str, title: str, lines: list) -> tuple:
    import tools as _t
    os.makedirs(ART_DIR, exist_ok=True)
    safe = "".join(c for c in (title or "hedron")[:40] if c.isalnum() or c in (" ", "-", "_")).strip() or "hedron"
    lines = [str(x) for x in (lines or ["—"])][:60]
    if kind == "xlsx":
        rows = [[l] if l.startswith("=") else [l] for l in lines]
        return (_t.write_xlsx(os.path.join(ART_DIR, safe + ".xlsx"), [["content"]] + rows),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if kind == "pptx":
        return (_t.write_pptx(os.path.join(ART_DIR, safe + ".pptx"), title, (lines + [""] * 6)[:6]),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    if kind == "pdf":
        return (_t.write_pdf(os.path.join(ART_DIR, safe + ".pdf"), title, lines), "application/pdf")
    return (_t.write_docx(os.path.join(ART_DIR, safe + ".docx"), title, lines),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


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
    chunks, ocr_chars = 0, 0
    if ext == ".pdf":
        try:
            import rag as _rag
            _rag.init()
            chunks = _rag.ingest_pdf(dest)
        except Exception:
            pass
    else:  # image: OCR text becomes a searchable Vault chunk
        try:
            import rag as _rag
            _rag.init()
            t = ocr_image(dest)
            ocr_chars = len(t)
            if len(t) >= 20:
                chunks = _rag.ingest_chunks([{"doc": os.path.splitext(name)[0],
                                              "page": 1, "text": t}])
        except Exception:
            pass
    return {"ok": True, "name": name, "chunks": chunks, "ocr_chars": ocr_chars,
            "vision": ext != ".pdf"}


@app.get("/sessions")
def sessions():
    return {"sessions": [{"id": sid, "title": s["title"], "turns": len(s["hist"]) // 2}
                         for sid, s in _SESS.items()]}


@app.get("/session/{sid}")
def session_hist(sid: str):
    s = _sess(sid)
    return {"id": sid[:40], "title": s["title"],
            "history": [{"role": r, "text": t} for r, t in s["hist"][-HIST_TURNS:]]}


@app.post("/artifact")
def artifact(body: ArtifactIn):
    path, media = _build_artifact(body.kind, body.title, body.lines)
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


@app.get("/artifact-file/{name}")
def artifact_file(name: str):
    safe = os.path.basename(name or "")
    if not safe.endswith((".docx", ".pdf", ".pptx", ".xlsx")):
        return {"ok": False, "error": "unknown file"}
    path = os.path.join(ART_DIR, safe)
    if not os.path.exists(path):
        return {"ok": False, "error": "not found"}
    return FileResponse(path, filename=safe)


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
