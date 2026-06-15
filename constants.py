# -*- coding: utf-8 -*-

import os

# --- Addon Package Name ---
addon_package_name = "SynapsePro1"
ADDON_DISPLAY_NAME = "SynapsePro"
print(f"Constants: Addon package name set to '{addon_package_name}'.")

ADDON_VERSION = "1.3.0"

# --- Launcher Constants ---
ADDON_NAME_LAUNCHER = "Launcher_Sidebar" 
ICONS_SUBFOLDER = "media" 

# --- URLs ---
AI_ASSISTANT_URL = "https://synapse-pro.vercel.app/"

# --- Colors & Styling (Launcher) ---
# These values are kept for backwards-compatibility with MockConstants fallbacks
# in launcher_widget.py and other modules.  The canonical source of truth is
# now theme.py – do not add new colour constants here.
try:
    from .theme import LIGHT as _TL, DARK as _TD
    SIDEBAR_BG_COLOR_HEX       = _TL["surface"]
    BUTTON_HOVER_PRESSED_COLOR = _TL["blue"]
    BUTTON_ACTIVE_BG_COLOR     = _TL["blue"]
    DEFAULT_TEXT_COLOR         = _TL["text"]
    TIMER_LABEL_COLOR          = _TL["sep_accent"]
    TIMER_BUTTON_HOVER_COLOR   = _TL["grey_mid"]
    TIMER_BUTTON_PRESSED_COLOR = _TL["grey_dark"]
    SEPARATOR_LINE_COLOR       = _TL["sep_accent"]
except Exception:
    # Fallback values when theme.py is not yet available
    SIDEBAR_BG_COLOR_HEX       = "#FFFFFF"
    BUTTON_HOVER_PRESSED_COLOR = "#0071D3"
    BUTTON_ACTIVE_BG_COLOR     = "#0071D3"
    DEFAULT_TEXT_COLOR         = "#1D1D1F"
    TIMER_LABEL_COLOR          = "#888888"
    TIMER_BUTTON_HOVER_COLOR   = "#D0D0D0"
    TIMER_BUTTON_PRESSED_COLOR = "#B0B0B0"
    SEPARATOR_LINE_COLOR       = "#888888"

# --- Sizes & Layout (Launcher) ---
BUTTON_ICON_SIZE = 30
SIDEBAR_WIDTH = 55
BUTTON_BORDER_RADIUS = 8
TIMER_BUTTON_ICON_SIZE = 18
INFO_IMAGE_WIDTH = 200
INFO_IMAGE_FILENAME = "info.png"

# --- Filenames & Object Names (Launcher & Submodules) ---
LOGO_FILENAME = "logo.svg"
MUSIC_ICON_FILENAME = "music.svg"

MINDMAP_DOCK_OBJECT_NAME = "IntegratedMindmapSidebarDock_Mobesa_v1" 
NOTEBOOK_DOCK_OBJECT_NAME = "IntegratedNotebookSidebarDock_Mobesa_v1"
WEBSITE_DOCK_OBJECT_NAME = "IntegratedWebsiteSidebarDock_Mobesa_v1"
AI_ASSISTANT_DOCK_OBJECT_NAME = "AIAssistantSidebarDock_Integrated_v1"
MINDMAP_HTML_FILENAME = "index.html" 

AI_TOOL_ICON_FILENAME = "ai_tool.svg"; WEBSITE_ICON_FILENAME = "website.svg"
NOTEBOOK_ICON_FILENAME = "notes.svg"
MINDMAP_ICON_FILENAME = "mindmap.svg" 
GAME_ICON_FILENAME = "game.svg"
STUDY_PLAN_ICON_FILENAME = "study_plan.svg"; TIMER_ICON_FILENAME = "timer.svg"
START_ICON_FILENAME = "start.svg"; PAUSE_ICON_FILENAME = "pause.svg"
RESET_ICON_FILENAME = "reset.svg"; SKIP_ICON_FILENAME = "skip.svg"

# --- Background Music Constants ---
ADDON_NAME_MUSIC = "Background_Music"
MUSIC_FILES = [ "lofi.mp3", "rain.mp3", "beta_waves.mp3", "alpha_waves.mp3", "classical.mp3", "library_sounds.mp3", "minecraft.mp3", "pokemon.mp3", ]

# --- Pomodoro Constants ---
ADDON_NAME_POMODORO = "Pomodoro_Integrated"
CONFIG_KEY_POMODORO = f"addon_{ADDON_NAME_POMODORO}_config"
CONFIG_KEY_POMODORO_STATS = f"addon_{ADDON_NAME_POMODORO}_stats"
DEFAULT_POMODORO_CONFIG = { "work_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 15, "pomodoros_before_long_break": 4, "sound_work_end": "bells.wav", "sound_break_end": "type.wav", "auto_start_next": False }
DEFAULT_POMODORO_STATS = { "total_pomodoros": 0, "total_focus_minutes": 0, "best_streak": 0, "daily_data": {} }
STATE_IDLE = 0; STATE_WORK = 1; STATE_SHORT_BREAK = 2; STATE_LONG_BREAK = 3; STATE_PAUSED = 4

# --- Website Sidebar Constants ---
ADDON_NAME_WEBSITE = "Website_Sidebar"
CONFIG_KEY_CUSTOM_SITES = f"addon_{ADDON_NAME_LAUNCHER}_{ADDON_NAME_WEBSITE}_custom_sites_v2"
DEFAULT_CUSTOM_SITES: list = []
WEBSITE_NOTION_URL = "https://www.notion.so"; WEBSITE_YOUTUBE_URL = "https://www.youtube.com"
MAX_CUSTOM_SITES = 4
try:
    _p = _TL["blue"]; _pb = _TL["blue_border"].replace("none","1px solid #0056A4")
    WEBSITE_BUTTON_STYLE = f"""
    QPushButton {{ background-color: {_p}; color: white; padding: 3px 6px; border: {_pb}; border-radius: 4px; min-width: 40px; }}
    QPushButton:hover {{ background-color: {_TL['blue_hover']}; }} QPushButton:pressed {{ background-color: {_TL['blue_pressed']}; }}
    QPushButton#AddButton {{ background-color: {_p}; color: white; min-width: 25px; max-width: 25px; padding: 3px; font-weight: bold; border: {_pb}; border-radius: 4px; }}
    QPushButton#AddButton:hover {{ background-color: {_TL['blue_hover']}; }} QPushButton#AddButton:pressed {{ background-color: {_TL['blue_pressed']}; }}
    QPushButton#AddButton:disabled {{ background-color: #5A6875; color: #A0A0A0; border: 1px solid #444444; }}
    QPushButton#DeleteButton {{ min-width: 18px; max-width: 18px; padding: 2px 1px; font-weight: bold; color: {_TL['text']}; background-color: {_TL['grey_light']}; border: 1px solid {_TL['grey_mid']}; border-radius: 4px; }}
    QPushButton#DeleteButton:hover {{ background-color: {_TL['hover_subtle']}; }} QPushButton#DeleteButton:pressed {{ background-color: {_TL['grey_mid']}; }}"""
except Exception:
    WEBSITE_BUTTON_STYLE = """
    QPushButton { background-color: #0071D3; color: white; padding: 3px 6px; border: 1px solid #0056A4; border-radius: 4px; min-width: 40px; }
    QPushButton:hover { background-color: #0062C4; } QPushButton:pressed { background-color: #004990; }
    QPushButton#AddButton { background-color: #0071D3; color: white; min-width: 25px; max-width: 25px; padding: 3px; font-weight: bold; border: 1px solid #0056A4; border-radius: 4px; }
    QPushButton#AddButton:hover { background-color: #0062C4; } QPushButton#AddButton:pressed { background-color: #004990; }
    QPushButton#AddButton:disabled { background-color: #5A6875; color: #A0A0A0; border: 1px solid #444444; }
    QPushButton#DeleteButton { min-width: 18px; max-width: 18px; padding: 2px 1px; font-weight: bold; color: #1D1D1F; background-color: #E0E0E0; border: 1px solid #B0B0B0; border-radius: 4px; }
    QPushButton#DeleteButton:hover { background-color: #F0F0F0; } QPushButton#DeleteButton:pressed { background-color: #D0D0D0; }"""
WEBSITE_PROFILE_SUBDIR = "website_web_profile"
CONFIG_KEY_LAST_OPENED_URL = f"addon_{ADDON_NAME_LAUNCHER}_{ADDON_NAME_WEBSITE}_last_opened_url"

# --- AI Assistant Sidebar Constants ---
ADDON_NAME_AI_ASSISTANT = "AI_Assistant_Sidebar"

# --- Color Theme ---
# Stores the user's chosen primary colour-theme for the addon UI.
# Valid values: "ocean" (default), "orchid", "forest", "deluge", "horizon", "dusty", "custom"
CONFIG_KEY_ACTIVE_COLOR_THEME = f"addon_{addon_package_name}_active_color_theme"
DEFAULT_ACTIVE_COLOR_THEME = "ocean"


# --- Set by init at runtime ---
addon_path: str = ""
icons_folder: str = ""
qt_version: int = 0
sound_available: bool = False
play_sound_function = lambda x: None