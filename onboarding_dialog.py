# -*- coding: utf-8 -*-
"""
SynapsePro – Web-based Onboarding Dialog
=========================================
Replaces the old QWizard with a QWebEngineView that loads
onboarding/onboarding.html (the polished HTML/CSS flow the user designed).

Communication bridge
--------------------
When the user clicks "Start" on the last screen, the JavaScript calls:

    console.log("SYNAPSEPRO_COMPLETE:" + JSON.stringify({
        lang:        "de",
        themeNumber: 3,
        roleKey:     "medical",
        source:      "ankiStore"
    }));

Python intercepts this via a custom QWebEnginePage subclass and
closes the dialog with accept(), making the result available via
get_result().
"""

import os
import json

# --- Translation ---
try:
    from .locales import _, TRANSLATIONS
except ImportError:
    def _(text): return text  # type: ignore
    TRANSLATIONS = {}  # type: ignore

try:
    from .onboarding_terms import TERMS_TRANSLATIONS
    from .web_translations import WEB_TRANSLATIONS
except ImportError:
    from onboarding_terms import TERMS_TRANSLATIONS  # type: ignore
    from web_translations import WEB_TRANSLATIONS  # type: ignore

# ── Theme mapping ──────────────────────────────────────────────────────────────
# Maps the 1-based index of the theme card (img_theme_N.png) to the
# theme name used by theme.py / addon_settings["active_color_theme"].
# Adjust this dict if the order of your theme images changes.
THEME_INDEX_TO_NAME = {
    1: "ocean",     # img_theme_1.png  — Blue
    2: "horizon",   # img_theme_2.png  — Gray / Slate
    3: "forest",    # img_theme_3.png  — Green
    4: "dusty",     # img_theme_4.png  — Teal
    5: "deluge",    # img_theme_5.png  — Purple
    6: "orchid",    # img_theme_6.png  — Pink / Magenta
}

# ── Role → Fact-category mapping ──────────────────────────────────────────────
# Maps the data-value of the selected role button to the fact_theme key
# used by daily_widgets.generate_daily_widgets_html().
ROLE_TO_FACT_THEME = {
    "medical":    "Medical",
    "law":        "Law",
    "language":   "Countries",
    "highschool": "General",
    "programmer": "General",
    "other":      "General",
}

# ── Qt 6 imports ───────────────────────────────────────────────────────────────
_QT_AVAILABLE = False

try:
    from aqt.qt import QDialog, QVBoxLayout, QUrl, Qt, pyqtSignal, QColor
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage
    _QT_AVAILABLE = True
except ImportError:
    pass


# ── Real implementation (requires WebEngine) ───────────────────────────────────
if _QT_AVAILABLE:

    class _OnboardingPage(QWebEnginePage):
        """
        Custom page that intercepts console.log() to receive the onboarding
        completion payload from JavaScript without needing QWebChannel.
        """
        completed = pyqtSignal(dict)

        def javaScriptConsoleMessage(self, level, message, line, source):
            # The console level is not needed by the bridge.
            if isinstance(message, str) and message.startswith("SYNAPSEPRO_COMPLETE:"):
                try:
                    payload = json.loads(message[len("SYNAPSEPRO_COMPLETE:"):])
                    self.completed.emit(payload)
                except Exception as e:
                    print(f"SynapsePro Onboarding: Failed to parse completion payload: {e}")
            # All other console output is silently swallowed (no dev-console in prod).


    class OnboardingDialog(QDialog):
        """
        Full-screen-ish dialog that hosts the HTML onboarding wizard.

        Usage
        -----
            dlg = OnboardingDialog(addon_path, parent=mw)
            if dlg.exec():
                result = dlg.get_result()
                # result = {"lang": "de", "themeNumber": 3, "roleKey": "medical", ...}
        """

        def __init__(self, addon_path: str, parent=None):
            super().__init__(parent)
            self.addon_path = addon_path
            self._result: dict = {}

            self.setWindowTitle(_("SynapsePro"))
            self.setWindowFlags(
                Qt.WindowType.Dialog |
                Qt.WindowType.WindowCloseButtonHint
            )
            self.resize(860, 540)
            self.setMinimumSize(860, 540)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self.view = QWebEngineView(self)
            self._page = _OnboardingPage(self.view)
            self.view.setPage(self._page)
            self._page.completed.connect(self._on_completed)
            self.view.loadFinished.connect(self._on_load_finished)

            layout.addWidget(self.view)

            html_path = os.path.join(addon_path, "onboarding", "onboarding.html")
            if os.path.exists(html_path):
                try:
                    dark = bool(parent and parent.pm and parent.pm.night_mode())
                    self._page.setBackgroundColor(
                        QColor("#1f2329") if dark else QColor("#ffffff"))
                except Exception:
                    pass
                self.view.load(QUrl.fromLocalFile(html_path))
            else:
                print(f"SynapsePro Onboarding: HTML file not found at {html_path!r}")
                self.accept()  # Skip gracefully so the addon still initialises

        def _on_load_finished(self, ok: bool):
            if not ok:
                return
            error_sources = (
                "SynapsePro error", "Show details", "Hide details", "Copy error",
                "Copied!", "Dismiss", "Unexpected error", "Unexpected error (async)",
                "Your data is safe. Please screenshot the details and send them to help.synapse.pro@gmail.com.",
                "(no stack trace available)",
            )
            errors = {
                lang: {
                    source: source if lang == "en" else WEB_TRANSLATIONS[source][lang]
                    for source in error_sources
                }
                for lang in ("en", "de", "es", "ko", "pt", "fr", "vi", "zh", "hi")
            }
            theme_sources = ("Ocean", "Horizon", "Forest", "Dusty", "Deluge", "Orchid")
            themes = {
                lang: [
                    source if lang == "en" else TRANSLATIONS.get(source, {}).get(lang, source)
                    for source in theme_sources
                ]
                for lang in ("en", "de", "es", "ko", "pt", "fr", "vi", "zh", "hi")
            }
            try:
                dark = bool(self.parent() and self.parent().pm and self.parent().pm.night_mode())
            except Exception:
                dark = False
            payload = json.dumps(
                {"terms": TERMS_TRANSLATIONS, "errors": errors, "themes": themes, "isDark": dark},
                ensure_ascii=False,
            ).replace("</", "<\\/")
            self._page.runJavaScript(
                f"window.initOnboarding && window.initOnboarding({payload});"
            )

        def _on_completed(self, data: dict):
            """Called by the JS bridge when the user clicks 'Start'."""
            self._result = data
            self.accept()

        def get_result(self) -> dict:
            """Return the onboarding payload after exec() returns True."""
            return self._result

    # Backwards-compatible alias — __init__.py calls OnboardingWizard(addon_path, mw)
    OnboardingWizard = OnboardingDialog


else:
    # ── Fallback stub (no WebEngine / Qt not available) ───────────────────────
    # Keeps the addon from crashing; onboarding is simply skipped.
    class OnboardingWizard:          # type: ignore[no-redef]
        def __init__(self, addon_path, parent=None):
            print("SynapsePro Onboarding: QWebEngineView not available, skipping.")

        def exec(self) -> bool:
            return False

        def get_result(self) -> dict:
            return {}

    OnboardingDialog = OnboardingWizard  # type: ignore[assignment]
