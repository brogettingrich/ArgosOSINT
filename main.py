"""
ArgosOSINT Android Entry Point
Starts pure Starlette/uvicorn backend in a background daemon thread,
and attaches a fullscreen Android WebView to PythonActivity on startup.
"""

import threading
import time
import os
import sys
import socket

# ── 1. Android App Storage Path Setup ─────────────────────────
if sys.platform == 'android' or 'ANDROID_ROOT' in os.environ:
    try:
        from android.storage import app_storage_path  # type: ignore
        app_data = os.path.join(app_storage_path(), 'data')
        os.environ['ARGOS_DATA_DIR'] = app_data
        os.makedirs(app_data, exist_ok=True)
    except Exception as e:
        print(f'[ArgosOSINT] App storage init: {e}')

SERVER_PORT = 8500
SERVER_URL = f'http://127.0.0.1:{SERVER_PORT}'

# ── 2. Start Uvicorn / Starlette in background thread ───────────
def _run_server():
    try:
        import uvicorn
        from app.main import app as starlette_app

        config = uvicorn.Config(
            app=starlette_app,
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
            access_log=False
        )
        server = uvicorn.Server(config)
        # Disable signal handlers in background thread
        server.install_signal_handlers = lambda: None
        server.run()
    except Exception as e:
        import traceback
        err_msg = f'[ArgosOSINT] Server start error: {e}\n{traceback.format_exc()}'
        print(err_msg)

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()

# ── 3. Embedded Android WebView ────────────────────────────────
from kivy.app import App                          # type: ignore
from kivy.uix.widget import Widget               # type: ignore
from kivy.clock import Clock                     # type: ignore

def attach_webview():
    try:
        from jnius import autoclass              # type: ignore

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity

        # Lock orientation to portrait (1 = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT)
        try:
            activity.setRequestedOrientation(1)
        except Exception:
            pass

        WebView = autoclass('android.webkit.WebView')
        WebViewClient = autoclass('android.webkit.WebViewClient')

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
        print('[ArgosOSINT] Native WebView successfully attached to Activity!')
    except Exception as e:
        import traceback
        print(f'[ArgosOSINT] WebView attach error: {e}\n{traceback.format_exc()}')

class ArgosApp(App):
    def build(self):
        return Widget()

    def on_start(self):
        # Run attach_webview on main UI thread via Kivy clock without android.runnable proxy
        Clock.schedule_once(lambda dt: attach_webview(), 0.5)

if __name__ == '__main__':
    ArgosApp().run()
