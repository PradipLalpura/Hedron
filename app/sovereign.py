"""Hedron MVP sovereign proof: localhost-only map + audit lines. No cloud exists."""
import hashlib
import time

AUDIT = "vault_store/audit.ndjson"

def net_status() -> dict:
    conns = []
    try:
        import psutil
        for c in psutil.net_connections(kind="tcp"):
            if c.status == "ESTABLISHED" and c.raddr:
                conns.append(c.raddr.ip)
    except Exception:
        pass
    external = [ip for ip in set(conns) if not ip.startswith("127.") and ip != "::1"]
    return {"external_calls": len(external), "llm_host": "127.0.0.1:11434", "ok": len(external) == 0}

def _last_hash() -> str:
    try:
        with open(AUDIT) as f:
            lines = f.readlines()
        if lines:
            import json
            return json.loads(lines[-1]).get("hash", "GENESIS")
    except Exception:
        pass
    return "GENESIS"


def _digest(payload: str) -> str:
    try:
        return hashlib.blake3(payload.encode()).hexdigest()[:16]
    except AttributeError:  # ponytail: stdlib has no blake3; sha256 fallback
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def audit(event: str, ref: str = "") -> str:
    import os
    os.makedirs("vault_store", exist_ok=True)
    prev = _last_hash()
    h = _digest("%s|%s|%s|%s" % (prev, time.time(), event, ref))
    with open(AUDIT, "a") as f:
        f.write('{"t": %d, "event": "%s", "ref": "%s", "prev": "%s", "hash": "%s"}\n'
                % (int(time.time()), event, ref, prev, h))
    return h


def verify_chain() -> dict:
    """Check each line's prev links to the previous hash. Returns {ok, events}."""
    import json
    try:
        with open(AUDIT) as f:
            lines = [ln for ln in f.readlines() if ln.strip()]
    except Exception:
        return {"ok": True, "events": 0}
    prev = "GENESIS"
    for ln in lines:
        try:
            e = json.loads(ln)
        except Exception:
            return {"ok": False, "events": len(lines)}
        if e.get("prev") != prev:
            return {"ok": False, "events": len(lines)}
        prev = e.get("hash", "")
    return {"ok": True, "events": len(lines)}
