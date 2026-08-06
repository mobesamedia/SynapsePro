# -*- coding: utf-8 -*-

from __future__ import annotations

import os, sys, json, re, traceback, shutil
from typing import Optional, Union, Any, Dict

# --- Import Sub-Modules ---
try:
    from . import constants, study_plan_trigger, locales
    from .locales import _
except ImportError as e:
    print(f"SynapsePro1 CRITICAL ERROR: {e}")
    constants=object(); study_plan_trigger=object()
    # Safety fallbacks so UI strings and language handling don't NameError
    # if the locales module fails to import.
    def _(text): return text
    class _LocalesStub: USER_LANG = "auto"
    locales = _LocalesStub()

# --- Anki Imports ---
mw, gui_hooks = None, None
try:
    import anki
    from anki.utils import int_version
    from aqt import mw, gui_hooks
    from aqt.qt import QDockWidget, QWidget, Qt, QTimer
    from aqt.utils import showWarning, tooltip
    from aqt.webview import WebContent
    from aqt.deckbrowser import DeckBrowser, DeckBrowserContent, DeckBrowserBottomBar
    from aqt.overview import Overview, OverviewBottomBar
    from aqt.reviewer import ReviewerBottomBar
    from aqt.toolbar import TopToolbar
except ImportError:
    print(f"SynapsePro1: ERROR - Failed to import Anki modules.")
    QDockWidget, QWidget, Qt, QTimer = object, object, None, None


_anki_version = getattr(anki, "version", "0") if "anki" in globals() else "0"
_minimum_version = getattr(constants, "MIN_ANKI_VERSION", "25.09.4")
_minimum_point_version = getattr(constants, "MIN_ANKI_POINT_VERSION", 250904)
_anki_point_version = int_version() if "int_version" in globals() else 0
if mw and _anki_point_version < _minimum_point_version:
    _version_error = (
        f"SynapsePro requires Anki {_minimum_version} or newer "
        f"(installed: {_anki_version})."
    )
    print(_version_error)
    try:
        QTimer.singleShot(0, lambda msg=_version_error: showWarning(msg))
    except Exception:
        pass
    raise RuntimeError(_version_error)

# --- Sound ---
if hasattr(constants, 'sound_available'): constants.sound_available = False
try:
    if mw: from anki.sound import play; constants.sound_available = True; constants.play_sound_function = play
except ImportError: pass

# --- Load Feature Modules ---
modules_loaded = False
try:
    from . import onboarding_dialog
    from . import mode
    from .launcher_widget import SidebarWidget
    from .pomodoro import init_pomodoro, cleanup_pomodoro
    from .website_sidebar import cleanup_website_sidebar
    from .background_music import cleanup_music_player
    from .ai_assistant import cleanup_ai_assistant_sidebar
    from .mindmap_sidebar import cleanup_mindmap_sidebar    
    from .notebook_sidebar import cleanup_notebook_sidebar, setup_notebook_sidebar, toggle_notebook_dock
    from . import deck_overview, sidebar_shortcuts
    from . import statistics_widget, daily_widgets, minimal_dashboard, settings_dialog
    from .gamification import GamificationManager, CMD_RESET_DATA, CMD_CLAIM_CHALLENGE, CMD_LP_START_PREFIX, CMD_LP_PAUSE_PREFIX
    from .sidebar import GamificationSidebar
    from .learning_plan import LearningPlanManager
    from .deadline_bar import DeadlineManager
    from .configuration import LearningPlanConfigDialog, StudyPlanViewerDialog, DeadlineViewerDialog, DeadlineConfigDialog
    modules_loaded = True
except Exception as e:
    print(f"SynapsePro1: ERROR - Failed to import sub-modules: {e}")
    traceback.print_exc()

# --- Config Paths ---
addon_path = os.path.dirname(__file__)

study_plan_config_json_path = os.path.join(addon_path, "study_plan_config.json")
addon_settings_path = os.path.join(addon_path, "addon_settings.json") 

if hasattr(constants, 'addon_path'):
    constants.addon_path = addon_path
    constants.icons_folder = os.path.join(addon_path, constants.ICONS_SUBFOLDER)

# --- Global State ---
addon_settings: Dict[str, Any] = {}
launcher_dock_widget: Optional[QDockWidget] = None
# Keep these annotations independent from optional feature imports.  If one
# feature cannot be imported, SynapsePro should still fail gracefully instead
# of raising a second NameError while initialising its globals.
sidebar_widget_instance: Optional[Any] = None
gamification_manager: Optional[Any] = None
gamification_sidebar: Optional[Any] = None
learning_plan_manager: Optional[Any] = None
deadline_manager: Optional[Any] = None
_dashboard_rendered_with_models = False
_daily_maintenance_done = False
_top_toolbar_redraw_generation = 0
_profile_generation = 0

_TOP_TOOLBAR_SIDEBAR_CMD = "synapsepro_toggle_launcher_sidebar"
_TOP_TOOLBAR_SIDEBAR_ID = "synapsepro-sidebar-toggle"
_TOP_TOOLBAR_SIDEBAR_ICON_ID = "synapsepro-sidebar-toggle-icon"

# --- Settings Handling ---
def get_default_settings() -> Dict[str, Any]:
    return {
        "onboarding_completed": False,
        "theme_enabled": True,
        "active_theme": "medical_theme.css",
        "fact_theme": "Medical", 
        "sidebar_visibility_mode": "always_show",
        "minimal_dashboard_enabled": False,
        "gamification_widgets_enabled": True, "daily_widgets_enabled": True, 
        "deadline_bar_enabled": True, "statistics_widget_enabled": True,
        "deck_overview_enabled": True,
        "pomodoro_enabled": True, "ai_assistant_enabled": True,
        "website_viewer_enabled": True, "notebook_enabled": True,
        "mindmap_enabled": True, "gamification_sidebar_enabled": True,
        "gamification_popups_enabled": True,
        "music_player_enabled": True, "stats_time_range": 7,
        "sidebar_shortcuts": {},
        "language": "auto",  # UI language: "auto", "en", "de", "es"
        "active_color_theme": "ocean",   # Colour theme: "ocean","orchid","forest","deluge","horizon","dusty","custom"
        "custom_theme_colors": {},       # Used when active_color_theme == "custom"
        "custom_bg_light": "#f5f5f7",    # Custom solid background (light mode)
        "custom_bg_dark":  "#1f1f21",    # Custom solid background (dark mode)
    }

# --- Custom solid background -------------------------------------------------
_HEX_RE = None

def _is_valid_hex(color: str) -> bool:
    global _HEX_RE
    if _HEX_RE is None:
        import re
        _HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
    return isinstance(color, str) and bool(_HEX_RE.match(color))

def write_custom_solid_css() -> None:
    """(Re)generate theme/user_files/custom_solid.css from the user's colours.

    Uses solid_light.css as a template and swaps its two placeholder colours.
    Safe no-op if the template is missing or the colours are invalid.
    """
    try:
        light = addon_settings.get("custom_bg_light", "#f5f5f7")
        dark = addon_settings.get("custom_bg_dark", "#1f1f21")
        if not _is_valid_hex(light): light = "#f5f5f7"
        if not _is_valid_hex(dark):  dark = "#1f1f21"
        base_dir = os.path.join(addon_path, "theme", "user_files")
        template_path = os.path.join(base_dir, "solid_light.css")
        if not os.path.exists(template_path):
            print("SynapsePro: custom solid template missing, skipping generation.")
            return
        with open(template_path, "r", encoding="utf-8") as f:
            css = f.read()
        css = css.replace("#f5f5f7", light).replace("#1f1f21", dark)
        css = "/* custom_solid.css — auto-generated, edits will be overwritten */\n" + css
        with open(os.path.join(base_dir, "custom_solid.css"), "w", encoding="utf-8") as f:
            f.write(css)
        print(f"SynapsePro: custom solid background written ({light}/{dark}).")
    except Exception as e:
        print(f"SynapsePro: could not write custom solid css: {e}")

def load_addon_settings():
    global addon_settings
    defaults = get_default_settings()
    try:
        with open(addon_settings_path, 'r', encoding='utf-8') as f:
            defaults.update(json.load(f))
    except FileNotFoundError:
        pass  # First run / no settings yet — defaults are correct.
    except json.JSONDecodeError as e:
        print(f"SynapsePro1: settings file corrupt, falling back to defaults: {e}")
    addon_settings = defaults

def save_addon_settings():
    tmp_path = addon_settings_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(addon_settings, f, indent=4)
        os.replace(tmp_path, addon_settings_path)
    except Exception as e:
        try:
            if os.path.exists(tmp_path): os.remove(tmp_path)
        except OSError: pass
        print(f"SynapsePro1 ERROR: Save settings: {e}")

def _sync_toolbar_review_class(new_state: str):
    """Toggle the 'reviewing' class on the persistent toolbar webviews.

    Solid-colour background themes use this to revert the top/bottom toolbar
    to Anki's default grey while a card is being reviewed — the solid colour
    should only show on the main screens.
    """
    try:
        flag = "true" if new_state == "review" else "false"
        js = f"document.body && document.body.classList.toggle('reviewing', {flag});"
        if mw and getattr(mw, "toolbar", None) and getattr(mw.toolbar, "web", None):
            mw.toolbar.web.eval(js)
        if mw and getattr(mw, "bottomWeb", None):
            mw.bottomWeb.eval(js)
    except Exception as e:
        print(f"SynapsePro: toolbar review sync failed: {e}")


def _launcher_sidebar_is_visible() -> bool:
    """Return the live dock visibility without retaining a deleted Qt object."""
    try:
        return bool(launcher_dock_widget and launcher_dock_widget.isVisible())
    except RuntimeError:
        return False


def _launcher_sidebar_icon_url(is_open: bool) -> str:
    """Return the exported URL for the current launcher-sidebar icon."""
    try:
        addon_pkg = mw.addonManager.addonFromModule(__name__) if mw else None
    except Exception:
        addon_pkg = None
    if not addon_pkg:
        addon_pkg = constants.addon_package_name
    state = "open" if is_open else "closed"
    return f"/_addons/{addon_pkg}/media/sidebar_icon_{state}.svg"


def _sync_launcher_toolbar_button(*_args) -> None:
    """Mirror the launcher dock state in the icon inside Anki's web toolbar."""
    try:
        toolbar = getattr(mw, "toolbar", None) if mw else None
        web = getattr(toolbar, "web", None)
        if web is None:
            return
        is_visible = _launcher_sidebar_is_visible()
        visible = "true" if is_visible else "false"
        icon_url = json.dumps(_launcher_sidebar_icon_url(is_visible))
        web.eval(
            "(function(){var b=document.getElementById(" 
            + json.dumps(_TOP_TOOLBAR_SIDEBAR_ID)
            + ");if(!b)return;b.classList.toggle('is-open',"
            + visible
            + ");b.setAttribute('aria-pressed',"
            + visible
            + ");var i=document.getElementById("
            + json.dumps(_TOP_TOOLBAR_SIDEBAR_ICON_ID)
            + ");var n="
            + icon_url
            + ";if(i&&i.getAttribute('src')!==n)i.setAttribute('src',n);})();"
        )
    except (RuntimeError, AttributeError):
        pass
    except Exception as e:
        print(f"SynapsePro: sidebar toolbar state sync failed: {e}")


def toggle_launcher_sidebar() -> None:
    """Show or hide SynapsePro's narrow launcher dock."""
    if not launcher_dock_widget:
        return
    try:
        launcher_dock_widget.setVisible(not launcher_dock_widget.isVisible())
        _sync_launcher_toolbar_button()
    except RuntimeError:
        pass


def _add_launcher_toggle_to_top_toolbar(links, toolbar) -> None:
    """Insert a native toolbar link before Anki's Decks link."""
    try:
        if any(_TOP_TOOLBAR_SIDEBAR_ID in str(link) for link in links):
            return

        tooltip_text = _("Show or hide the launcher sidebar.")
        link = toolbar.create_link(
            _TOP_TOOLBAR_SIDEBAR_CMD,
            "Sidebar",
            toggle_launcher_sidebar,
            tip=tooltip_text,
            id=_TOP_TOOLBAR_SIDEBAR_ID,
        )

        is_visible = _launcher_sidebar_is_visible()
        active_class = " is-open" if is_visible else ""
        pressed = "true" if is_visible else "false"
        icon_url = _launcher_sidebar_icon_url(is_visible)
        icon_html = (
            f' aria-pressed="{pressed}">'
            f'<img id="{_TOP_TOOLBAR_SIDEBAR_ICON_ID}" aria-hidden="true" '
            f'draggable="false" width="14" height="14" src="{icon_url}" '
            'style="width:14px;height:14px;min-width:14px;max-width:14px;'
            'min-height:14px;max-height:14px;object-fit:contain">'
            '</a>'
        )
        link = link.replace(
            "class=hitem",
            f'class="hitem sp-sidebar-toggle{active_class}"',
            1,
        ).replace(
            ">Sidebar</a>",
            icon_html,
            1,
        )

        style = f"""
        <style>
          #{_TOP_TOOLBAR_SIDEBAR_ID}.sp-sidebar-toggle {{
            box-sizing:border-box; padding:5px 7px !important; margin:0 2px 0 0;
            line-height:18px; vertical-align:baseline;
            color:#000 !important; background:transparent !important;
            border-color:transparent !important; border-radius:0; box-shadow:none !important;
            text-decoration:none !important; opacity:1;
          }}
          #{_TOP_TOOLBAR_SIDEBAR_ID}:hover {{
            color:#000 !important; background:transparent !important;
            border-color:transparent !important; box-shadow:none !important; opacity:1;
          }}
          #{_TOP_TOOLBAR_SIDEBAR_ID}:active {{
            color:#000 !important; background:transparent !important;
            border-color:transparent !important; box-shadow:none !important; opacity:1;
          }}
          #{_TOP_TOOLBAR_SIDEBAR_ICON_ID} {{
            box-sizing:border-box; display:inline-block; vertical-align:middle;
            width:14px; height:14px; min-width:14px; max-width:14px;
            min-height:14px; max-height:14px; margin:0; padding:0; object-fit:contain;
            transform:translate(1px,-1px);
          }}
          :root.night-mode #{_TOP_TOOLBAR_SIDEBAR_ICON_ID},
          body.nightMode #{_TOP_TOOLBAR_SIDEBAR_ICON_ID} {{
            filter:brightness(0) invert(1);
          }}
          body.fancy #{_TOP_TOOLBAR_SIDEBAR_ID}.sp-sidebar-toggle {{
            background:transparent !important; border-color:transparent !important;
          }}
        </style>
        """
        links.insert(0, style + link)
    except Exception as e:
        print(f"SynapsePro: could not add sidebar toolbar button: {e}")

# --- State Change Notification (Show/Hide Sidebar) ---
def on_state_change(new_state: str, old_state: str):
    global launcher_dock_widget
    _sync_toolbar_review_class(new_state)

    # Remember when a review session starts — Anki's congrats screen gets a
    # session summary (cards, time, XP) injected afterwards.
    if new_state == "review" and old_state != "review":
        try:
            import time as _time
            mw._sp_session_start_ms = int(_time.time() * 1000)
        except Exception:
            pass

    # Leaving the review: if Anki lands on the congrats page ("Congratulations!
    # You have finished this deck for now."), add the session summary to it.
    # The injected JS verifies the page itself, so these speculative calls are
    # harmless when a different screen is shown. Two attempts cover slow loads.
    if old_state == "review" and new_state != "review":
        # Reviews change every dashboard metric. Refresh the streak once here
        # (and persist it for same-day restarts), then let the next dashboard
        # render reuse that value instead of scanning the full revlog again.
        try:
            statistics_widget.invalidate_statistics_cache()
        except Exception:
            pass
        try:
            if gamification_manager:
                gamification_manager.invalidate_dashboard_cache()
                gamification_manager.refresh_streak_cache(persist=True)
        except Exception as e:
            print(f"SynapsePro: dashboard cache refresh failed: {e}")
        try:
            mw.progress.single_shot(450, deck_overview.inject_session_summary_into_congrats)
            mw.progress.single_shot(1400, deck_overview.inject_session_summary_into_congrats)
        except Exception:
            pass
    if not launcher_dock_widget:
        return
    
    try:
        mode = addon_settings.get("sidebar_visibility_mode", "always_show")
        
        if mode == "hide_review":
            if new_state == "review":
                launcher_dock_widget.setVisible(False)
            else:
                launcher_dock_widget.setVisible(True)
        _sync_launcher_toolbar_button()

    except RuntimeError:
        pass

# --- Startup & Logic ---
def _apply_onboarding_result(result: dict):
    """
    Apply language, colour theme, and fact-category from the onboarding
    payload directly to addon_settings (and to the live module globals),
    then persist to disk.

    result keys (all optional / have safe defaults):
        lang        – e.g. "de", "en", "ko"
        themeNumber – 1-based int matching THEME_INDEX_TO_NAME in onboarding_dialog
        roleKey     – "medical" | "law" | "language" | "highschool" | "programmer" | "other"
        source      – consented onboarding analytics key
    """
    if not result:
        return

    # ── Language ──────────────────────────────────────────────────────────────
    valid_langs = {"auto", "en", "de", "es", "ko", "pt", "fr", "vi", "zh", "hi"}
    lang = result.get("lang", "en")
    if lang not in valid_langs:
        lang = "en"
    addon_settings["language"] = lang
    locales.USER_LANG = lang

    # ── Colour theme ──────────────────────────────────────────────────────────
    try:
        theme_num = int(result.get("themeNumber", 1))
    except (ValueError, TypeError):
        theme_num = 1
    theme_name = onboarding_dialog.THEME_INDEX_TO_NAME.get(theme_num, "ocean")
    addon_settings["active_color_theme"] = theme_name
    try:
        from .theme import set_active_theme
        set_active_theme(theme_name)
    except Exception as e:
        print(f"SynapsePro Onboarding: could not apply theme '{theme_name}': {e}")

    # ── Fact category (driven by user role) ───────────────────────────────────
    role_key = result.get("roleKey", "other")
    fact_theme = onboarding_dialog.ROLE_TO_FACT_THEME.get(role_key, "General")
    addon_settings["fact_theme"] = fact_theme

    # Keep the selected discovery source locally as part of the onboarding
    # result, matching the consent screen shown before completion.
    source_key = result.get("source", "other")
    if not isinstance(source_key, str) or len(source_key) > 80:
        source_key = "other"
    addon_settings["onboarding_source"] = source_key

    save_addon_settings()
    print(f"SynapsePro Onboarding: applied — lang={lang}, theme={theme_name}, "
          f"fact_theme={fact_theme}, role={role_key}")

    # Consented onboarding analytics → Supabase. This is fire-and-forget and
    # can never block setup or fail add-on initialisation when offline.
    def _send_onboarding_analytics():
        try:
            import json as _json
            import ssl
            import urllib.request
            from .analytics_config import (
                SUPABASE_ONBOARDING_URL,
                SUPABASE_PUBLIC_ANON_KEY,
            )

            payload = _json.dumps({
                "lang": lang,
                "role": role_key,
                "source": source_key,
                "theme_number": str(theme_num),
                "addon_version": getattr(constants, "ADDON_VERSION", "unknown"),
                "anki_version": getattr(anki, "version", "unknown"),
            }).encode("utf-8")
            request = urllib.request.Request(
                SUPABASE_ONBOARDING_URL,
                data=payload,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "apikey": SUPABASE_PUBLIC_ANON_KEY,
                    "Authorization": f"Bearer {SUPABASE_PUBLIC_ANON_KEY}",
                    "Prefer": "return=minimal",
                },
            )
            with urllib.request.urlopen(
                request, context=ssl.create_default_context(), timeout=8
            ) as response:
                print(f"SynapsePro Onboarding analytics: sent (HTTP {response.status})")
        except Exception as exc:
            print(f"SynapsePro Onboarding analytics: unavailable — {exc}")

    import threading
    threading.Thread(target=_send_onboarding_analytics, daemon=True).start()


def _refresh_ui_after_onboarding():
    """
    Refresh all visible UI components after onboarding applies its settings.
    Called via single_shot so it runs after the dialog has fully closed
    and the event loop is clean.
    """
    # Sidebar icon strip
    if sidebar_widget_instance:
        try:
            sidebar_widget_instance.apply_stylesheet()
        except Exception:
            pass

    # Gamification sidebar
    if gamification_sidebar:
        try:
            gamification_sidebar.refresh_style()
        except Exception:
            pass

    # Website sidebar button colours
    try:
        from .website_sidebar import refresh_website_theme
        refresh_website_theme()
    except Exception:
        pass

    # Refresh the already-open AI Assistant without reloading the chat. This
    # keeps its accent token in sync with the selected SynapsePro colour theme.
    try:
        from .ai_assistant import refresh_ai_assistant_theme
        refresh_ai_assistant_theme()
    except Exception:
        pass

    # Deck browser — re-renders all widgets (fact, gamification, deadline…)
    if mw and mw.state == "deckBrowser":
        try:
            mw.deckBrowser.refresh()
        except Exception:
            pass
    elif mw:
        try:
            mw.reset()
        except Exception:
            pass


def run_onboarding_if_needed():
    if not addon_settings.get("onboarding_completed", False) and hasattr(onboarding_dialog, 'OnboardingWizard'):
        wizard = onboarding_dialog.OnboardingWizard(addon_path, mw)
        if wizard.exec():
            # Apply the user's language / theme / role selections directly.
            # We do NOT open the settings dialog afterwards — the onboarding
            # already collected everything the user needs to configure.
            _apply_onboarding_result(wizard.get_result())
            # Refresh all visible UI so theme + language take effect immediately.
            if mw:
                mw.progress.single_shot(150, _refresh_ui_after_onboarding)
            addon_settings["onboarding_completed"] = True
            save_addon_settings()
            tooltip(_("SynapsePro is ready!"))

def _apply_saved_settings(new_settings):
    """Persist the returned settings and refresh every affected piece of UI.
    Shared by the HTML settings dialog and the native fallback."""
    addon_settings.update(new_settings); save_addon_settings()

    # Enabling the compact dashboard may require plan/deadline managers even
    # when their large legacy widgets are switched off.
    _init_data_managers()

    # Shortcuts are lightweight QShortcut objects and can be replaced live;
    # no restart is needed after changing only their assignments.
    try:
        sidebar_shortcuts.refresh(addon_settings)
    except Exception as e:
        print(f"SynapsePro: shortcut refresh failed: {e}")

    # Regenerate the custom solid background CSS if it is (still) selected,
    # so colour changes take effect on the next webview render.
    if addon_settings.get("active_theme") == "custom_solid.css":
        write_custom_solid_css()

    # Apply new language setting live so subsequent UI uses it immediately.
    locales.USER_LANG = addon_settings.get("language", "auto")
    # Apply colour theme immediately so all widgets reflect the change.
    try:
        from .theme import set_active_theme, set_custom_theme_colors
        _theme_name = addon_settings.get("active_color_theme", "ocean")
        if _theme_name == "custom":
            set_custom_theme_colors(addon_settings.get("custom_theme_colors", {}))
        set_active_theme(_theme_name)
    except Exception:
        pass

    # Refresh the launcher sidebar (always-visible icon bar on the side).
    if sidebar_widget_instance:
        try:
            sidebar_widget_instance.apply_stylesheet()
        except Exception:
            pass

    # Refresh the gamification sidebar in-place (always-visible Qt widget).
    if gamification_sidebar:
        try:
            gamification_sidebar.refresh_style()
        except Exception:
            pass

    # Refresh website sidebar button colours.
    try:
        from .website_sidebar import refresh_website_theme
        refresh_website_theme()
    except Exception:
        pass

    # Keep the open AI Assistant in sync with the newly selected colour theme
    # without reloading it or clearing the conversation.
    try:
        from .ai_assistant import refresh_ai_assistant_theme
        refresh_ai_assistant_theme()
    except Exception:
        pass

    # Refresh music player dialog colour (if open).
    try:
        from .background_music import refresh_music_player_theme
        refresh_music_player_theme()
    except Exception:
        pass

    deck_overview.update_settings(addon_settings)

    if mw:
        on_state_change(mw.state, mw.state)

    # Redraw the top toolbar so a changed background style applies immediately.
    # (Its HTML is only rendered on demand, unlike the bottom bar.)
    _schedule_top_toolbar_redraw(0)
    _sync_webview_bg_colors()

    if mw.state == "deckBrowser": mw.deckBrowser.refresh()
    if mw.state == "overview": mw.reset()
    tooltip(_("Settings saved."))


def _redraw_top_toolbar():
    """Re-render the top toolbar webview so our theme CSS gets (re)injected.

    Anki draws the top toolbar once very early during startup — BEFORE this
    add-on has loaded its settings in on_profile_open. At that point the CSS
    injector still falls back to the default theme, so a user-selected
    background (e.g. a solid colour) never reaches the top toolbar. Redrawing
    after settings are available fixes that; the bottom bar doesn't need it
    because it is redrawn on every state change anyway.
    """
    try:
        if not mw:
            return
        from . import embedded_window
        if embedded_window.is_active():
            return
        toolbar = getattr(mw, "toolbar", None)
        if toolbar is not None:
            # Normal theme refreshes must not touch QWidget min/max heights.
            # embedded_window.restore() owns the exceptional geometry-repair
            # path; a regular toolbar draw lets Anki keep its native sizing.
            toolbar.draw()
    except Exception as e:
        print(f"SynapsePro: top toolbar redraw failed: {e}")


def _schedule_top_toolbar_redraw(delay_ms: int = 0) -> None:
    """Debounce toolbar redraw requests into one generation-safe operation."""
    global _top_toolbar_redraw_generation
    _top_toolbar_redraw_generation += 1
    generation = _top_toolbar_redraw_generation

    def run_if_current() -> None:
        if generation == _top_toolbar_redraw_generation:
            _redraw_top_toolbar()

    try:
        QTimer.singleShot(max(0, int(delay_ms)), run_if_current)
    except Exception:
        run_if_current()


def _get_theme_bg_hex(night: bool) -> str:
    """Best-effort background colour of the active theme for Qt surfaces.

    Solid themes declare a plain hex on body.deckbrowser; gradient themes
    fall back to the gradient's edge grey so any exposed strip blends in.
    """
    fallback = "#2b2b2b" if night else "#f5f5f5"
    try:
        import re
        css_file = addon_settings.get("active_theme", "medical_theme.css")
        if "/" in css_file or "\\" in css_file:
            return fallback
        path = os.path.join(addon_path, "theme", "user_files", css_file)
        if not os.path.exists(path):
            return fallback
        with open(path, "r", encoding="utf-8") as f:
            css = f.read()
        sel = r"body\.nightMode\.deckbrowser" if night else r"body\.deckbrowser"
        m = re.search(sel + r"[^{]*\{[^}]*?background:\s*(#[0-9a-fA-F]{6})", css)
        if m:
            return m.group(1)
    except Exception:
        pass
    return fallback


def _sync_webview_bg_colors():
    """Match the Qt-level backgrounds to the active theme.

    The main screen and the bottom button bar are two separate web views. At
    certain window sizes / fractional display scaling a ~1px seam between
    them can show through as a dark line (the unpainted native background
    behind the pages). Painting the pages' native background colour AND the
    central widget in the theme colour makes any such seam invisible.
    """
    try:
        if not mw or not addon_settings.get("theme_enabled", True):
            return
        from aqt.qt import QColor
        night = False
        try:
            night = bool(mw.pm.night_mode())
        except Exception:
            pass
        qc = QColor(_get_theme_bg_hex(night))
        if not qc.isValid():
            return
        for wv in (getattr(mw, "web", None), getattr(mw, "bottomWeb", None)):
            try:
                if wv is not None and wv.page() is not None:
                    wv.page().setBackgroundColor(qc)
            except Exception:
                pass
        try:
            cw = mw.centralWidget()
            if cw is not None:
                pal = cw.palette()
                pal.setColor(cw.backgroundRole(), qc)
                cw.setPalette(pal)
                cw.setAutoFillBackground(True)
        except Exception:
            pass
    except Exception as e:
        print(f"SynapsePro: webview bg sync failed: {e}")


def show_settings_dialog():
    try:
        dlg = None
        # Preferred: the modern HTML settings UI. Falls back to the native
        # Qt dialog if WebEngine isn't available.
        try:
            from . import web_settings_dialog
            cand = web_settings_dialog.WebSettingsDialog(addon_settings, mw)
            if cand.is_available():
                dlg = cand
        except Exception as e:
            print(f"SynapsePro: HTML settings unavailable ({e}); using native dialog.")

        if dlg is None:
            from . import settings_dialog
            dlg = settings_dialog.SettingsDialog(addon_settings, mw)

        if dlg.exec():
            _apply_saved_settings(dlg.get_new_settings())
    except Exception:
        traceback.print_exc()

def _ensure_gamification_sidebar():
    """Create the Chromium-backed sidebar only when the user opens it."""
    global gamification_sidebar
    if gamification_sidebar:
        return gamification_sidebar
    if (not mw or not gamification_manager
            or not (addon_settings.get("gamification_sidebar_enabled", True)
                    or addon_settings.get("minimal_dashboard_enabled", False))):
        return None
    try:
        sidebar = GamificationSidebar(manager=gamification_manager, parent=mw)
        # Keep it hidden while it is attached. It becomes visible below only in
        # direct response to the user's click, never during Anki startup.
        sidebar.setVisible(False)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, sidebar)
        gamification_sidebar = sidebar
        mw.gamification_sidebar = sidebar
        return sidebar
    except Exception as e:
        print(f"SynapsePro: could not create gamification sidebar: {e}")
        traceback.print_exc()
        return None


def toggle_gamification_sidebar():
    sidebar = _ensure_gamification_sidebar()
    if sidebar:
        if sidebar.isVisible():
            sidebar.hide()
        else:
            sidebar.update_display()
            sidebar.show()
            sidebar.raise_()

def show_configuration_dialog():
    try:
        if LearningPlanConfigDialog(study_plan_config_json_path, mw).exec():
            if learning_plan_manager: learning_plan_manager._initialize_status_for_today()
            if mw.state == "deckBrowser": mw.deckBrowser.refresh()
    except Exception as e: print(f"SynapsePro: configuration dialog error: {e}")

# --- Theme Change Notification ---
def on_theme_changed():
    _sync_webview_bg_colors()
    try:
        from .ai_assistant import refresh_ai_assistant_theme
        refresh_ai_assistant_theme()
    except Exception:
        pass
    if mw: mw.progress.single_shot(500, mode.show_restart_warning)


def on_sync_finished(*_args) -> None:
    """Invalidate dashboard snapshots after reviews arrive through AnkiWeb."""
    try:
        statistics_widget.invalidate_statistics_cache()
    except Exception:
        pass
    try:
        if gamification_manager:
            gamification_manager.invalidate_dashboard_cache()
            gamification_manager.refresh_streak_cache(persist=True)
    except Exception as e:
        print(f"SynapsePro: post-sync dashboard refresh failed: {e}")


def _init_data_managers() -> None:
    """Create lightweight dashboard models before Anki's first page render.

    This deliberately does not create any QWebEngineView. It prepares the small
    data models and bounded daily maintenance so the first Deck Browser HTML
    already has its final structure and values.
    """
    global gamification_manager, learning_plan_manager, deadline_manager
    global _daily_maintenance_done
    if not mw or not getattr(mw, "col", None):
        return

    try:
        deck_overview.init_deck_overview()
        deck_overview.update_settings(addon_settings)
    except Exception as e:
        print(f"SynapsePro: deck overview initialization failed: {e}")

    if not gamification_manager:
        try:
            gamification_manager = GamificationManager(
                addon_path=constants.addon_path)
            mw.gamification_manager = gamification_manager
        except Exception as e:
            print(f"SynapsePro: gamification manager initialization failed: {e}")
            traceback.print_exc()

    minimal_dashboard_enabled = addon_settings.get("minimal_dashboard_enabled", False)

    if (minimal_dashboard_enabled or addon_settings.get("deadline_bar_enabled", True)) and not deadline_manager:
        try:
            deadline_manager = DeadlineManager()
            mw.deadline_manager = deadline_manager
        except Exception as e:
            print(f"SynapsePro: deadline manager initialization failed: {e}")

    if (minimal_dashboard_enabled or addon_settings.get("daily_widgets_enabled", True)) and not learning_plan_manager:
        try:
            learning_plan_manager = LearningPlanManager(
                study_plan_config_json_path)
            mw.learning_plan_manager = learning_plan_manager
        except Exception as e:
            print(f"SynapsePro: learning-plan initialization failed: {e}")

    if gamification_manager and not _daily_maintenance_done:
        try:
            # The streak query is bounded to recent history and all manager
            # state is now ready. Completing maintenance here means the first
            # dashboard render is final and needs no corrective second paint.
            gamification_manager.check_and_update_streak_and_time_xp()
            _daily_maintenance_done = True
        except Exception as e:
            print(f"SynapsePro: daily gamification maintenance failed: {e}")


def _init_launcher_dock() -> None:
    """Install the lightweight 55px launcher before the first dashboard paint."""
    global launcher_dock_widget, sidebar_widget_instance
    if not mw or launcher_dock_widget:
        return

    try:
        # The launcher buttons may be clicked immediately after they appear.
        study_plan_trigger.set_gamification_sidebar_trigger_function(
            toggle_gamification_sidebar)
        study_plan_trigger.set_study_plan_trigger_function(
            show_configuration_dialog)

        launcher_dock_name = "MobesaLauncherSidebarDock_v2"
        existing = mw.findChild(QDockWidget, launcher_dock_name)
        if existing:
            existing.setVisible(False)
            existing.deleteLater()

        dock = QDockWidget("", mw)
        dock.setObjectName(launcher_dock_name)
        content = SidebarWidget(
            parent=dock,
            settings_dialog_trigger=show_settings_dialog,
            settings=addon_settings,
        )
        dock.setWidget(content)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.setTitleBarWidget(QWidget())
        dock.setFixedWidth(constants.SIDEBAR_WIDTH)
        mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        launcher_dock_widget = dock
        sidebar_widget_instance = content
        if addon_settings.get("pomodoro_enabled", True):
            init_pomodoro(
                mw,
                content.update_timer_ui,
                content.update_timer_label_only,
            )
        try:
            dock.visibilityChanged.connect(_sync_launcher_toolbar_button)
        except (AttributeError, RuntimeError):
            pass

        on_state_change(mw.state, "")
        try:
            sidebar_shortcuts.refresh(addon_settings)
        except Exception as e:
            print(f"SynapsePro: shortcut setup failed: {e}")
    except Exception as e:
        print(f"SynapsePro: launcher initialization failed: {e}")
        traceback.print_exc()


def on_profile_open():
    global study_plan_config_json_path, addon_settings_path
    global _dashboard_rendered_with_models, _daily_maintenance_done, _profile_generation

    _profile_generation += 1
    profile_generation = _profile_generation

    try:
        profile_folder = mw.pm.profileFolder()
        data_folder = os.path.join(profile_folder, "SynapsePro_Data")
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)

        new_settings_path = os.path.join(data_folder, "addon_settings.json")
        new_plan_path = os.path.join(data_folder, "study_plan_config.json")

        old_settings = os.path.join(addon_path, "addon_settings.json")
        if os.path.exists(old_settings) and not os.path.exists(new_settings_path):
            try:
                shutil.move(old_settings, new_settings_path)
                print("SynapsePro: Migrated settings to profile folder.")
            except Exception as e: print(f"SynapsePro Migration Error (Settings): {e}")

        old_plan = os.path.join(addon_path, "study_plan_config.json")
        if os.path.exists(old_plan) and not os.path.exists(new_plan_path):
            try:
                shutil.move(old_plan, new_plan_path)
                print("SynapsePro: Migrated study plan to profile folder.")
            except Exception as e: print(f"SynapsePro Migration Error (Plan): {e}")

        addon_settings_path = new_settings_path
        study_plan_config_json_path = new_plan_path

    except Exception as e:
        print(f"SynapsePro: Error determining profile path: {e}")

    load_addon_settings()
    # Make sure the custom solid background file exists if it is selected
    # (e.g. after an add-on update wiped generated files).
    if addon_settings.get("active_theme") == "custom_solid.css":
        write_custom_solid_css()
    # Apply language preference from the loaded settings so every later _()
    # call (menus, tooltips, dialogs) uses the correct language.
    locales.USER_LANG = addon_settings.get("language", "auto")
    # Apply colour theme so all subsequent palette() calls use the right tokens.
    try:
        from .theme import set_active_theme, set_custom_theme_colors
        theme_name = addon_settings.get("active_color_theme", "ocean")
        if theme_name == "custom":
            set_custom_theme_colors(addon_settings.get("custom_theme_colors", {}))
        set_active_theme(theme_name)
    except Exception:
        pass
    _dashboard_rendered_with_models = False
    _daily_maintenance_done = False
    try:
        statistics_widget.invalidate_statistics_cache()
    except Exception:
        pass
    if mw:
        mw.progress.single_shot(
            200,
            lambda g=profile_generation: (
                run_onboarding_if_needed()
                if g == _profile_generation and getattr(mw, "col", None)
                else None
            ),
        )
        if modules_loaded:
            # Structural/lightweight initialization happens before Anki's first
            # dashboard paint, avoiding the visible 300ms sidebar/widget jump.
            _init_data_managers()
            _init_launcher_dock()
            _sync_webview_bg_colors()
            _schedule_top_toolbar_redraw(0)
            mw.progress.single_shot(
                300, lambda g=profile_generation: _init_ui_delayed(g))

def _init_ui_delayed(expected_profile_generation=None):
    global launcher_dock_widget, sidebar_widget_instance, gamification_manager, learning_plan_manager, deadline_manager
    global study_plan_config_json_path, _daily_maintenance_done
    
    if (not mw or not modules_loaded or not getattr(mw, "col", None)
            or (expected_profile_generation is not None
                and expected_profile_generation != _profile_generation)):
        return

    # Idempotent fallbacks in case an unusual profile-start order prevented the
    # early lightweight phase from completing.
    _init_data_managers()
    _init_launcher_dock()

    daily_state_changed = False
    if gamification_manager and not _daily_maintenance_done:
        try:
            daily_state_changed = bool(
                gamification_manager.check_and_update_streak_and_time_xp())
            _daily_maintenance_done = True
        except Exception as e:
            print(f"SynapsePro: daily gamification maintenance failed: {e}")

    if addon_settings.get("notebook_enabled", True):
        setup_notebook_sidebar()

    if study_plan_trigger:
        study_plan_trigger.set_gamification_sidebar_trigger_function(toggle_gamification_sidebar)
        study_plan_trigger.set_study_plan_trigger_function(show_configuration_dialog)

    # Focus Music: resume playback from the last session (if the user opted in
    # and music was still playing when Anki was closed).
    if addon_settings.get("music_player_enabled", True):
        try:
            from .background_music import maybe_autoresume_music
            current_generation = _profile_generation
            mw.progress.single_shot(
                1500,
                lambda g=current_generation: (
                    maybe_autoresume_music()
                    if g == _profile_generation and getattr(mw, "col", None)
                    else None
                ),
            )
        except Exception as e:
            print(f"SynapsePro: music autoresume error: {e}")

    if (mw.state == "deckBrowser"
            and (daily_state_changed or not _dashboard_rendered_with_models)):
        mw.deckBrowser.refresh()
    

def on_profile_close():
    global launcher_dock_widget, sidebar_widget_instance, gamification_manager, gamification_sidebar, learning_plan_manager, deadline_manager
    global _dashboard_rendered_with_models, _daily_maintenance_done
    global _top_toolbar_redraw_generation, _profile_generation, _synapse_tools_menu
    _profile_generation += 1
    for subject in list(_plan_timers):
        _plan_timer_cancel(subject)
    if gamification_manager: gamification_manager.save_data()
    if deadline_manager: deadline_manager.save_data()

    try:
        sidebar_shortcuts.cleanup()
    except Exception:
        pass
    
    cleanup_pomodoro(); cleanup_website_sidebar()
    cleanup_music_player(); cleanup_ai_assistant_sidebar()
    cleanup_mindmap_sidebar(); cleanup_notebook_sidebar()

    # Docks are children of Anki's persistent main window, not of a profile.
    # Remove them explicitly so profile switches cannot retain old web pages,
    # signals or data-bound widgets until the next profile finishes loading.
    for dock in (gamification_sidebar, launcher_dock_widget):
        if dock:
            try:
                mw.removeDockWidget(dock)
                dock.deleteLater()
            except (RuntimeError, AttributeError):
                pass
    gamification_manager = None; gamification_sidebar = None
    learning_plan_manager = None; deadline_manager = None
    sidebar_widget_instance = None; launcher_dock_widget = None
    _dashboard_rendered_with_models = False
    _daily_maintenance_done = False
    _top_toolbar_redraw_generation += 1
    try:
        statistics_widget.invalidate_statistics_cache()
    except Exception:
        pass
    if _synapse_tools_menu is not None:
        try: mw.form.menuTools.removeAction(_synapse_tools_menu.menuAction())
        except Exception: pass
        _synapse_tools_menu = None
    
    for attr in ["gamification_manager", "deadline_manager", "learning_plan_manager", "daily_widgets", "gamification_sidebar"]:
        if hasattr(mw, attr): delattr(mw, attr)

# --- Webview & Rendering Hooks ---
def render_all_deck_browser_widgets(deck_browser: DeckBrowser, content: DeckBrowserContent):
    global _dashboard_rendered_with_models
    minimal_enabled = bool(addon_settings.get("minimal_dashboard_enabled", False))
    if (not minimal_enabled
            and not addon_settings.get("statistics_widget_enabled", True)
            and not addon_settings.get("gamification_widgets_enabled", True)
            and not addon_settings.get("daily_widgets_enabled", True)
            and not addon_settings.get("deadline_bar_enabled", True)):
        _dashboard_rendered_with_models = True
        return
    
    stats_html = gamification_html = daily_html = deadline_html = compact_html = compact_stats_html = ""
    gm = getattr(mw, 'gamification_manager', None)
    lpm = getattr(mw, 'learning_plan_manager', None)
    dm = getattr(mw, 'deadline_manager', None)
    if minimal_enabled:
        _dashboard_rendered_with_models = bool(gm and lpm and dm)
        try:
            fact_theme = addon_settings.get("fact_theme", "Medical")
            fact_html = daily_widgets.generate_fact_widget(fact_theme)
            compact_html, compact_stats_html = minimal_dashboard.render_minimal_dashboard_sections(
                gm, lpm, dm, int(addon_settings.get("stats_time_range", 7)),
                fact_theme, fact_html,
            )
        except Exception as e:
            print(f"SynapsePro: minimal dashboard render error: {e}")
    else:
        _dashboard_rendered_with_models = bool(
            (not addon_settings.get("gamification_widgets_enabled", True) or gm)
            and (not addon_settings.get("daily_widgets_enabled", True) or lpm)
            and (not addon_settings.get("deadline_bar_enabled", True) or dm)
        )

        if addon_settings.get("statistics_widget_enabled", True):
            try: stats_html = statistics_widget.render_statistics_widget_html(stats_days=int(addon_settings.get("stats_time_range", 7)))
            except Exception as e: print(f"SynapsePro: stats widget render error: {e}")
        if addon_settings.get("gamification_widgets_enabled", True) and gm:
            try: gamification_html = gm.render_widgets_html()
            except Exception as e: print(f"SynapsePro: gamification widget render error: {e}")
        if addon_settings.get("daily_widgets_enabled", True) and lpm:
            try: daily_html = daily_widgets.generate_daily_widgets_html(lpm.get_plan_for_display(), addon_settings.get("fact_theme", "Medical"))
            except Exception as e: print(f"SynapsePro: daily widget render error: {e}")
        if addon_settings.get("deadline_bar_enabled", True) and dm:
            try: deadline_html = dm.render_deadline_bar_html()
            except Exception as e: print(f"SynapsePro: deadline bar render error: {e}")
    
    # Celebration popup (rank-up / level-up / challenge) — deck browser only,
    # so it can never interrupt a review session. Events are consumed from the
    # manager even while popups are disabled, so re-enabling them later
    # doesn't replay old events.
    celebrate_html = ""
    try:
        gm = getattr(mw, 'gamification_manager', None)
        if gm:
            events = gm.get_celebration_events()
            if events and addon_settings.get("gamification_popups_enabled", True):
                from . import gamification_popup
                celebrate_html = gamification_popup.render_celebration_modal(events)
    except Exception as e:
        print(f"SynapsePro: celebration popup error: {e}")

    content.stats = compact_stats_html + stats_html + celebrate_html + getattr(content, 'stats', '')
    content.tree = compact_html + gamification_html + daily_html + deadline_html + getattr(content, 'tree', '')

# --- Study-plan countdown timers ------------------------------------------------
# Fire a "time's up" notification when a subject's timer runs out — even while the
# user is reviewing cards (the deck-browser JS timer is not running then).
_plan_timers: Dict[str, Any] = {}

def _plan_timer_cancel(subject: str):
    t = _plan_timers.pop(subject, None)
    if t is not None:
        try: t.stop(); t.deleteLater()
        except Exception: pass

def _plan_timer_fire(subject: str):
    _plan_timers.pop(subject, None)
    try: tooltip(_("Time's up — finished studying: %s") % subject, period=6000)
    except Exception as e: print(f"SynapsePro plan timer notify error: {e}")

def _plan_timer_start(subject: str, end_ms: int):
    _plan_timer_cancel(subject)
    if QTimer is None or QTimer is object or mw is None: return
    import time as _time
    delay = max(0, min(86400000, int(end_ms - _time.time() * 1000)))
    try:
        t = QTimer(mw); t.setSingleShot(True)
        t.timeout.connect(lambda s=subject: _plan_timer_fire(s))
        t.start(delay)
        _plan_timers[subject] = t
    except Exception as e:
        print(f"SynapsePro plan timer start error: {e}")

def _handle_plan_timer(cmd: str):
    import urllib.parse as _up
    parts = cmd.split(":", 3)  # ["planTimer", action, ...]
    action = parts[1] if len(parts) > 1 else ""
    if action == "start" and len(parts) >= 4:
        _plan_timer_start(_up.unquote(parts[3]), int(parts[2]))
    elif action == "cancel" and len(parts) >= 3:
        _plan_timer_cancel(_up.unquote(parts[2]))

def webview_did_receive_js_message(handled: bool, message: str, context: object) -> Union[bool, object]:
    if not isinstance(message, str) or not message.startswith("pycmd:"): return handled
    # These commands are emitted exclusively by widgets injected into the deck
    # browser.  Reject the same strings from reviewer/card/add-on WebViews.
    if not isinstance(context, DeckBrowser):
        return handled
    cmd = message[6:]
    if cmd.startswith("planTimer:"):
        try: _handle_plan_timer(cmd)
        except Exception as e: print(f"SynapsePro plan timer error: {e}")
        return (True, None)
    if cmd == CMD_RESET_DATA:
        gm = getattr(mw, 'gamification_manager', None)
        if gm and gm.reset_all_data() and gamification_sidebar: gamification_sidebar.update_display()
        return (True, None)
    if cmd == CMD_CLAIM_CHALLENGE:
        gm = getattr(mw, 'gamification_manager', None)
        if gm:
            try:
                gm.on_complete_challenge()
                if gamification_sidebar:
                    gamification_sidebar.update_display()
            except Exception as e:
                print(f"SynapsePro: claim challenge error: {e}")
        return (True, None)
    # ── Multi-deadline navigation & viewer ───────────────────────────────
    if cmd in ("synapsepro:deadline_next", "synapsepro:deadline_viewer", "synapsepro:deadline_settings"):
        dm = getattr(mw, 'deadline_manager', None)
        if cmd == "synapsepro:deadline_next":
            if dm:
                dm.cycle_deadline(+1)
                if mw.state == "deckBrowser":
                    mw.deckBrowser.refresh()
        elif cmd == "synapsepro:deadline_viewer":
            try:
                DeadlineViewerDialog(dm, parent=mw).exec()
            except Exception as e:
                print(f"SynapsePro: DeadlineViewerDialog error: {e}")
            if mw.state == "deckBrowser":
                mw.deckBrowser.refresh()
        elif cmd == "synapsepro:deadline_settings":
            try:
                DeadlineConfigDialog(dm, parent=mw).exec()
            except Exception as e:
                print(f"SynapsePro: DeadlineConfigDialog error: {e}")
            if mw.state == "deckBrowser":
                mw.deckBrowser.refresh()
        return (True, None)
    if cmd == "synapsepro:study_plan_viewer":
        lpm = getattr(mw, 'learning_plan_manager', None)
        try:
            StudyPlanViewerDialog(lpm, study_plan_config_json_path, parent=mw).exec()
        except Exception as e:
            print(f"SynapsePro: StudyPlanViewerDialog error: {e}")
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        return (True, None)
    if cmd == "synapsepro:gamification_viewer":
        toggle_gamification_sidebar()
        return (True, None)
    # Info button ("i") in the statistics widget — explains every statistic.
    if cmd == "synapsepro:stats_info":
        try:
            statistics_widget.show_statistics_info_dialog(
                parent=mw, stats_days=int(addon_settings.get("stats_time_range", 7)))
        except Exception as e:
            print(f"SynapsePro: statistics info dialog error: {e}")
        return (True, None)
    # "Don't show again" checkbox in the gamification celebration popup.
    if cmd == "synapsepro:celebrate_optout:1":
        addon_settings["gamification_popups_enabled"] = False
        save_addon_settings()
        return (True, None)
    return handled

# --- Theme Injection (Dynamic) ---
def inject_theme_assets(web_content: WebContent, context: Optional[Any]):
    if not addon_settings.get("theme_enabled", True): return
    
    try:
        addon_pkg = mw.addonManager.addonFromModule(__name__)
        if not addon_pkg: return
        
        css_file = addon_settings.get("active_theme", "medical_theme.css")
        
        if "/" in css_file or "\\" in css_file: 
            css_file = "medical_theme.css"
        
        local_path = os.path.join(addon_path, 'theme', 'user_files', css_file)
        
        if not os.path.exists(local_path):
            local_path = os.path.join(addon_path, 'theme', 'user_files', 'medical_theme.css')
            css_file = "medical_theme.css"

        if os.path.exists(local_path):
            web_content.css.append(f"/_addons/{addon_pkg}/theme/user_files/{css_file}?v={int(os.path.getmtime(local_path))}")
            if isinstance(context, DeckBrowser):
                dashboard_class = (
                    ",'synapse-minimal-dashboard'"
                    if addon_settings.get("minimal_dashboard_enabled", False)
                    else ""
                )
                # Prepend so the width-mode class is present before the deck
                # table is parsed and no 860px -> native-width jump is painted.
                web_content.body = (
                    f"<script>document.body.classList.add('deckbrowser'{dashboard_class});</script>"
                    + web_content.body
                )
            elif isinstance(context, Overview): web_content.body += "<script>document.body.classList.add('overview');</script>"
            elif isinstance(context, TopToolbar): web_content.body += "<script>document.body.classList.add('top-toolbar');</script>"
            elif isinstance(context, ReviewerBottomBar):
                # 'reviewing' lets solid themes revert this bar to Anki's default
                web_content.body += "<script>document.body.classList.add('bottom-toolbar','reviewing');</script>"
            elif isinstance(context, (DeckBrowserBottomBar, OverviewBottomBar)):
                web_content.body += "<script>document.body.classList.add('bottom-toolbar');</script>"
            # Fallback: some Anki versions pass different context objects for the
            # toolbars, so ALSO detect them from their DOM structure. Inert on
            # every other page.
            web_content.body += (
                "<script>(function(){try{var b=document.body;"
                "if(document.querySelector('.header a#decks, #header a#decks'))"
                "b.classList.add('top-toolbar');"
                "if(document.getElementById('outer')&&!b.classList.contains('deckbrowser')"
                "&&!b.classList.contains('overview'))b.classList.add('bottom-toolbar');"
                "}catch(e){}})();</script>"
            )

    except Exception as e: print(f"SynapsePro: CSS injection error: {e}")

_synapse_tools_menu = None

def _add_menus():
    global _synapse_tools_menu
    if not mw or not hasattr(mw, 'form'): return
    # This hook fires on every profile_did_open. mw (and its Tools menu) persist
    # across profile switches, so remove any previously added menu first to
    # avoid a second identical "SynapsePro" entry stacking up.
    if _synapse_tools_menu is not None:
        try:
            mw.form.menuTools.removeAction(_synapse_tools_menu.menuAction())
        except Exception:
            pass
        _synapse_tools_menu = None
    # "SynapsePro" is the brand/product name and is intentionally not translated.
    m = mw.form.menuTools.addMenu("SynapsePro")
    _synapse_tools_menu = m
    m.addAction(_("Settings..."), show_settings_dialog)
    m.addAction(_("Configure Study Plan..."), show_configuration_dialog)
    m.addSeparator()
    m.addAction(_("Toggle Gamification Sidebar"), toggle_gamification_sidebar)

# --- Init Hooks ---
if modules_loaded and mw and gui_hooks:
    gui_hooks.profile_did_open.append(on_profile_open)
    gui_hooks.profile_will_close.append(on_profile_close)
    gui_hooks.deck_browser_will_render_content.append(render_all_deck_browser_widgets)
    gui_hooks.webview_did_receive_js_message.append(webview_did_receive_js_message)
    gui_hooks.profile_did_open.append(_add_menus)
    gui_hooks.state_did_change.append(on_state_change)
    if hasattr(gui_hooks, "top_toolbar_did_init_links"):
        gui_hooks.top_toolbar_did_init_links.append(
            _add_launcher_toggle_to_top_toolbar
        )
    mw.addonManager.setWebExports(__name__, r"(theme/user_files/.+\.css|web_notebook/.+|media/.+)$") # Allow css, notebook AND media files
    gui_hooks.webview_will_set_content.append(inject_theme_assets)
    
    if hasattr(gui_hooks, "theme_did_change"):
        gui_hooks.theme_did_change.append(on_theme_changed)
    if hasattr(gui_hooks, "sync_did_finish"):
        gui_hooks.sync_did_finish.append(on_sync_finished)
    
    print(f"SynapsePro1 loaded.")
