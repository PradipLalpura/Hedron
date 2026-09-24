"""Hedron desktop shell — native window over the local UI. No cloud, no browser."""
import os
import subprocess
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8000/"


def wait(url=URL, tries=24):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url + "health", timeout=3)
            return True
        except Exception:
            time.sleep(2.5)
    return False


class Api:
    """JS bridge: native save dialog. Blob-anchor downloads die silently in webviews."""

    def save_file(self, name, b64):
        import base64
        try:
            import webview
            picked = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG,
                                                           save_filename=name or "hedron.bin")
            if not picked:
                return ""
            path = picked[0] if isinstance(picked, list) else picked
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            return path
        except Exception as e:
            return "error: " + str(e)[:120]


if __name__ == "__main__":
    if not wait():
        here = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(here, "server.py")],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        wait()
    import webview
    webview.create_window("Hedron — Sovereign Workbench", URL, width=1280, height=860,
                          js_api=Api())
    webview.start()
