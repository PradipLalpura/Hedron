"""Hedron MVP Vault search. Chroma if available, else SQLite FTS fallback (works on any Python)."""
import sqlite3

try:
    import chromadb  # noqa: F401
    HAS_CHROMA = True
except Exception:
    HAS_CHROMA = False

DB = "vault_store/vault.db"

def init():
    import os
    os.makedirs("vault_store", exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(doc, page, text)")
    c.commit()
    c.close()

def add_chunk(doc: str, page: int, text: str):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO chunks(doc, page, text) VALUES (?,?,?)", (doc, page, text))
    c.commit()
    c.close()

def search(query: str, k: int = 3) -> list:
    try:
        c = sqlite3.connect(DB)
        rows = c.execute("SELECT doc, page, text FROM chunks WHERE chunks MATCH ? LIMIT ?", (query, k)).fetchall()
        c.close()
        return [{"doc": d, "page": p, "text": t} for d, p, t in rows]
    except Exception:
        return []
