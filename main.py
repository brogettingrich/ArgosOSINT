"""
ArgosOSINT Android Entry Point
Starts the FastAPI/uvicorn server in a background thread,
polls until ready, then opens the UI in an Android WebView in portrait mode.
"""

import threading
import time
import os
import sys
import socket

# ── Clean up any host-compiled .so files that break ARM64 ─────
for p in list(sys.path):
    if p and os.path.isdir(p):
        try:
            for root, _, files in os.walk(p):
                if 'pydantic' in root or 'typing_extensions' in root:
                    for f in files:
                        if f.endswith('.so'):
                            try:
                                os.remove(os.path.join(root, f))
                            except Exception:
                                pass
        except Exception:
            pass

# ── Android-specific storage & path setup ─────────────────────
if sys.platform == 'android' or 'ANDROID_ROOT' in os.environ:
    try:
        from android.storage import app_storage_path  # type: ignore
        os.environ['ARGOS_DATA_DIR'] = os.path.join(app_storage_path(), 'data')
        os.makedirs(os.environ['ARGOS_DATA_DIR'], exist_ok=True)
    except Exception as e:
        print(f'[ArgosOSINT] Storage init warning: {e}')

SERVER_PORT = 8500
SERVER_URL = f'http://127.0.0.1:{SERVER_PORT}'

# ── Start FastAPI server in background daemon thread ───────────
def _run_server():
    try:
        import uvicorn
        from app.main import app as fastapi_app
        uvicorn.run(
            fastapi_app,
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
            access_log=False
        )
    except Exception as e:
        print(f'[ArgosOSINT] Server error: {e}')

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()

def is_server_ready(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(('127.0.0.1', SERVER_PORT), timeout=0.3)
            s.close()
            return True
        except OSError:
            time.sleep(0.2)
    return False

# ── Launch Kivy App with embedded Android WebView ───────────────
from kivy.app import App                          # type: ignore
from kivy.uix.widget import Widget               # type: ignore
from kivy.clock import Clock                     # type: ignore

def launch_native_webview():
    # Wait for the backend thread to open port 8500
    is_server_ready(timeout=10)

    try:
        from jnius import autoclass              # type: ignore
        from android.runnable import run_on_ui_thread  # type: ignore

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        ActivityInfo   = autoclass('android.content.pm.ActivityInfo')
        WebView        = autoclass('android.webkit.WebView')
        WebViewClient  = autoclass('android.webkit.WebViewClient')

        @run_on_ui_thread
        def _attach():
            activity = PythonActivity.mActivity
            activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT)

            wv = WebView(activity)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setAllowFileAccess(True)
            settings.setDatabaseEnabled(True)
            settings.setUseWideViewPort(True)
            settings.setLoadWithOverviewMode(True)

            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(SERVER_URL)
            activity.setContentView(wv)

        _attach()
    except Exception as e:
        print(f'[ArgosOSINT] Native WebView attach fallback: {e}')
        import webbrowser
        webbrowser.open(SERVER_URL)

class ArgosApp(App):
    def build(self):
        return Widget()

    def on_start(self):
        # Run webview launcher in a background thread to avoid blocking Kivy while waiting for port 8500
        threading.Thread(target=launch_native_webview, daemon=True).start()

if __name__ == '__main__':
    ArgosApp().run()
