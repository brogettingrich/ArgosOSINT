"""
ArgosOSINT Android Entry Point
Starts the FastAPI/uvicorn server in a background thread,
then opens the UI in an Android WebView that fills the screen.
"""

import threading
import time
import os
import sys

# ── Android-specific path setup ──────────────────────────────
if sys.platform == 'android' or 'ANDROID_ROOT' in os.environ:
    from android.storage import app_storage_path  # type: ignore
    # Point the database to writable app storage
    os.environ['ARGOS_DATA_DIR'] = os.path.join(app_storage_path(), 'data')
    os.makedirs(os.environ['ARGOS_DATA_DIR'], exist_ok=True)

SERVER_PORT = 8500
SERVER_URL  = f'http://127.0.0.1:{SERVER_PORT}'

# ── Start FastAPI server in background thread ─────────────────
def _run_server():
    try:
        import uvicorn
        uvicorn.run(
            'app.main:app',
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
        )
    except Exception as e:
        print(f'[ArgosOSINT] Server error: {e}')

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()

# ── Wait for server to be ready (max 10 s) ───────────────────
import socket

def _wait_for_server(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(('127.0.0.1', SERVER_PORT), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(0.3)
    return False

_wait_for_server()

# ── Launch Kivy WebView ───────────────────────────────────────
from kivy.app import App                          # type: ignore
from kivy.uix.widget import Widget               # type: ignore
from kivy.clock import Clock                     # type: ignore
from kivy.core.window import Window              # type: ignore

Window.fullscreen = 'auto'

try:
    # Android native WebView via pyjnius
    from jnius import autoclass                  # type: ignore
    from android.runnable import run_on_ui_thread  # type: ignore

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    WebView        = autoclass('android.webkit.WebView')
    WebViewClient  = autoclass('android.webkit.WebViewClient')
    LinearLayout   = autoclass('android.widget.LinearLayout')
    ViewGroup      = autoclass('android.view.ViewGroup$LayoutParams')

    class ArgosApp(App):
        def build(self):
            self.widget = Widget()
            Clock.schedule_once(self._launch_webview, 0.1)
            return self.widget

        @run_on_ui_thread
        def _launch_webview(self, dt):
            activity = PythonActivity.mActivity
            wv = WebView(activity)
            wv.getSettings().setJavaScriptEnabled(True)
            wv.getSettings().setDomStorageEnabled(True)
            wv.getSettings().setAllowFileAccess(True)
            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(SERVER_URL)
            activity.setContentView(wv)

except Exception:
    # Fallback: Kivy Label + open system browser
    from kivy.uix.label import Label            # type: ignore
    import webbrowser

    class ArgosApp(App):
        def build(self):
            webbrowser.open(SERVER_URL)
            return Label(
                text=f'ArgosOSINT\nOpen {SERVER_URL}\nin your browser',
                halign='center',
            )

if __name__ == '__main__':
    ArgosApp().run()
