"""
ArgosOSINT Android Entry Point
Starts pure Starlette/uvicorn backend in a background daemon thread,
and attaches a fullscreen Android WebView to PythonActivity on startup.

External-link routing (no PyJNIUS proxy tricks):
  • JS clicks "OPEN PROFILE" → fetch('/api/open-external?url=...')
  • Starlette queues the URL in app.android_bridge.pending_external_urls
  • _url_dispatcher() thread pops it → fires Android ACTION_VIEW Intent
  • Instagram/Chrome/etc opens in a NEW task; WebView + scan untouched

Back button:
  • Navigates WebView history; exits only when no history remains.

WakeLock:
  • PARTIAL_WAKE_LOCK keeps the CPU alive during long SSE scan streams.
"""

import threading
import time
import os
import sys
import socket
import queue

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
SERVER_URL  = f'http://127.0.0.1:{SERVER_PORT}'

# ── 2. Start Uvicorn / Starlette in background thread ───────────
_server_state = {'error': None}

def _run_server():
    try:
        import uvicorn
        from app.main import app as starlette_app

        config = uvicorn.Config(
            app=starlette_app,
            host='127.0.0.1',
            port=SERVER_PORT,
            log_level='warning',
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server.run()
    except Exception as e:
        import traceback
        print(f'[ArgosOSINT] Server start error: {e}\n{traceback.format_exc()}')
        _server_state['error'] = str(e)

server_thread = threading.Thread(target=_run_server, daemon=True)
server_thread.start()


def _wait_for_server(timeout=10.0, interval=0.2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_state['error']:
            return False
        try:
            with socket.create_connection(('127.0.0.1', SERVER_PORT), timeout=0.3):
                return True
        except OSError:
            time.sleep(interval)
    return False


# ── 3. External URL dispatcher ───────────────────────────────────
# Reads URLs queued by /api/open-external (via JS click intercept) and
# fires Android ACTION_VIEW Intents.  Uses zero PyJNIUS proxy tricks —
# startActivity() is a plain method call, safe from any thread when
# FLAG_ACTIVITY_NEW_TASK is set.
def _url_dispatcher():
    try:
        from jnius import autoclass  # type: ignore
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent         = autoclass('android.content.Intent')
        Uri            = autoclass('android.net.Uri')

        from app.android_bridge import pending_external_urls

        print('[ArgosOSINT] URL dispatcher ready')
        while True:
            try:
                url = pending_external_urls.get(timeout=1.0)
                try:
                    activity = PythonActivity.mActivity
                    intent   = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    activity.startActivity(intent)
                    print(f'[ArgosOSINT] Opened externally: {url}')
                except Exception as ex:
                    print(f'[ArgosOSINT] Intent dispatch error: {ex}')
            except queue.Empty:
                continue
    except Exception as e:
        print(f'[ArgosOSINT] URL dispatcher init error: {e}')

threading.Thread(target=_url_dispatcher, daemon=True).start()


# ── 4. Kivy shell + status UI ────────────────────────────────────
from kivy.app             import App           # type: ignore
from kivy.clock           import Clock         # type: ignore
from kivy.uix.floatlayout import FloatLayout  # type: ignore
from kivy.uix.label       import Label         # type: ignore
from kivy.graphics        import Color, Rectangle  # type: ignore


class StatusScreen(FloatLayout):
    """Branded splash shown while the backend/WebView come up."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.07, 0.07, 0.09, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self.title_label = Label(
            text='ArgosOSINT',
            font_size='26sp', bold=True,
            color=(0.85, 0.85, 0.92, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.56},
            size_hint=(0.9, None), height=40,
        )
        self.status_label = Label(
            text='Starting up...',
            font_size='15sp',
            color=(0.55, 0.55, 0.63, 1),
            halign='center', valign='top',
            pos_hint={'center_x': 0.5, 'center_y': 0.46},
            size_hint=(0.85, None), height=140,
        )
        self.status_label.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.add_widget(self.title_label)
        self.add_widget(self.status_label)

    def _sync_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def set_status(self, text, is_error=False):
        self.status_label.text  = text
        self.status_label.color = (0.85, 0.4, 0.4, 1) if is_error else (0.55, 0.55, 0.63, 1)


# ── Global WebView reference (needed for back-button navigation) ──
_webview = None


def attach_webview(on_done):
    """Build the native Android WebView and attach it to the Activity.
    Must run on Android's actual UI/Looper thread (guaranteed by the
    run_on_ui_thread decorator in ArgosApp._begin_attach).

    External links are NOT handled here — they are intercepted by the
    JavaScript click handler in app.js and routed through the
    /api/open-external endpoint → _url_dispatcher() thread → Intent.
    This completely avoids any need to subclass WebViewClient (which
    PythonJavaClass cannot do because WebViewClient is a class, not an
    interface, and Java's Proxy only supports interfaces).
    """
    global _webview
    try:
        from jnius import autoclass  # type: ignore

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity       = PythonActivity.mActivity

        # Lock to portrait
        try:
            activity.setRequestedOrientation(1)
        except Exception:
            pass

        WebView       = autoclass('android.webkit.WebView')
        WebViewClient = autoclass('android.webkit.WebViewClient')

        wv = WebView(activity)
        settings = wv.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setDomStorageEnabled(True)
        settings.setAllowFileAccess(True)
        settings.setDatabaseEnabled(True)
        settings.setUseWideViewPort(True)
        settings.setLoadWithOverviewMode(True)

        # Plain WebViewClient — keeps all navigation inside our WebView.
        # External links are handled by JS + _url_dispatcher, not here.
        wv.setWebViewClient(WebViewClient())
        wv.loadUrl(SERVER_URL)
        activity.setContentView(wv)

        _webview = wv  # store for back-button handler

        # ── WakeLock: keep CPU awake during long SSE scan streams ──
        try:
            Context      = autoclass('android.content.Context')
            pm           = activity.getSystemService(Context.POWER_SERVICE)
            wl           = pm.newWakeLock(1, 'ArgosOSINT:ScanWakeLock')
            wl.acquire()
            print('[ArgosOSINT] WakeLock acquired')
        except Exception as wl_err:
            print(f'[ArgosOSINT] WakeLock unavailable: {wl_err}')

        print('[ArgosOSINT] Native WebView successfully attached to Activity!')
        Clock.schedule_once(lambda dt: on_done(None), 0)

    except Exception as e:
        import traceback
        print(f'[ArgosOSINT] WebView attach error: {e}\n{traceback.format_exc()}')
        Clock.schedule_once(lambda dt, err=str(e): on_done(err), 0)


# ── 5. Kivy App class ────────────────────────────────────────────
class ArgosApp(App):
    def build(self):
        self.status_screen = StatusScreen()
        return self.status_screen

    # ── Back button: navigate WebView history instead of exiting ──
    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        KEYCODE_BACK = 27   # Kivy maps Android back → ESC (27)
        if key == KEYCODE_BACK and _webview is not None:
            try:
                if _webview.canGoBack():
                    _webview.goBack()
                    return True    # consumed — don't exit
            except Exception:
                pass
        return False           # let Kivy / Android handle it (exits app)

    def _on_attach_result(self, error):
        if error is None:
            return
        self.status_screen.set_status(
            f'Could not load the app UI:\n{error}\n\n'
            f'Backend is still running at\n{SERVER_URL}',
            is_error=True,
        )

    def _begin_attach(self, server_ok):
        if not server_ok:
            self._on_attach_result(
                _server_state['error'] or 'Backend server did not start in time.'
            )
            return

        self.status_screen.set_status('Loading interface...')
        try:
            from android.runnable import run_on_ui_thread  # type: ignore

            @run_on_ui_thread
            def _do_attach():
                attach_webview(self._on_attach_result)

            _do_attach()
        except Exception as e:
            import traceback
            print(f'[ArgosOSINT] run_on_ui_thread unavailable: {e}\n{traceback.format_exc()}')
            self._on_attach_result(str(e))

    def on_start(self):
        from kivy.core.window import Window  # type: ignore
        Window.bind(on_keyboard=self.on_keyboard)

        self.status_screen.set_status('Starting backend server...')

        def _wait_then_attach():
            ok = _wait_for_server(timeout=10.0)
            Clock.schedule_once(lambda dt: self._begin_attach(ok), 0)

        threading.Thread(target=_wait_then_attach, daemon=True).start()


if __name__ == '__main__':
    ArgosApp().run()
