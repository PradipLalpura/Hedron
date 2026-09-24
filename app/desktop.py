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


if __name__ == "__main__":
    if not wait():
        here = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(here, "server.py")],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        wait()
    import webview
    webview.create_window("Hedron — Sovereign Workbench", URL, width=1280, height=860)
    webview.start()
