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
