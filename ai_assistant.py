# -*- coding: utf-8 -*-
"""
SynapsePro – AI Assistant Sidebar (v2)
======================================
Local HTML chat UI. No remote website dependency.
Providers: OpenAI · Google Gemini · OpenRouter · Anthropic Claude · Ollama (local)

Bridge: JS → Python via console.log("PYCALL:action:json")
        Python → JS via page.runJavaScript(...)
"""

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

# ── Local imports ─────────────────────────────────────────────────────────────
try:
    from . import constants
except ImportError:
    class MockConstants:
        qt_version = 0
        try:
            from PyQt6.QtCore import QT_VERSION_STR; qt_version = 6
        except ImportError:
            try:
                from PyQt5.QtCore import QT_VERSION_STR; qt_version = 5
            except ImportError:
                pass
        ADDON_NAME_LAUNCHER = "Launcher_Sidebar"
        addon_path = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
    constants = MockConstants()  # type: ignore[assignment]

try:
    from .locales import _
except ImportError:
    def _(t):  # type: ignore[misc]
        return t

# ── PyQt imports ──────────────────────────────────────────────────────────────
_qt_ok = False
try:
    if constants.qt_version == 6:
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QDockWidget, QSizePolicy,
            QDialog, QDialogButtonBox, QLabel, QPushButton,
            QHBoxLayout, QProgressBar, QListWidget, QListWidgetItem,
            QStackedWidget, QMessageBox,
        )
        from PyQt6.QtCore import QUrl, QTimer, Qt, QObject, pyqtSignal
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import (
            QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
        )
        _qt_ok = True
        print("AI Assistant: PyQt6 loaded OK")
    elif constants.qt_version == 5:
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QDockWidget, QSizePolicy,
            QDialog, QDialogButtonBox, QLabel, QPushButton,
            QHBoxLayout, QProgressBar, QListWidget, QListWidgetItem,
            QStackedWidget, QMessageBox,
        )
        from PyQt5.QtCore import QUrl, QTimer, Qt, QObject, pyqtSignal
        from PyQt5.QtGui import QIcon
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtWebEngineCore import (
            QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
        )
        _qt_ok = True
        print("AI Assistant: PyQt5 loaded OK")
    else:
        raise ImportError("Qt version unknown")
except ImportError as _e:
    print(f"AI Assistant: Qt import FAILED – {_e}")
    QWidget = QVBoxLayout = QDockWidget = QSizePolicy = object  # type: ignore[misc,assignment]
    QDialog = QDialogButtonBox = QLabel = QPushButton = object  # type: ignore[misc,assignment]
    QHBoxLayout = QProgressBar = QListWidget = QListWidgetItem = object  # type: ignore[misc,assignment]
    QStackedWidget = QMessageBox = QObject = object  # type: ignore[misc,assignment]
    QUrl = QTimer = Qt = QIcon = pyqtSignal = object  # type: ignore[misc,assignment]
    QWebEngineView = QWebEngineProfile = QWebEnginePage = QWebEngineSettings = object  # type: ignore[misc,assignment]

# ── Anki imports ──────────────────────────────────────────────────────────────
_anki_ok = False
try:
    from aqt import mw, gui_hooks
    from aqt.reviewer import Reviewer
    from aqt.utils import tooltip, qconnect, showWarning
    _anki_ok = True
    print("AI Assistant: Anki imports OK")
except ImportError as _e:
    print(f"AI Assistant: Anki import FAILED – {_e}")
    mw = gui_hooks = None  # type: ignore[assignment]
    Reviewer = object  # type: ignore[assignment,misc]
    def tooltip(msg, *a, **k): print(f"[tooltip] {msg}")
    def qconnect(sig, slot): pass
    def showWarning(msg, *a, **k): print(f"[warning] {msg}")

# ── Night mode ────────────────────────────────────────────────────────────────
def _detect_night_mode() -> bool:
    """Detect Anki's current night mode setting (safe to call any time)."""
    try:
        if mw and hasattr(mw, 'pm') and mw.pm:
            return bool(mw.pm.night_mode())
    except Exception:
        pass
    return False


def _get_theme_accent(is_dark: bool) -> str:
    """Return the active SynapsePro theme's accent colour (blue_accent token).
    Falls back to a sensible default if theme module is unavailable."""
    try:
        from .theme import palette  # type: ignore[import]
        color = palette(is_dark).get("blue_accent", "")
        if color and color.startswith("#"):
            return color
    except Exception:
        pass
    return "#3b82f6" if not is_dark else "#6366f1"

# ── Module constants ──────────────────────────────────────────────────────────
DOCK_NAME     = "AIAssistantSidebarDock_Integrated_v1"
HTML_FILENAME = "chat_ui.html"
OLLAMA_EP_DEFAULT = "http://localhost:11434"

PREFERRED_FRONT = ["Vorderseite","Front","Question","Text","Frage","Prompt","Front Side"]
PREFERRED_BACK  = ["Rückseite","Back","Answer","Antwort","Back Side"]

LANG_SUFFIX: Dict[str, str] = {
    "English":              "in English",
    "German":               "in German",
    "French":               "in French",
    "Spanish":              "in Spanish",
    "Italian":              "in Italian",
    "Portuguese":           "in Portuguese",
    "Dutch":                "in Dutch",
    "Russian":              "in Russian",
    "Japanese":             "in Japanese",
    "Chinese (Simplified)": "in Simplified Chinese",
    "Korean":               "in Korean",
}
DEFAULT_OWN_PROMPT = "Explain the key aspects of {content} in simple terms."

# ── Config keys ───────────────────────────────────────────────────────────────
_PFX          = f"addon_{constants.ADDON_NAME_LAUNCHER}_AIv2_"
CK_PROVIDER   = _PFX + "provider"
CK_MODEL      = _PFX + "model"
CK_KEY_OPENAI = _PFX + "key_openai"
CK_KEY_GEMINI = _PFX + "key_gemini"
CK_KEY_OR     = _PFX + "key_openrouter"
CK_KEY_ANTH   = _PFX + "key_anthropic"
CK_OLLAMA_EP  = _PFX + "ollama_endpoint"
CK_OLLAMA_MDL = _PFX + "ollama_model"
CK_LANGUAGE   = _PFX + "language"
CK_SOURCE     = _PFX + "source"
CK_OWN_PROMPT = _PFX + "own_prompt"
CK_CHIPS      = _PFX + "chips_config"
CK_FONT_SIZE  = _PFX + "font_size"

_DEFAULT_CHIPS: Dict[str, Any] = {
    "builtin":   {"short": True, "concise": True, "detailed": True,
                  "mcq": True, "mnemonic": True},
    "shortcuts": {"short": "", "concise": "", "detailed": "", "mcq": "", "mnemonic": ""},
    "custom":    [],
}

# ── Module globals ────────────────────────────────────────────────────────────
_dock:            Optional[Any] = None
_webview:         Optional[Any] = None
_profile:         Optional[Any] = None
_hooks_connected: bool          = False
_conversation:    List[Dict[str, str]] = []
_dispatcher:      Optional[Any] = None   # set up in _setup_sidebar()


# ── Cross-thread JS dispatcher (signal/slot, always marshals to main thread) ──
# QTimer.singleShot() does NOT work from plain threading.Thread workers because
# those threads have no Qt event loop.  A queued signal → slot connection is the
# correct Qt way to send a call from any thread to the main (GUI) thread.
if _qt_ok and QObject is not object and pyqtSignal is not object:

    class _JsDispatcher(QObject):  # type: ignore[misc]
        _sig = pyqtSignal(str)

        def __init__(self) -> None:
            super().__init__()
            # Qt.ConnectionType.QueuedConnection is the default for cross-thread
            # signals but we spell it out for clarity.
            self._sig.connect(self._execute, Qt.ConnectionType.QueuedConnection)
            print("AI Assistant: JS dispatcher created (signal/slot bridge)")

        def _execute(self, code: str) -> None:
            """Runs on the main thread via the event loop."""
            _run_js(code)

        def dispatch(self, code: str) -> None:
            """Thread-safe: emit from any thread; slot runs on main thread."""
            self._sig.emit(code)

else:
    class _JsDispatcher:  # type: ignore[no-redef]
        def dispatch(self, code: str) -> None:
            print(f"AI Assistant: _JsDispatcher stub – Qt not available. code: {code[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
# Config helpers
# ══════════════════════════════════════════════════════════════════════════════

def _cfg_get(key: str, default: Any = "") -> Any:
    if _anki_ok and mw and mw.col:
        try:
            return mw.col.get_config(key, default)
        except Exception as e:
            print(f"AI Assistant: config read error for '{key}': {e}")
    return default

def _cfg_set(key: str, value: Any) -> None:
    if _anki_ok and mw and mw.col:
        try:
            mw.col.set_config(key, value)
        except Exception as e:
            print(f"AI Assistant: config write error for '{key}': {e}")

def _load_settings() -> Dict[str, Any]:
    provider = _cfg_get(CK_PROVIDER, "openai")
    key_map  = {
        "openai":     _cfg_get(CK_KEY_OPENAI, ""),
        "gemini":     _cfg_get(CK_KEY_GEMINI, ""),
        "openrouter": _cfg_get(CK_KEY_OR,     ""),
        "anthropic":  _cfg_get(CK_KEY_ANTH,   ""),
    }
    current_key    = key_map.get(provider, "")
    ollama_ep      = _cfg_get(CK_OLLAMA_EP, OLLAMA_EP_DEFAULT)
    ollama_model   = _cfg_get(CK_OLLAMA_MDL, "")
    effective_model = ollama_model if provider == "ollama" else _cfg_get(CK_MODEL, "")
    return {
        "provider":     provider,
        "model":        effective_model,
        "apiKey":       current_key,
        "language":     _cfg_get(CK_LANGUAGE,  "English"),
        "source":       _cfg_get(CK_SOURCE,    "Front & Back"),
        "ownPrompt":    _cfg_get(CK_OWN_PROMPT, DEFAULT_OWN_PROMPT),
        "ollamaEndpoint": ollama_ep,
        "isDark":         _detect_night_mode(),
        "isConfigured":   _is_configured(provider, current_key),
        "chipsConfig":    _cfg_get(CK_CHIPS, _DEFAULT_CHIPS),
        "accentColor":    _get_theme_accent(_detect_night_mode()),
        "fontSize":       _cfg_get(CK_FONT_SIZE, "13px"),
    }

def _claude_cli_path() -> Optional[str]:
    """Locate the local `claude` (Claude Code) CLI binary.

    Anki launches with a minimal PATH that often omits user bin dirs, so we
    fall back to the common install locations before giving up.
    """
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        os.path.expanduser("~/.local/bin/claude"),
        os.path.expanduser("~/.claude/local/claude"),
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
        "/usr/bin/claude",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def _is_configured(provider: str, api_key: str) -> bool:
    if provider == "ollama":
        return True
    if provider == "claude_cli":
        return _claude_cli_path() is not None
    return bool(api_key and api_key.strip())

def _save_settings_dict(data: Dict[str, Any]) -> None:
    provider  = data.get("provider", "openai")
    api_key   = data.get("apiKey", "").strip()
    model     = data.get("model", "").strip()
    ollama_ep = data.get("ollamaEndpoint", OLLAMA_EP_DEFAULT).strip() or OLLAMA_EP_DEFAULT

    _cfg_set(CK_PROVIDER,   provider)
    _cfg_set(CK_LANGUAGE,   data.get("language",  "English"))
    _cfg_set(CK_SOURCE,     data.get("source",    "Front & Back"))
    font_size = data.get("fontSize", "13px").strip()
    if font_size:
        _cfg_set(CK_FONT_SIZE, font_size)
    _cfg_set(CK_OWN_PROMPT, data.get("ownPrompt", DEFAULT_OWN_PROMPT))
    _cfg_set(CK_OLLAMA_EP,  ollama_ep)

    if provider == "ollama":
        if model:
            _cfg_set(CK_OLLAMA_MDL, model)
    else:
        if model:
            _cfg_set(CK_MODEL, model)
        key_cfg = {
            "openai":     CK_KEY_OPENAI,
            "gemini":     CK_KEY_GEMINI,
            "openrouter": CK_KEY_OR,
            "anthropic":  CK_KEY_ANTH,
        }
        if provider in key_cfg and api_key:
            _cfg_set(key_cfg[provider], api_key)

    print(f"AI Assistant: settings saved — provider={provider}, model={model}, "
          f"endpoint={ollama_ep if provider=='ollama' else 'n/a'}, "
          f"key={'(set)' if api_key else '(empty)'}")


# ══════════════════════════════════════════════════════════════════════════════
# API error classification
# ══════════════════════════════════════════════════════════════════════════════

def _classify_error(exc: Exception, provider: str = "") -> str:
    """Return a clear, user-facing error message."""
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass

        if code in (401, 403):
            return (
                f"Invalid API key (HTTP {code}). "
                "Please check your key in Settings → API Key."
            )
        elif code == 429:
            if provider == "openrouter":
                return (
                    "Rate limit exceeded (HTTP 429) from OpenRouter. "
                    "If you selected a model ending in ':free', those models are rate-limited "
                    "for everyone, even with a paid key. "
                    "Open Settings and switch to a paid model such as "
                    "'openai/gpt-4o-mini' or 'google/gemini-2.0-flash-001'."
                )
            return (
                "Rate limit exceeded (HTTP 429). "
                "You've sent too many requests — please wait a moment and try again."
            )
        elif code == 400:
            detail = body or exc.reason or "bad request"
            return f"Bad request (HTTP 400): {detail}"
        elif code == 404:
            return (
                f"Model not found (HTTP 404). "
                "Check that the model name in Settings is correct."
            )
        elif code >= 500:
            return (
                f"Server error (HTTP {code}). "
                f"The {provider or 'API'} service may be temporarily down. Try again later."
            )
        else:
            return f"API error (HTTP {code}): {exc.reason or body}"

    elif isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        reason_str = str(reason)
        if isinstance(reason, ConnectionRefusedError):
            if provider == "ollama":
                return (
                    "Cannot connect to Ollama (connection refused). "
                    "Make sure Ollama is running on your computer."
                )
            return f"Connection refused by {provider or 'server'}."
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            return (
                "Request timed out. "
                "Check your internet connection or try a smaller model."
            )
        elif any(x in reason_str for x in ("Name or service not known",
                                            "nodename nor servname",
                                            "Temporary failure in name resolution",
                                            "getaddrinfo failed")):
            return (
                "Cannot reach server. "
                "Please check your internet connection."
            )
        elif "Connection refused" in reason_str:
            if provider == "ollama":
                return "Ollama is not running. Start Ollama and try again."
            return f"Connection refused: {reason_str}"
        else:
            return f"Network error: {reason_str}"

    elif isinstance(exc, (TimeoutError, socket.timeout)):
        return "Request timed out. Check your internet connection."

    elif isinstance(exc, json.JSONDecodeError):
        return f"Unexpected response from server (not valid JSON): {exc.msg}"

    else:
        return str(exc)


# ══════════════════════════════════════════════════════════════════════════════
# Streaming API providers
# All providers use streaming (SSE / NDJSON) for the typewriter effect.
# ══════════════════════════════════════════════════════════════════════════════

def _stream_openai_compat(
    url: str,
    api_key: str,
    model: str,
    messages: list,
    on_chunk: Callable[[str], None],
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> None:
    """OpenAI-compatible streaming (also used for OpenRouter)."""
    print(f"AI Assistant: streaming OpenAI-compat url={url.split('/')[2]}, model={model}")
    payload = json.dumps({
        "model": model, "messages": messages, "max_tokens": 2048, "stream": True,
    }).encode("utf-8")
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                ev      = json.loads(data_str)
                choices = ev.get("choices") or []
                if choices:
                    content = (choices[0].get("delta") or {}).get("content") or ""
                    if content:
                        on_chunk(content)
            except Exception:
                pass


def _stream_gemini(
    api_key: str,
    model: str,
    messages: list,
    on_chunk: Callable[[str], None],
) -> None:
    """Gemini streaming via SSE (alt=sse)."""
    print(f"AI Assistant: streaming Gemini, model={model}")
    contents: list = []
    system_parts: list = []
    for m in messages:
        if m["role"] == "system":
            system_parts.append({"text": m["content"]})
        else:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload_dict: Dict[str, Any] = {"contents": contents}
    if system_parts:
        payload_dict["system_instruction"] = {"parts": system_parts}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:streamGenerateContent?key={api_key}&alt=sse")
    payload = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                ev         = json.loads(data_str)
                candidates = ev.get("candidates") or []
                if candidates:
                    parts = (candidates[0].get("content") or {}).get("parts") or []
                    if parts:
                        text = parts[0].get("text") or ""
                        if text:
                            on_chunk(text)
            except Exception:
                pass


def _stream_anthropic(
    api_key: str,
    model: str,
    messages: list,
    on_chunk: Callable[[str], None],
) -> None:
    """Anthropic streaming via SSE."""
    print(f"AI Assistant: streaming Anthropic, model={model}")
    system    = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    payload_dict: Dict[str, Any] = {
        "model": model, "max_tokens": 2048, "messages": user_msgs, "stream": True,
    }
    if system:
        payload_dict["system"] = system
    payload = json.dumps(payload_dict).encode("utf-8")
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type":      "application/json",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                ev = json.loads(data_str)
                if ev.get("type") == "content_block_delta":
                    text = (ev.get("delta") or {}).get("text") or ""
                    if text:
                        on_chunk(text)
                elif ev.get("type") == "message_stop":
                    break
            except Exception:
                pass


def _stream_ollama(
    model: str,
    messages: list,
    endpoint: str,
    on_chunk: Callable[[str], None],
) -> None:
    """Ollama streaming via newline-delimited JSON."""
    print(f"AI Assistant: streaming Ollama, model={model}, endpoint={endpoint}")
    payload = json.dumps({
        "model": model, "messages": messages, "stream": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/api/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                ev      = json.loads(line)
                content = (ev.get("message") or {}).get("content") or ""
                if content:
                    on_chunk(content)
                if ev.get("done"):
                    break
            except Exception:
                pass


def _stream_claude_cli(
    model: str,
    messages: list,
    on_chunk: Callable[[str], None],
) -> None:
    """Stream a reply from the local Claude Code CLI (`claude -p`).

    No API key required — uses the user's existing Claude Code login. The
    system prompt is passed via --append-system-prompt; the conversation is
    flattened into a single prompt delivered on stdin. Output streams to the
    webview as it is generated.
    """
    binary = _claude_cli_path()
    if not binary:
        raise RuntimeError(
            "Claude CLI not found. Install Claude Code and make sure the "
            "`claude` command works in your terminal, then try again."
        )
    print(f"AI Assistant: streaming Claude CLI, model={model}, bin={binary}")

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    convo  = [m for m in messages if m["role"] != "system"]
    # Flatten the conversation into one prompt (CLI -p takes a single prompt).
    parts: List[str] = []
    for m in convo:
        role = "Assistant" if m["role"] == "assistant" else "User"
        parts.append(f"{role}: {m['content']}")
    prompt = "\n\n".join(parts).strip() or "Hello"

    cmd = [binary, "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    if system:
        cmd += ["--append-system-prompt", system]

    env = dict(os.environ)
    # Anki's webview can leave these set in ways that confuse subprocesses.
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1,
    )
    try:
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            if line:
                on_chunk(line)
        ret = proc.wait(timeout=300)
        if ret != 0:
            err = (proc.stderr.read() if proc.stderr else "").strip()
            raise RuntimeError(
                err or f"Claude CLI exited with code {ret}."
            )
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass
        if proc.poll() is None:
            proc.kill()


# ══════════════════════════════════════════════════════════════════════════════
# Thread helper & JS runner
# ══════════════════════════════════════════════════════════════════════════════

def _run_js(code: str) -> None:
    """Run JS in the webview (must be called from the main thread)."""
    global _webview
    if not _webview:
        print(f"AI Assistant: _run_js called but webview is None. code: {code[:60]}")
        return
    try:
        page = _webview.page()
        if page:
            page.runJavaScript(code)
        else:
            print("AI Assistant: _run_js called but page is None")
    except Exception as e:
        print(f"AI Assistant: runJavaScript error: {e}")

def _js_on_main(code: str) -> None:
    """Thread-safe: run JS on the Qt main thread via the signal dispatcher.

    Works correctly from plain threading.Thread workers (no Qt event loop
    needed in the calling thread — the queued signal does the marshalling).
    """
    if _dispatcher is not None:
        _dispatcher.dispatch(code)
    else:
        # Fallback before dispatcher is initialised (should be rare)
        print(f"AI Assistant: _js_on_main – dispatcher not ready, code: {code[:60]}")
        if _qt_ok and QTimer is not object:
            QTimer.singleShot(0, lambda: _run_js(code))

def _run_api_in_thread(settings: Dict[str, Any], messages: List[Dict]) -> None:
    """Stream API response token by token; each chunk is dispatched to the webview."""
    def worker() -> None:
        provider  = settings.get("provider", "?")
        model     = settings.get("model", "")
        api_key   = settings.get("apiKey", "")
        ollama_ep = settings.get("ollamaEndpoint", OLLAMA_EP_DEFAULT)
        full_text: List[str] = []

        if not model and provider != "claude_cli":
            err = "No model selected. Please configure a model in Settings."
            _js_on_main(f"receiveResponse({json.dumps(err)}, true);")
            return

        def on_chunk(chunk: str) -> None:
            full_text.append(chunk)
            _js_on_main(f"appendChunk({json.dumps(chunk)});")

        try:
            # Signal JS to create the streaming bubble (hides typing indicator)
            _js_on_main("startAIBubble();")

            if provider == "openai":
                _stream_openai_compat(
                    "https://api.openai.com/v1/chat/completions",
                    api_key, model, messages, on_chunk,
                )
            elif provider == "gemini":
                _stream_gemini(api_key, model, messages, on_chunk)
            elif provider == "openrouter":
                _stream_openai_compat(
                    "https://openrouter.ai/api/v1/chat/completions",
                    api_key, model, messages, on_chunk,
                    extra_headers={
                        "HTTP-Referer": "https://synapse-pro.vercel.app/",
                        "X-Title":      "SynapsePro",
                    },
                )
            elif provider == "anthropic":
                _stream_anthropic(api_key, model, messages, on_chunk)
            elif provider == "ollama":
                _stream_ollama(model, messages, ollama_ep, on_chunk)
            elif provider == "claude_cli":
                _stream_claude_cli(model, messages, on_chunk)
            else:
                raise RuntimeError(f"Unknown provider: '{provider}'")

            text = "".join(full_text)
            _conversation.append({"role": "assistant", "content": text})
            _js_on_main("finalizeResponse();")
            print(f"AI Assistant: streaming done [{provider}] ({len(text)} chars)")

        except Exception as exc:
            err_msg = _classify_error(exc, provider)
            _EXPECTED = (urllib.error.HTTPError, urllib.error.URLError,
                         TimeoutError, socket.timeout, json.JSONDecodeError,
                         RuntimeError)
            if isinstance(exc, _EXPECTED):
                print(f"AI Assistant: API error [{provider}] {type(exc).__name__}: {exc}")
            else:
                print(f"AI Assistant: unexpected error [{provider}]:")
                traceback.print_exc()

            if full_text:
                # Partial response was streamed — finalize it, then show error below
                _js_on_main("finalizeResponse();")
            else:
                # Nothing arrived yet — remove the empty bubble
                _js_on_main("cancelStream();")
            _js_on_main(f"receiveResponse({json.dumps(err_msg)}, true);")

    threading.Thread(target=worker, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# Conversation management
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_MSG: Dict[str, str] = {
    "role":    "system",
    "content": (
        "You are a helpful study assistant integrated into the Anki flashcard app. "
        "Provide clear, educational responses. Be concise unless the user asks for detail. "
        "When explaining flashcard content, go beyond rephrasing — add context, "
        "examples, or analogies to deepen understanding."
    ),
}

def _reset_conversation() -> None:
    global _conversation
    _conversation = [dict(_SYSTEM_MSG)]
    print("AI Assistant: conversation history reset")


# ══════════════════════════════════════════════════════════════════════════════
# Card content helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_card_content() -> Optional[str]:
    if not _anki_ok or not mw or mw.state != "review":
        print("AI Assistant: _get_card_content – not in review state")
        return None
    try:
        rev: Any = mw.reviewer
        if not rev or not rev.card:
            return None
        note   = rev.card.note()
        source = _cfg_get(CK_SOURCE, "Front & Back")

        # Helper: strip HTML
        def _strip(raw: str) -> str:
            return " ".join(re.sub(r"<[^<]+?>", " ", raw or "").split()).strip()

        # Back Only mode
        if source == "Back Only":
            for bn in PREFERRED_BACK:
                if bn in note:
                    back = _strip(note[bn])
                    if back:
                        print(f"AI Assistant: card content (back only) = '{back[:80]}…'")
                        return back
            print("AI Assistant: no back content found for Back Only mode")
            return None

        # Get front
        front = ""
        for fn in PREFERRED_FRONT:
            if fn in note:
                front = _strip(note[fn])
                if front:
                    break

        # Fallback: use first non-empty field if none of the preferred names matched
        if not front:
            for fn in note.keys():
                val = _strip(note[fn])
                if val:
                    front = val
                    print(f"AI Assistant: using fallback field '{fn}' as front content")
                    break

        if not front:
            print("AI Assistant: no front content found in card fields")
            return None

        if source == "Front & Back":
            for bn in PREFERRED_BACK:
                if bn in note:
                    back = _strip(note[bn])
                    if back:
                        result = f"Front: {front} | Back: {back}"
                        print(f"AI Assistant: card content = '{result[:80]}…'")
                        return result

        print(f"AI Assistant: card content = '{front[:80]}…'")
        return front
    except Exception as e:
        print(f"AI Assistant: _get_card_content error: {e}")
        return None

def _lang_suffix() -> str:
    return LANG_SUFFIX.get(_cfg_get(CK_LANGUAGE, "English"), "in English")

def _build_chip_prompt(action: str, content: str) -> str:
    lang = _lang_suffix()
    prompts = {
        "short": (
            f'Briefly explain the core idea of "{content}" (from an Anki flashcard) '
            f"{lang}. Add 1–2 clarifying points beyond the card. Keep it short."
        ),
        "concise": (
            f'Give a concise but comprehensive explanation of "{content}" (Anki card) '
            f"{lang}. Focus on critical aspects and relationships."
        ),
        "detailed": (
            f'Explain "{content}" (Anki card) in detail {lang}. '
            f"Use structure (headings, bullet points), analogies, and real-world examples."
        ),
        "mcq": (
            f'Create a single multiple-choice question with 4 options (one correct) '
            f'{lang} about "{content}". Do NOT reveal the answer. '
            f"After the user responds, check if they are correct and explain why."
        ),
        "mnemonic": (
            f'Create a creative mnemonic, acronym, or memory aid {lang} for "{content}". '
            f"Only the mnemonic, no extra explanation."
        ),
    }
    if action in prompts:
        return prompts[action]
    if action == "own":
        template = _cfg_get(CK_OWN_PROMPT, DEFAULT_OWN_PROMPT)
        if "{content}" not in template:
            print("AI Assistant: own prompt template missing {content}, using default")
            template = DEFAULT_OWN_PROMPT
        return template.replace("{content}", f'"{content}"') + f" {lang}"
    return f'Tell me about "{content}" {lang}.'


# ══════════════════════════════════════════════════════════════════════════════
# ChatPage – console.log("PYCALL:…") interception
# ══════════════════════════════════════════════════════════════════════════════

if _qt_ok and QWebEnginePage is not object:

    class ChatPage(QWebEnginePage):  # type: ignore[misc]
        """
        Intercepts console.log messages from chat_ui.html.
        JS sends:  console.log("PYCALL:<action>:<json-data>")
        Python parses the action name and data, then dispatches.
        All other console messages are printed for debugging.
        """

        def javaScriptConsoleMessage(self, level, message, line, source):  # type: ignore[override]
            msg = str(message or "")

            if msg.startswith("PYCALL:"):
                rest    = msg[7:]
                colon   = rest.find(":")
                action  = rest[:colon] if colon >= 0 else rest
                data_str = rest[colon + 1:] if colon >= 0 else "{}"
                data: Dict[str, Any] = {}
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError as e:
                    print(f"AI Assistant: PYCALL JSON parse error "
                          f"(action='{action}'): {e} | raw='{data_str[:80]}'")
                print(f"AI Assistant: bridge received action='{action}'")
                try:
                    _handle_action(action, data)
                except Exception as e:
                    print(f"AI Assistant: action '{action}' handler error: {e}")
                    traceback.print_exc()
                return

            # Regular JS console output → print to Anki debug console
            level_names = ["DEBUG", "INFO", "WARNING", "ERROR"]
            try:
                lvl_name = level_names[int(level)] if 0 <= int(level) < 4 else str(level)
            except Exception:
                lvl_name = str(level)
            src = (source or "").split("/")[-1]  # just filename, not full path
            print(f"[JS/{lvl_name}] {src}:{line}: {msg}")

else:
    ChatPage = QWebEnginePage  # type: ignore[assignment,misc]
    print("AI Assistant: WARNING – ChatPage fallback, bridge disabled")


# ══════════════════════════════════════════════════════════════════════════════
# Action handlers
# ══════════════════════════════════════════════════════════════════════════════

def _handle_action(action: str, data: Dict[str, Any]) -> None:
    dispatch = {
        "page_ready":    _action_page_ready,
        "send_message":  _action_send_message,
        "chip_action":   _action_chip,
        "save_settings": _action_save_settings,
        "save_chips":    _action_save_chips,
        "check_ollama":  _action_check_ollama,
        "setup_ollama":  _action_setup_ollama,
        "clear_history": _action_clear_history,
    }
    handler = dispatch.get(action)
    if handler:
        handler(data)
    else:
        print(f"AI Assistant: unknown action '{action}'")


def _action_page_ready(_data: Dict[str, Any]) -> None:
    """HTML page finished loading and is ready to receive init()."""
    print("AI Assistant: page_ready received – injecting init config")
    _reset_conversation()
    _inject_init()


def _action_send_message(data: Dict[str, Any]) -> None:
    text = (data.get("text") or "").strip()
    if not text:
        print("AI Assistant: send_message called with empty text")
        return

    settings = _load_settings()
    provider = settings["provider"]
    api_key  = settings["apiKey"]

    print(f"AI Assistant: send_message provider={provider}, "
          f"model={settings['model']}, key={'(set)' if api_key else '(empty)'}")

    if not _is_configured(provider, api_key):
        print("AI Assistant: not configured – showing error")
        _run_js('receiveResponse("No API key configured. Open Settings (⚙) and enter your API key.", true);')
        return

    _conversation.append({"role": "user", "content": text})
    _run_js("showTyping();")
    _run_api_in_thread(settings, list(_conversation))


def _action_chip(data: Dict[str, Any]) -> None:
    action  = data.get("action", "")
    label   = data.get("label",  action.capitalize())
    content = _get_card_content()

    if not content:
        _run_js('receiveResponse("No card content found. Make sure you are reviewing a card.", true);')
        return

    settings = _load_settings()
    provider = settings["provider"]
    api_key  = settings["apiKey"]

    if not _is_configured(provider, api_key):
        _run_js('receiveResponse("No API key configured. Open Settings (⚙) and enter your API key.", true);')
        return

    if action == "custom":
        template = data.get("prompt", "").strip()
        if not template:
            print("AI Assistant: custom chip called with empty prompt")
            return
        lang   = _lang_suffix()
        prompt = template.replace("{content}", f'"{content}"')
        if lang and lang not in prompt:
            prompt = f"{prompt} {lang}"
    else:
        prompt = _build_chip_prompt(action, content)

    print(f"AI Assistant: chip '{action}' label='{label}' → prompt '{prompt[:80]}…'")

    # Send only the label to JS (not the full prompt) — no user bubble shown
    _run_js(f"receiveChipPrompt({json.dumps(label)});")
    _conversation.append({"role": "user", "content": prompt})
    _run_api_in_thread(settings, list(_conversation))


def _action_save_settings(data: Dict[str, Any]) -> None:
    _save_settings_dict(data)
    tooltip(_("AI settings saved."))


def _action_save_chips(data: Dict[str, Any]) -> None:
    config = data.get("config", {})
    if isinstance(config, dict):
        _cfg_set(CK_CHIPS, config)
        custom_count = len(config.get("custom", []))
        print(f"AI Assistant: chips config saved, custom_count={custom_count}")


def _action_check_ollama(_data: Optional[Dict] = None) -> None:
    """Check if Ollama is running; send result to JS."""
    print("AI Assistant: checking Ollama status…")

    def worker():
        ep = _cfg_get(CK_OLLAMA_EP, OLLAMA_EP_DEFAULT)
        print(f"AI Assistant: connecting to Ollama at {ep}")
        try:
            with urllib.request.urlopen(f"{ep}/api/tags", timeout=5) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in result.get("models", [])]
            print(f"AI Assistant: Ollama running, models={models}")
            _js_on_main(f"setOllamaStatus('running', {json.dumps(models)});")
        except Exception as exc:
            print(f"AI Assistant: Ollama check failed: {exc}")
            _js_on_main("setOllamaStatus('stopped', []);")

    threading.Thread(target=worker, daemon=True).start()


def _action_setup_ollama(_data: Optional[Dict] = None) -> None:
    print("AI Assistant: opening Ollama wizard")
    if _qt_ok and _anki_ok and mw and QTimer is not object:
        QTimer.singleShot(0, _open_ollama_wizard)


def _action_clear_history(_data: Optional[Dict] = None) -> None:
    _reset_conversation()
    print("AI Assistant: chat history cleared")


# ══════════════════════════════════════════════════════════════════════════════
# Ollama Wizard
# ══════════════════════════════════════════════════════════════════════════════

def _open_ollama_wizard() -> None:
    if not _qt_ok or QDialog is object:
        return
    parent = mw if _anki_ok else None
    wizard = OllamaWizard(parent)
    wizard.exec()
    # Refresh Ollama status in the webview after wizard closes
    _action_check_ollama()


if _qt_ok and QDialog is not object:

    class OllamaWizard(QDialog):  # type: ignore[misc]
        """
        Guided 3-step wizard for setting up Ollama.
        Step 0 – Checking
        Step 1 – Install instructions (if not running)
        Step 2 – Model selection / pull
        """
        RECOMMENDED = [
            ("gemma2:2b",   "1.6 GB", "Fast, lightweight"),
            ("llama3.2:3b", "2.0 GB", "Good quality, well-rounded"),
            ("qwen2.5:3b",  "2.0 GB", "Multilingual, good reasoning"),
            ("phi3.5",      "2.2 GB", "Microsoft Phi — fast & capable"),
        ]

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self.setWindowTitle(_("Set up Ollama – Local AI"))
            self.setMinimumWidth(440)
            self._ep = _cfg_get(CK_OLLAMA_EP, OLLAMA_EP_DEFAULT)
            self._installed_models: List[str] = []
            self._pull_thread: Optional[threading.Thread] = None
            self._build_ui()
            self._check_ollama()

        def _build_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(20, 20, 20, 20)
            root.setSpacing(14)

            self._stack = QStackedWidget()
            root.addWidget(self._stack)
            self._stack.addWidget(self._page_checking())
            self._stack.addWidget(self._page_install())
            self._stack.addWidget(self._page_models())

            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            qconnect(btns.rejected, self.reject)
            root.addWidget(btns)

        def _page_checking(self) -> QWidget:
            w = QWidget(); lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(_("Checking Ollama status…"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl); lay.addStretch()
            return w

        def _page_install(self) -> QWidget:
            w = QWidget(); lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
            title = QLabel("<b>" + _("Ollama is not running") + "</b>")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(title)
            desc = QLabel(_(
                "Ollama lets you run AI models locally — free, private, no API key needed.\n\n"
                "1.  Download and install Ollama from <b>ollama.com</b>\n"
                "2.  Start Ollama (runs in the background)\n"
                "3.  Click <i>Check again</i> below"
            ))
            desc.setWordWrap(True)
            desc.setTextFormat(Qt.TextFormat.RichText)
            lay.addWidget(desc)
            row = QHBoxLayout()
            btn_dl = QPushButton(_("Open ollama.com"))
            btn_dl.clicked.connect(lambda: __import__("webbrowser").open("https://ollama.com"))
            btn_chk = QPushButton(_("Check again"))
            btn_chk.clicked.connect(self._check_ollama)
            row.addWidget(btn_dl); row.addWidget(btn_chk)
            lay.addLayout(row); lay.addStretch()
            return w

        def _page_models(self) -> QWidget:
            w = QWidget(); lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)
            title = QLabel("<b>" + _("Choose a Model") + "</b>")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(title)
            lay.addWidget(QLabel(_("Installed models:")))
            self._model_list = QListWidget()
            self._model_list.setMaximumHeight(90)
            lay.addWidget(self._model_list)
            lay.addWidget(QLabel(_("Recommended models to download:")))
            for name, size, desc in self.RECOMMENDED:
                row = QWidget(); rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 2, 0, 2)
                lbl = QLabel(f"<b>{name}</b>  <span style='color:gray'>{size} – {desc}</span>")
                lbl.setTextFormat(Qt.TextFormat.RichText); lbl.setWordWrap(True)
                btn = QPushButton(_("Pull")); btn.setFixedWidth(56)
                btn.clicked.connect(lambda _, n=name: self._pull_model(n))
                rl.addWidget(lbl, 1); rl.addWidget(btn)
                lay.addWidget(row)
            self._progress_lbl = QLabel(""); lay.addWidget(self._progress_lbl)
            self._progress_bar = QProgressBar()
            self._progress_bar.setVisible(False); self._progress_bar.setRange(0, 100)
            lay.addWidget(self._progress_bar)
            btn_use = QPushButton(_("Use Selected Model"))
            btn_use.clicked.connect(self._use_selected)
            lay.addWidget(btn_use); lay.addStretch()
            return w

        def _check_ollama(self) -> None:
            self._stack.setCurrentIndex(0)
            def worker():
                try:
                    with urllib.request.urlopen(f"{self._ep}/api/tags", timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                    models = [m["name"] for m in data.get("models", [])]
                    QTimer.singleShot(0, lambda: self._on_found(models))
                except Exception as exc:
                    print(f"AI Assistant Wizard: Ollama check failed: {exc}")
                    QTimer.singleShot(0, self._on_not_found)
            threading.Thread(target=worker, daemon=True).start()

        def _on_found(self, models: List[str]) -> None:
            self._installed_models = models; self._refresh_list(); self._stack.setCurrentIndex(2)

        def _on_not_found(self) -> None:
            self._stack.setCurrentIndex(1)

        def _refresh_list(self) -> None:
            self._model_list.clear()
            for m in (self._installed_models or ["(no models installed)"]):
                self._model_list.addItem(QListWidgetItem(m))
            if self._installed_models: self._model_list.setCurrentRow(0)

        def _pull_model(self, name: str) -> None:
            if self._pull_thread and self._pull_thread.is_alive(): return
            self._progress_bar.setValue(0); self._progress_bar.setVisible(True)
            self._progress_lbl.setText(_(f"Pulling {name}…"))
            def worker():
                try:
                    url  = f"{self._ep}/api/pull"
                    body = json.dumps({"name": name, "stream": True}).encode()
                    req  = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                    resp = urllib.request.urlopen(req, timeout=None)
                    total = completed = 0
                    for raw in resp:
                        line = raw.decode("utf-8", errors="replace").strip()
                        if not line: continue
                        try: ev = json.loads(line)
                        except Exception: continue
                        if "error" in ev: raise RuntimeError(ev["error"])
                        if "total" in ev:
                            total = int(ev.get("total", 0) or 0)
                            completed = int(ev.get("completed", 0) or 0)
                        if total > 0:
                            pct = int(completed / total * 100)
                            QTimer.singleShot(0, lambda p=pct: self._progress_bar.setValue(p))
                        if ev.get("status") == "success": break
                    QTimer.singleShot(0, lambda: self._on_pull_done(name))
                except Exception as exc:
                    err = str(exc)
                    print(f"AI Assistant Wizard: pull error: {err}")
                    QTimer.singleShot(0, lambda e=err: self._on_pull_error(e))
            self._pull_thread = threading.Thread(target=worker, daemon=True)
            self._pull_thread.start()

        def _on_pull_done(self, name: str) -> None:
            self._progress_bar.setVisible(False)
            self._progress_lbl.setText(_(f"✓ {name} downloaded"))
            self._check_ollama()

        def _on_pull_error(self, err: str) -> None:
            self._progress_bar.setVisible(False)
            self._progress_lbl.setText(f"Error: {err}")

        def _use_selected(self) -> None:
            items = self._model_list.selectedItems()
            if not items: return
            m = items[0].text()
            if m == "(no models installed)": return
            _cfg_set(CK_OLLAMA_MDL, m); _cfg_set(CK_PROVIDER, "ollama")
            tooltip(_(f"Using Ollama model: {m}")); self.accept()

else:
    class OllamaWizard:  # type: ignore[no-redef]
        def __init__(self, *a, **k): pass
        def exec(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# UI setup
# ══════════════════════════════════════════════════════════════════════════════

def _get_html_path() -> str:
    p = os.path.join(constants.addon_path, HTML_FILENAME)
    print(f"AI Assistant: HTML path = {p}  exists={os.path.exists(p)}")
    return p


def _inject_init() -> None:
    """Load current settings and inject them into the HTML via init()."""
    settings = _load_settings()
    print(f"AI Assistant: _inject_init provider={settings['provider']}, "
          f"model={settings['model']}, configured={settings['isConfigured']}")

    if settings["provider"] == "ollama":
        def check_then_init():
            ep = settings.get("ollamaEndpoint", OLLAMA_EP_DEFAULT)
            try:
                with urllib.request.urlopen(f"{ep}/api/tags", timeout=3) as resp:
                    data   = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                settings["ollamaModels"]  = models
                settings["ollamaRunning"] = True
                print(f"AI Assistant: Ollama running at init, models={models}")
            except Exception as exc:
                print(f"AI Assistant: Ollama not available at init: {exc}")
                settings["ollamaModels"]  = []
                settings["ollamaRunning"] = False
            _js_on_main(f"init({json.dumps(settings)});")
        threading.Thread(target=check_then_init, daemon=True).start()
    else:
        _run_js(f"init({json.dumps(settings)});")


def _update_chips() -> None:
    if _webview and _anki_ok and mw:
        in_review = (mw.state == "review")
        _run_js(f"setChipsEnabled({'true' if in_review else 'false'});")


def _setup_sidebar() -> bool:
    global _dock, _webview, _profile, _hooks_connected, _dispatcher

    if _dock is not None:
        print("AI Assistant: sidebar already set up")
        return True
    if not _qt_ok:
        print("AI Assistant: cannot setup – Qt not available")
        return False
    if not _anki_ok:
        print("AI Assistant: cannot setup – Anki not available")
        return False

    print("AI Assistant: setting up sidebar…")
    _reset_conversation()

    # Create the dispatcher on the main thread so its slots run here.
    if _dispatcher is None:
        _dispatcher = _JsDispatcher()

    try:
        # Profile
        profile_path = os.path.join(constants.addon_path, "ai_v2_profile")
        os.makedirs(profile_path, exist_ok=True)
        _profile = QWebEngineProfile(
            f"SynapseAIv2_{constants.ADDON_NAME_LAUNCHER}", mw
        )
        _profile.setPersistentStoragePath(profile_path)
        _profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        s = _profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled,   True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        print("AI Assistant: WebEngine profile created")

        # WebView + ChatPage (console.log bridge)
        _webview = QWebEngineView()
        page     = ChatPage(_profile, _webview)
        _webview.setPage(page)

        # Load HTML
        html_path = _get_html_path()
        if not os.path.exists(html_path):
            print(f"AI Assistant: FATAL – chat_ui.html not found at {html_path}")
            showWarning(
                f"AI Assistant: chat_ui.html not found.\n"
                f"Expected: {html_path}"
            )
            return False

        # page_ready signal from JS will trigger _inject_init()
        # (no fixed-delay injection needed)
        _webview.setUrl(QUrl.fromLocalFile(html_path))
        print(f"AI Assistant: loading {html_path}")

        # Dock
        _dock = QDockWidget(_("AI Assistant"), mw)
        _dock.setObjectName(DOCK_NAME)
        _dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        _dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        _dock.setTitleBarWidget(QWidget())
        _dock.setMinimumWidth(340)
        _webview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _dock.setWidget(_webview)
        _dock.setVisible(False)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, _dock)

        # Hooks
        if not _hooks_connected and gui_hooks:
            gui_hooks.state_did_change.append(_on_state_change)
            if hasattr(_dock, "visibilityChanged"):
                qconnect(_dock.visibilityChanged, _on_visibility_changed)
            _hooks_connected = True
            print("AI Assistant: hooks connected")

        print("AI Assistant: sidebar setup complete ✓")
        return True

    except Exception as e:
        print(f"AI Assistant: CRITICAL setup error: {e}")
        traceback.print_exc()
        showWarning(_("AI Assistant setup error: {}").format(e))
        _dock = _webview = _profile = None
        _hooks_connected = False
        return False


# ── Hooks ──────────────────────────────────────────────────────────────────────

def _on_state_change(new_state: str, old_state: str) -> None:
    _update_chips()

def _on_visibility_changed(visible: bool) -> None:
    if visible:
        print("AI Assistant: sidebar became visible")
        _update_chips()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def toggle_ai_assistant_dock() -> None:
    """Show or hide the AI Assistant sidebar. Called by launcher_widget.py."""
    global _dock

    if not _qt_ok or not _anki_ok:
        showWarning(_("AI Assistant is not available (missing Qt/Anki components)."))
        return

    if _dock is None:
        print("AI Assistant: first toggle – running setup")
        if not _setup_sidebar():
            return

    if _dock is None:
        return

    try:
        if _dock.isHidden():
            print("AI Assistant: showing dock")
            _dock.show()
            _dock.raise_()
            _update_chips()
        else:
            print("AI Assistant: hiding dock")
            _dock.hide()
    except Exception as e:
        print(f"AI Assistant: toggle error: {e}")
        traceback.print_exc()


def cleanup_ai_assistant_sidebar() -> None:
    """Called by __init__.py on profile close / add-on unload."""
    global _dock, _webview, _profile, _hooks_connected

    print("AI Assistant: cleanup starting…")

    if _hooks_connected and gui_hooks:
        try:
            gui_hooks.state_did_change.remove(_on_state_change)
        except Exception:
            pass
        if _dock and hasattr(_dock, "visibilityChanged"):
            try:
                _dock.visibilityChanged.disconnect(_on_visibility_changed)
            except Exception:
                pass
        _hooks_connected = False

    if _dock:
        try:
            _dock.deleteLater()
        except Exception as e:
            print(f"AI Assistant: cleanup dock error: {e}")

    _dock = _webview = _profile = None
    _conversation.clear()
    print("AI Assistant: cleanup done ✓")


# ── Module load ───────────────────────────────────────────────────────────────
print(
    f"=== AI Assistant v2 module loaded ==="
    f"  Qt={'6' if constants.qt_version==6 else '5' if constants.qt_version==5 else '?'}"
    f"  qt_ok={_qt_ok}"
    f"  anki_ok={_anki_ok}"
    f"  addon_path={getattr(constants,'addon_path','?')}"
)
