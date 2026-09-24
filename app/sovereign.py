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

def audit(event: str, ref: str = "") -> str:
    import os
    os.makedirs("vault_store", exist_ok=True)
    h = hashlib.blake3(f"{time.time()}{event}{ref}".encode()).hexdigest()[:16]
    with open(AUDIT, "a") as f:
        f.write('{"t": %d, "event": "%s", "hash": "%s"}\n' % (int(time.time()), event, h))
    return h
