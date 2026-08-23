"""
ArgosOSINT Android Entry Point
Starts FastAPI/uvicorn in a background daemon thread with disabled signal handlers,
polls until port 8500 is responsive, then embeds the UI in a fullscreen Android WebView.
"""

import threading
import time
import os
import sys
import socket

# ── 1. Clean up any host x86_64 .so binaries in pure-Python packages ──
for p in list(sys.path):
    if p and os.path.isdir(p):
        try:
            for root, _, files in os.walk(p):
                if any(pkg in root for pkg in ['pydantic', 'typing_extensions']):
                    for f in files:
                        if f.endswith('.so'):
                            try:
                                os.remove(os.path.join(root, f))
                            except Exception:
                                pass
        except Exception:
            pass

# ── 2. Android App Storage Path Setup ─────────────────────────
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

# ── 3. Start Uvicorn / FastAPI in background thread ────────────
def _run_server():
    try:
        import uvicorn
        from app.main import app as fastapi_app

        config = uvicorn.Config(
            app=fastapi_app,
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
            access_log=False
        )
        server = uvicorn.Server(config)
        # MUST disable signal handlers in non-main thread
        server.install_signal_handlers = lambda: None
        server.run()
    except Exception as e:
        import traceback
        err_msg = f'[ArgosOSINT] Server start error: {e}\n{traceback.format_exc()}'
        print(err_msg)
        try:
            with open('argos_boot_error.log', 'w') as f:
                f.write(err_msg)
        except Exception:
            pass

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()

def wait_for_server(timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(('127.0.0.1', SERVER_PORT), timeout=0.3)
            s.close()
            return True
        except OSError:
            time.sleep(0.2)
    return False

# ── 4. Embedded Android WebView ────────────────────────────────
from kivy.app import App                          # type: ignore
from kivy.uix.widget import Widget               # type: ignore

def launch_native_webview():
    # Ensure port 8500 is accepting connections before loading WebView
    wait_for_server(timeout=15)

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
            # Lock to portrait orientation
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
        print(f'[ArgosOSINT] WebView attach error: {e}')

class ArgosApp(App):
    def build(self):
        return Widget()

    def on_start(self):
        # Run WebView attachment in background thread to avoid blocking Kivy startup
        threading.Thread(target=launch_native_webview, daemon=True).start()

if __name__ == '__main__':
    ArgosApp().run()
