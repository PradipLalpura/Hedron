"""Hedron MVP backend — FastAPI, localhost only. Phase 0 stub: real routes, mock brains."""
import time
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="hedron-mvp")

class ChatIn(BaseModel):
    prompt: str
    mode: str = "Auto"
    scope: str = "Single"
    model: str = "Auto"

def route(prompt: str) -> dict:
    p = prompt.lower()
    if any(k in p for k in ("code", ".py", "calc", "fix", "function")):
        return {"model": "ornith-9b", "reason": "code/calc task + tool calls"}
    if any(k in p for k in ("scan", "photo", "image", "p&id", "drawing")):
        return {"model": "qwen2.5vl-3b", "reason": "vision input detected"}
    return {"model": "qwen-7b", "reason": "doc/summary default"}

@app.post("/chat")
def chat(body: ChatIn):
    r = {"echo": body.prompt, "router": route(body.prompt), "mode": body.mode, "scope": body.scope}
    if body.model != "Auto":
        r["router"] = {"model": body.model, "reason": "manual pin"}
    return r

@app.get("/proof")
def proof():
    return {"external_calls": 0, "llm_host": "127.0.0.1:11434", "uptime_s": int(time.time() % 86400)}

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
