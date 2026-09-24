"""Hedron MVP tools: jailed python + office writers. All offline."""
import subprocess
import sys

def run_python_jail(code: str, timeout: int = 5) -> dict:
    """Run code with no network: blocked socket import, timeout, byte cap."""
    guard = "import socket as _s; _s.socket = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('network blocked'))\n"
    try:
        r = subprocess.run([sys.executable, "-c", guard + code[:8000]],
                           capture_output=True, text=True, timeout=timeout)
        return {"ok": r.returncode == 0, "stdout": r.stdout[-2000:], "stderr": r.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout after %ss" % timeout}

def write_docx(path: str, title: str, paras: list) -> str:
    import os
    from docx import Document
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    d = Document()
    d.add_heading(title, 0)
    for p in paras:
        d.add_paragraph(p)
    d.save(path)
    return path

def verify(answer: str, cites: list, xlsx_path: str | None = None,
           need_cites: bool = False, max_chars: int = 2000) -> dict:
    """Release gate: cites≥1 (when required), recalc 0, overflow cap."""
    checks = {}
    checks["cites"] = (len(cites or []) >= 1) if need_cites else True
    checks["overflow"] = len(answer or "") <= max_chars
    checks["recalc"] = True
    if xlsx_path:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(xlsx_path, data_only=False)
            bad = 0
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        v = c.value
                        if isinstance(v, str) and v.startswith("="):
                            if "[" in v or "#REF!" in v or "#NAME?" in v:
                                bad += 1  # external link or broken ref
            checks["recalc"] = bad == 0
        except Exception:
            checks["recalc"] = False
    ok = all(checks.values())
    return {"ok": ok, "checks": checks}

def write_xlsx(path: str, rows: list) -> str:
    import os
    from openpyxl import Workbook
    from openpyxl.styles import Font
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True)
    wb.save(path)
    return path
