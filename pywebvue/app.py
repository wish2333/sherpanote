"""App class - creates pywebview window and manages the bridge lifecycle."""

from __future__ import annotations

import http.server
import platform
import socket
import sys
import threading
from pathlib import Path

import webview

from pywebvue.bridge import Bridge


class _FrontendHTTPServer(http.server.HTTPServer):
    """Lightweight HTTP server for serving the frontend dist directory.

    Used only on macOS where WebKit (WKWebView) requires a secure context
    (https or localhost) for navigator.mediaDevices to be available.
    """

    allow_reuse_address = True


def _start_http_server(directory: Path, port: int = 0) -> tuple[int, _FrontendHTTPServer]:
    """Start a background HTTP server serving *directory*.

    Returns (actual_port, server). The server runs in a daemon thread and
    stops automatically when the process exits.
    """
    directory = Path(directory).resolve()

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass  # Suppress request logs

    server = _FrontendHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server.server_address[1], server


def _resolve_frontend_path(frontend_dir: str) -> Path:
    """Resolve the absolute path to the frontend directory.

    Handles three environments:

    * **PyInstaller --onefile**: resources live in ``sys._MEIPASS``.
    * **PyInstaller --onedir**: resources live beside the executable.
    * **Development**: uses the given ``frontend_dir`` relative to CWD.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # --onefile bundle
        return Path(sys._MEIPASS) / frontend_dir
    if getattr(sys, "frozen", False):
        # --onedir bundle
        return Path(sys.executable).parent / frontend_dir
    return Path(frontend_dir)


class App:
    """Create a pywebview window wired to a :class:`Bridge` instance.

    Usage::

        from pywebvue import App, Bridge, expose

        class MyApi(Bridge):
            @expose
            def greet(self, name: str) -> dict:
                return {"success": True, "data": f"Hello, {name}!"}

        App(MyApi(), title="Demo", width=800, height=600,
            frontend_dir=".").run(dev=True)
    """

    def __init__(
        self,
        bridge: Bridge,
        *,
        title: str = "App",
        width: int = 1200,
        height: int = 960,
        min_size: tuple[int, int] = (600, 400),
        frontend_dir: str = "frontend_dist",
        dev_url: str = "http://localhost:5173",
    ) -> None:
        self._bridge = bridge
        self._title = title
        self._width = width
        self._height = height
        self._min_size = min_size
        self._frontend_dir = frontend_dir
        self._dev_url = dev_url

    @property
    def dev(self) -> bool:
        """True when running inside PyInstaller bundle."""
        return not getattr(sys, "frozen", False)

    def emit(self, event: str, data=None) -> None:
        """Push an event to the frontend. See :meth:`Bridge._emit`."""
        self._bridge._emit(event, data)

    def run(self, dev: bool | None = None, *, debug: bool | None = None) -> None:
        """Create the window and start the event loop.

        Args:
            dev:   URL source. ``True`` = Vite dev server, ``False`` = disk,
                   ``None`` = auto-detect (dev when not frozen).
            debug: Open developer tools. ``True`` / ``False`` / ``None``
                   (default: True when not frozen).
        """
        is_dev = dev if dev is not None else self.dev
        show_debug = debug if debug is not None else self.dev

        if is_dev:
            url = self._dev_url
        else:
            base = _resolve_frontend_path(self._frontend_dir)
            # macOS WebKit requires a secure context (https/localhost) for
            # navigator.mediaDevices. Serve via localhost HTTP instead of file://.
            if sys.platform == "darwin":
                port, _ = _start_http_server(base)
                url = f"http://127.0.0.1:{port}/index.html"
            else:
                url = str(base / "index.html")

        window = webview.create_window(
            self._title,
            url,
            width=self._width,
            height=self._height,
            min_size=self._min_size,
            js_api=self._bridge,
        )

        self._bridge._window = window

        # Set up native file drag-and-drop.
        self._setup_drag_drop(window)

        webview.start(debug=show_debug)

    def _setup_drag_drop(self, window) -> None:
        """Register a drop handler and start the event flush timer."""

        def on_loaded() -> None:
            from webview.dom import DOMEventHandler

            doc = window.dom.document
            handler = DOMEventHandler(self._bridge._on_drop, prevent_default=True)
            doc.on("drop", handler)

            # Start a periodic timer that flushes queued events from
            # background threads to the frontend via evaluate_js.
            # This keeps evaluate_js on the main thread (required by
            # WebView2/COM on Windows).
            window.evaluate_js(
                "setInterval(function() {"
                "  try { window.pywebview.api.flush_events(); }"
                "  catch(e) { console.error('flush_events error:', e); }"
                "}, 50);"
            )

            # Also start task executor that runs functions on the main thread
            # (required for thread-unsafe C++ extensions like ONNX Runtime).
            # Run less frequently (100ms) to reduce log spam.
            window.evaluate_js(
                "setInterval(function() {"
                "  try { window.pywebview.api.execute_task(); }"
                "  catch(e) { console.error('execute_task exception:', e); }"
                "}, 100);"
            )
            print("DEBUG: Task executor timers started")  # This goes to server console

        window.events.loaded += on_loaded
