# -*- coding: utf-8 -*-

import os, sys, json, traceback, shutil
from typing import Optional, Union, Any, Dict

# --- Import Sub-Modules ---
try:
    from . import constants, study_plan_trigger, onboarding_dialog, locales
    from .locales import _
except ImportError as e:
    print(f"SynapsePro1 CRITICAL ERROR: {e}")
    constants=object(); study_plan_trigger=object()
    # Safety fallbacks so UI strings and language handling don't NameError
    # if the locales module fails to import.
    def _(text): return text
    class _LocalesStub: USER_LANG = "auto"
    locales = _LocalesStub()

# --- QT Imports Check ---
QDockWidget, QWidget, Qt = object, object, None
if hasattr(constants, 'qt_version'):
    try:
        from PyQt6.QtWidgets import QDockWidget, QWidget; from PyQt6.QtCore import Qt; constants.qt_version = 6
    except ImportError:
        try:
            from PyQt5.QtWidgets import QDockWidget, QWidget; from PyQt5.QtCore import Qt; constants.qt_version = 5
        except ImportError: constants.qt_version = 0
else:
    if not hasattr(constants, 'qt_version'): constants.qt_version = 0

# --- Anki Imports ---
mw, gui_hooks = None, None
try:
    import anki
    from aqt import mw, gui_hooks
    from aqt.utils import showWarning, tooltip
    from aqt.webview import WebContent
    from aqt.deckbrowser import DeckBrowser, DeckBrowserContent, DeckBrowserBottomBar
    from aqt.overview import Overview, OverviewBottomBar
    from aqt.reviewer import ReviewerBottomBar
    from aqt.toolbar import TopToolbar
except ImportError: 
    print(f"SynapsePro1: ERROR - Failed to import Anki modules.")

# --- Sound ---
if hasattr(constants, 'sound_available'): constants.sound_available = False
try:
    if constants.qt_version > 0 and mw: from anki.sound import play; constants.sound_available = True; constants.play_sound_function = play
except ImportError: pass

# --- Load Feature Modules ---
modules_loaded = False
try:
    from . import mode
    from .launcher_widget import SidebarWidget
    from .pomodoro import init_pomodoro, cleanup_pomodoro
    from .website_sidebar import cleanup_website_sidebar
    from .background_music import cleanup_music_player
    from .ai_assistant import cleanup_ai_assistant_sidebar
    from .mindmap_sidebar import cleanup_mindmap_sidebar    
    from .notebook_sidebar import cleanup_notebook_sidebar, setup_notebook_sidebar, toggle_notebook_dock
    from . import deck_overview    
    from . import statistics_widget, daily_widgets, settings_dialog
    from .gamification import GamificationManager, CMD_RESET_DATA, CMD_LP_START_PREFIX, CMD_LP_PAUSE_PREFIX
    from .sidebar import GamificationSidebar
    from .learning_plan import LearningPlanManager
    from .deadline_bar import DeadlineManager
    from .configuration import LearningPlanConfigDialog, DeadlineViewerDialog, DeadlineConfigDialog
    modules_loaded = True
except ImportError as e: 
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
sidebar_widget_instance: Optional[SidebarWidget] = None
gamification_manager: Optional[GamificationManager] = None
gamification_sidebar: Optional[GamificationSidebar] = None
learning_plan_manager: Optional[LearningPlanManager] = None
deadline_manager: Optional[DeadlineManager] = None

# --- Settings Handling ---
def get_default_settings() -> Dict[str, Any]:
    return {
        "onboarding_completed": False,
        "theme_enabled": True,
        "active_theme": "medical_theme.css",
        "fact_theme": "Medical", 
        "sidebar_visibility_mode": "always_show",
        "gamification_widgets_enabled": True, "daily_widgets_enabled": True, 
        "deadline_bar_enabled": True, "statistics_widget_enabled": True,
        "deck_overview_enabled": True,
        "pomodoro_enabled": True, "ai_assistant_enabled": True,
        "website_viewer_enabled": True, "notebook_enabled": True,
        "mindmap_enabled": True, "gamification_sidebar_enabled": True,
        "music_player_enabled": True, "stats_time_range": 7,
        "language": "auto",  # UI language: "auto", "en", "de", "es"
        "active_color_theme": "ocean",   # Colour theme: "ocean","orchid","forest","deluge","horizon","dusty","custom"
        "custom_theme_colors": {},       # Used when active_color_theme == "custom"
    }

def load_addon_settings():
    global addon_settings
    defaults = get_default_settings()
    try:
        with open(addon_settings_path, 'r', encoding='utf-8') as f:
            defaults.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError): pass 
    addon_settings = defaults

def save_addon_settings():
    try:
        with open(addon_settings_path, 'w', encoding='utf-8') as f:
            json.dump(addon_settings, f, indent=4)
    except Exception as e: print(f"SynapsePro1 ERROR: Save settings: {e}")

# --- State Change Notification (Show/Hide Sidebar) ---
def on_state_change(new_state: str, old_state: str):
    global launcher_dock_widget
    if not launcher_dock_widget: 
        return
    
    try:
        mode = addon_settings.get("sidebar_visibility_mode", "always_show")
        
        if mode == "hide_review":
            if new_state == "review":
                launcher_dock_widget.setVisible(False)
            else:
                launcher_dock_widget.setVisible(True)
                
        
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
        source      – analytics key (stored but not acted upon yet)
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

    # ── Source (saved for later analytics, no immediate action) ───────────────
    if result.get("source"):
        addon_settings["onboarding_source"] = result["source"]

    save_addon_settings()
    print(f"SynapsePro Onboarding: applied — lang={lang}, theme={theme_name}, "
          f"fact_theme={fact_theme}, role={role_key}")

    # ── Anonymous telemetry → Supabase (fire-and-forget, background thread) ──
    def _send_to_supabase():
        try:
            import urllib.request, json as _json, ssl
            from . import _secrets
            url = _secrets.SUPABASE_URL
            try:
                _anki_version = getattr(anki, 'version', "unknown")
            except Exception:
                _anki_version = "unknown"
            try:
                import json as _mj
                _manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
                with open(_manifest_path, encoding="utf-8") as _mf:
                    _addon_version = _mj.load(_mf).get("version", "unknown")
            except Exception:
                _addon_version = "unknown"
            payload = _json.dumps({
                "lang":          lang,
                "role":          role_key,
                "source":        result.get("source", "other"),
                "theme_number":  str(result.get("themeNumber", 1)),
                "addon_version": _addon_version,
                "anki_version":  _anki_version,
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                method="POST",
                headers={
                    "Content-Type":  "application/json",
                    "apikey":        _secrets.SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {_secrets.SUPABASE_ANON_KEY}",
                    "Prefer":        "return=minimal",
                },
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                print(f"SynapsePro Telemetry: sent (HTTP {resp.status})")
        except Exception as e:
            # Never crash Anki over analytics
            print(f"SynapsePro Telemetry: failed silently — {e}")

    import threading
    threading.Thread(target=_send_to_supabase, daemon=True).start()


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

def show_settings_dialog():
    try:
        from . import settings_dialog
        d = settings_dialog.SettingsDialog(addon_settings, mw)
        if d.exec():
            addon_settings.update(d.get_new_settings()); save_addon_settings()

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

            # Refresh music player dialog colour (if open).
            try:
                from .background_music import refresh_music_player_theme
                refresh_music_player_theme()
            except Exception:
                pass

            deck_overview.update_settings(addon_settings)

            if mw:
                on_state_change(mw.state, mw.state)

            if mw.state == "deckBrowser": mw.deckBrowser.refresh()
            if mw.state == "overview": mw.reset()
            tooltip(_("Settings saved."))
    except Exception: traceback.print_exc()

def toggle_gamification_sidebar():
    if gamification_sidebar:
        if gamification_sidebar.isVisible(): gamification_sidebar.hide()
        else: gamification_sidebar.update_display(); gamification_sidebar.show(); gamification_sidebar.raise_()

def show_configuration_dialog():
    try:
        if LearningPlanConfigDialog(study_plan_config_json_path, mw).exec():
            if learning_plan_manager: learning_plan_manager._initialize_status_for_today()
            if mw.state == "deckBrowser": mw.deckBrowser.refresh()
    except Exception as e: print(f"SynapsePro: configuration dialog error: {e}")

# --- Theme Change Notification ---
def on_theme_changed():
    if mw: mw.progress.single_shot(500, mode.show_restart_warning)

def on_profile_open():
    global study_plan_config_json_path, addon_settings_path

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
    if mw:
        mw.progress.single_shot(200, run_onboarding_if_needed)
        if modules_loaded:
            mw.progress.single_shot(300, _init_ui_delayed)

def _init_ui_delayed():
    global launcher_dock_widget, sidebar_widget_instance, gamification_manager, gamification_sidebar, learning_plan_manager, deadline_manager
    global study_plan_config_json_path
    
    if not mw or not modules_loaded: return

    deck_overview.init_deck_overview()

    deck_overview.update_settings(addon_settings)

    # Managers Init
    if not gamification_manager:
        gamification_manager = GamificationManager(addon_path=constants.addon_path)
        mw.gamification_manager = gamification_manager
        gamification_manager.check_and_update_streak_and_time_xp()
    
    if addon_settings.get("deadline_bar_enabled", True) and not deadline_manager:
        deadline_manager = DeadlineManager(); mw.deadline_manager = deadline_manager
        
    if addon_settings.get("daily_widgets_enabled", True) and not learning_plan_manager:
        learning_plan_manager = LearningPlanManager(study_plan_config_json_path); mw.learning_plan_manager = learning_plan_manager

    if addon_settings.get("gamification_sidebar_enabled", True) and not gamification_sidebar and gamification_manager:
        gamification_sidebar = GamificationSidebar(manager=gamification_manager, parent=mw)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, gamification_sidebar)
        gamification_sidebar.setVisible(False)

    if addon_settings.get("notebook_enabled", True):
        setup_notebook_sidebar()

    # Left Sidebar (Launcher)
    launcher_dock_name = "MobesaLauncherSidebarDock_v2"
    existing = mw.findChild(QDockWidget, launcher_dock_name)
    if existing: existing.deleteLater()
    
    launcher_dock_widget = QDockWidget("", mw)
    launcher_dock_widget.setObjectName(launcher_dock_name)
    sidebar_widget_instance = SidebarWidget(parent=launcher_dock_widget, settings_dialog_trigger=show_settings_dialog, settings=addon_settings)
    launcher_dock_widget.setWidget(sidebar_widget_instance)
    launcher_dock_widget.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
    launcher_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
    launcher_dock_widget.setTitleBarWidget(QWidget())
    launcher_dock_widget.setFixedWidth(constants.SIDEBAR_WIDTH)
    mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, launcher_dock_widget)
    
    on_state_change(mw.state, "")

    # Sub-Features Init
    if addon_settings.get("pomodoro_enabled", True): 
        init_pomodoro(mw, sidebar_widget_instance.update_timer_ui, sidebar_widget_instance.update_timer_label_only)
    
    if study_plan_trigger:
        study_plan_trigger.set_gamification_sidebar_trigger_function(toggle_gamification_sidebar)
        study_plan_trigger.set_study_plan_trigger_function(show_configuration_dialog)
        
    if mw.state == "deckBrowser": mw.deckBrowser.refresh()
    

def on_profile_close():
    global launcher_dock_widget, sidebar_widget_instance, gamification_manager, gamification_sidebar, learning_plan_manager, deadline_manager
    if gamification_manager: gamification_manager.save_data()
    if deadline_manager: deadline_manager.save_data()
    
    cleanup_pomodoro(); cleanup_website_sidebar()
    cleanup_music_player(); cleanup_ai_assistant_sidebar()
    cleanup_mindmap_sidebar(); cleanup_notebook_sidebar()
    
    gamification_manager = None; gamification_sidebar = None
    learning_plan_manager = None; deadline_manager = None
    sidebar_widget_instance = None; launcher_dock_widget = None
    
    for attr in ["gamification_manager", "deadline_manager", "learning_plan_manager", "daily_widgets", "gamification_sidebar"]:
        if hasattr(mw, attr): delattr(mw, attr)

# --- Webview & Rendering Hooks ---
def render_all_deck_browser_widgets(deck_browser: DeckBrowser, content: DeckBrowserContent):
    if not addon_settings.get("statistics_widget_enabled", True) and not addon_settings.get("gamification_widgets_enabled", True) and not addon_settings.get("daily_widgets_enabled", True) and not addon_settings.get("deadline_bar_enabled", True): return
    
    stats_html = gamification_html = daily_html = deadline_html = ""
    gm = getattr(mw, 'gamification_manager', None)
    lpm = getattr(mw, 'learning_plan_manager', None)
    dm = getattr(mw, 'deadline_manager', None)

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
    
    content.stats = stats_html + getattr(content, 'stats', '')
    content.tree = gamification_html + daily_html + deadline_html + getattr(content, 'tree', '')

def webview_did_receive_js_message(handled: bool, message: str, context: object) -> Union[bool, object]:
    if not isinstance(message, str) or not message.startswith("pycmd:"): return handled
    cmd = message[6:]
    if cmd == CMD_RESET_DATA:
        gm = getattr(mw, 'gamification_manager', None)
        if gm and gm.reset_all_data() and gamification_sidebar: gamification_sidebar.update_display()
        return True
    # ── Multi-deadline navigation & viewer ───────────────────────────────
    if cmd in ("synapsepro:deadline_next", "synapsepro:deadline_viewer"):
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
            if isinstance(context, DeckBrowser): web_content.body += "<script>document.body.classList.add('deckbrowser');</script>"
            elif isinstance(context, Overview): web_content.body += "<script>document.body.classList.add('overview');</script>"
            elif isinstance(context, TopToolbar): web_content.body += "<script>document.body.classList.add('top-toolbar');</script>"
    except Exception as e: print(f"SynapsePro: CSS injection error: {e}")

def _add_menus():
    if not mw or not hasattr(mw, 'form'): return
    # "SynapsePro" is the brand/product name and is intentionally not translated.
    m = mw.form.menuTools.addMenu("SynapsePro")
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
    mw.addonManager.setWebExports(__name__, r"(theme/user_files/.+\.css|web_notebook/.+|media/.+)$") # Allow css, notebook AND media files
    gui_hooks.webview_will_set_content.append(inject_theme_assets)
    
    if hasattr(gui_hooks, "theme_did_change"):
        gui_hooks.theme_did_change.append(on_theme_changed)
    
    print(f"SynapsePro1 loaded.")