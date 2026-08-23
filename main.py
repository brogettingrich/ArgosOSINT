"""
ArgosOSINT Android Entry Point
Starts the FastAPI/uvicorn server in a background thread,
then opens the UI in an Android WebView that fills the screen in portrait mode.
"""

import threading
import time
import os
import sys

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
        # Import app here after env vars are set
        uvicorn.run(
            'app.main:app',
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
            access_log=False
        )
    except Exception as e:
        print(f'[ArgosOSINT] Server error: {e}')

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()

# ── Launch Kivy App with embedded Android WebView ───────────────
from kivy.app import App                          # type: ignore
from kivy.uix.widget import Widget               # type: ignore
from kivy.clock import Clock                     # type: ignore

def launch_native_webview():
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
            # Lock screen orientation to portrait
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
        # Schedule webview launch on the main thread after Kivy window init
        Clock.schedule_once(lambda dt: launch_native_webview(), 0.2)

if __name__ == '__main__':
    ArgosApp().run()
