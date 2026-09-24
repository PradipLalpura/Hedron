"""Hedron MVP Vault search: chunk-by-heading → nomic-embed → Chroma, FTS fallback."""
import os
import re
import sqlite3

try:
    import chromadb  # noqa: F401
    HAS_CHROMA = True
except Exception:
    HAS_CHROMA = False

DB = "vault_store/vault.db"
CHROMA_DIR = ".chroma"
COLL = "vault"
EMBED_MODEL = "nomic-embed-text"
MAX_CHARS = 800  # one chunk ≈ one heading section, fits 4K ctx even x3

_coll = None  # lazy Chroma collection


def init():
    os.makedirs("vault_store", exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(doc, page, text)")
    c.commit()
    c.close()


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 90:
        return False
    return (s.startswith("#")
            or (s.isupper() and len(s.split()) <= 8)
            or re.match(r"^(section|step|clause)\s+\d+", s, re.I) is not None)


def chunk_page(doc: str, page: int, text: str) -> list:
    """Split one page by headings into ≤MAX_CHARS chunks, keep (doc, page)."""
    chunks, cur = [], ""
    for line in (text or "").splitlines():
        if _is_heading(line) and cur.strip():
            chunks.append(cur.strip())
            cur = ""
        cur += line + "\n"
        if len(cur) >= MAX_CHARS:
            chunks.append(cur.strip())
            cur = ""
    if cur.strip():
        chunks.append(cur.strip())
    return [{"doc": doc, "page": page, "text": c} for c in chunks if len(c) >= 20]


def add_chunk(doc: str, page: int, text: str):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO chunks(doc, page, text) VALUES (?,?,?)", (doc, page, text))
    c.commit()
    c.close()


def _embed(texts: list) -> list | None:
    try:
        import ollama
        out = []
        for t in texts:
            r = ollama.embed(model=EMBED_MODEL, input=t[:2000])
            out.append(r["embeddings"][0])
        return out
    except Exception:
        return None  # ponytail: Ollama down → vector path off, FTS covers


def _coll():
    global _coll
    if _coll is not None:
        return _coll
    if not HAS_CHROMA:
        return None
    try:
        from chromadb import PersistentClient
        _coll = PersistentClient(path=CHROMA_DIR).get_or_create_collection(COLL)
        return _coll
    except Exception:
        return None


def ingest_chunks(chunks: list):
    """Store chunks in FTS always + Chroma vectors when possible."""
    if not chunks:
        return 0
    for ch in chunks:
        add_chunk(ch["doc"], ch["page"], ch["text"])
    col = _coll()
    vecs = _embed([c["text"] for c in chunks]) if col is not None else None
    if col is not None and vecs is not None:
        try:
            col.add(ids=["%s:%s:%d" % (c["doc"], c["page"], i) for i, c in enumerate(chunks)],
                    documents=[c["text"] for c in chunks],
                    metadatas=[{"doc": c["doc"], "page": c["page"]} for c in chunks],
                    embeddings=vecs)
        except Exception:
            pass
    return len(chunks)


def ingest_pdf(path: str) -> int:
    """PDF → per-page text → chunk-by-heading → store. Returns chunk count."""
    from pypdf import PdfReader
    doc = os.path.splitext(os.path.basename(path))[0]
    chunks = []
    for i, pg in enumerate(PdfReader(path).pages):
        chunks += chunk_page(doc, i + 1, pg.extract_text() or "")
    return ingest_chunks(chunks)


_STOP = {"what", "is", "the", "a", "an", "of", "to", "in", "on", "per", "for",
         "and", "or", "by", "as", "at", "it", "its", "this", "that", "do", "does"}


def _fts(query: str, k: int) -> list:
    toks = [t for t in re.findall(r"[A-Za-z0-9]+", query)
            if len(t) > 2 and t.lower() not in _STOP]  # MATCH-safe, question-tolerant
    if not toks:
        return []
    try:
        c = sqlite3.connect(DB)
        rows = c.execute("SELECT doc, page, text FROM chunks WHERE chunks MATCH ? "
                         "ORDER BY rank LIMIT ?", ("{text} : (" + " OR ".join(toks) + ")", k)).fetchall()
        c.close()
        return [{"doc": d, "page": p, "text": t} for d, p, t in rows]
    except Exception:
        return []


def _keys(s: str) -> set:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9]+", s)
            if len(t) > 3 and t.lower() not in _STOP}


def search(query: str, k: int = 3) -> list:
    """Vector first, FTS fallback. Always returns [{doc, page, text}]."""
    col = _coll()
    if col is not None:
        try:
            if col.count() > 0:
                vec = _embed([query])
                if vec is not None:
                    r = col.query(query_embeddings=vec, n_results=k)
                    if r["documents"][0]:
                        qk = _keys(query)
                        # ponytail: vectors always return *something*; keep only keyword-overlap
                        keep = [{"doc": m["doc"], "page": m["page"], "text": d}
                                for d, m in zip(r["documents"][0], r["metadatas"][0])
                                if qk and (qk & _keys(d))]
                        if keep:
                            return keep[:k]
        except Exception:
            pass
    return _fts(query, k)


def cite(hit: dict) -> str:
    return "[%s p.%s]" % (hit["doc"], hit["page"])


def context_for(query: str, k: int = 2) -> tuple:
    """(context_str | None, hits). None → caller must say 'not in SOP'."""
    hits = search(query, k=k)
    if not hits:
        return None, []
    ctx = "\n".join("%s %s" % (cite(h), h["text"][:600]) for h in hits)
    return ctx, hits
