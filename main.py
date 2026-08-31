# Focus Buddy — corrected full file
# - Restores get_unlocked_theme_ids (was missing)
# - Fixes set_native_dnd quoting bug
# - Header buttons layout + theme styling improvements remain
# - Tabs now fill full width (no gap) and use themed accent color
# Save this file over your current main.py and run: python main.py

import json
import os
import io
import shutil
import tempfile
import colorsys
import logging
import random
from datetime import datetime, date
from PIL import Image as PILImage

from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '640')
Config.set('graphics', 'resizable', False)

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.utils import platform

try:
    from plyer import accelerometer, filechooser
    HAS_PLYER = True
except Exception:
    HAS_PLYER = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DATA_FILE = "user_data.json"
AVAILABLE_SOUNDS = [
    ("None", None),
    ("Cicadas", "cicadas.mp3"),
    ("Heavy Rain", "heavyrain.mp3"),
    ("Mountains", "togomoutains.mp3"),
    ("Mountain Spring", "mountain-spring.mp3"),
    ("Pine Forest", "pineforest.mp3"),
    ("Rain", "Rain.mp3"),
    ("Deep Space", "space.mp3"),
    ("Underwater", "underwater.mp3"),
    ("Summer Rain", "SummerRain.mp3"),
    ("BlackFrancolin", "blackfrancolin.mp3")
]

ACCEL_FACE_DOWN_THRESHOLD = -7.0

BASE_COLOR_GROUPS = [
    ("Crimson", 0), ("Coral", 15), ("Amber", 40), ("Sunshine", 55),
    ("Lime", 85), ("Forest", 120), ("Teal", 170), ("Cyan", 190),
    ("Sky", 210), ("Indigo", 240), ("Violet", 275), ("Magenta", 310),
]
VARIANT_LABELS = ["Soft", "Deep", "Bright"]

def contrast_text_color(rgb):
    r, g, b = rgb[:3]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return [0, 0, 0, 1] if lum > 0.65 else [1, 1, 1, 1]

def generate_compact_color_themes():
    themes = []
    classic = {
        "id": "classic",
        "name": "Focus Classic",
        "description": "A calm, balanced workspace",
        "unlock_exp": 0,
        "primary": [0.20, 0.60, 1.00, 1],
        "text": [0.94, 0.97, 1.00, 1],
    }
    themes.append(classic)
    for base_name, base_hue in BASE_COLOR_GROUPS:
        for vi, label in enumerate(VARIANT_LABELS):
            sat = 0.65 + 0.1 * vi
            val = 0.85 + 0.05 * vi
            h = (base_hue % 360) / 360.0
            r, g, b = colorsys.hsv_to_rgb(h, min(1.0, sat), min(1.0, val))
            primary = [r, g, b, 1]
            text = contrast_text_color((r, g, b))
            hue_id = f"{base_name.lower()}_{label.lower()}"
            name = f"{base_name} {label}"
            theme = {
                "id": hue_id,
                "name": name,
                "description": f"{label} {base_name} accents",
                "unlock_exp": 0,
                "primary": primary,
                "text": text,
            }
            themes.append(theme)
    rest = themes[1:]
    random.shuffle(rest)
    shuffled = [themes[0]] + rest
    for i, t in enumerate(shuffled):
        t["unlock_exp"] = 0 if t["id"] == "classic" else i * 100
    return shuffled

COLOR_THEMES = generate_compact_color_themes()
COLOR_THEME_BY_ID = {theme["id"]: theme for theme in COLOR_THEMES}

def build_full_palette_from_colors(primary, text):
    primary = list(primary or [0.2, 0.6, 1.0, 1])
    text = list(text or [1, 1, 1, 1])
    button_down = [max(0, c * 0.75) for c in primary[:3]] + [primary[3] if len(primary) > 3 else 1]
    border = primary
    ring_track = [0.20, 0.22, 0.28, 1]
    return {
        "id": "composed",
        "name": "Composed Palette",
        "primary": primary,
        "text": text,
        "muted": [0.68, 0.72, 0.80, 1],
        "background": [0.07, 0.09, 0.14, 1],
        "surface": [0.10, 0.13, 0.20, 0.96],
        "card": [0.14, 0.18, 0.27, 0.92],
        "button": primary,
        "button_down": button_down,
        "button_text": text,
        "border": border,
        "ring_track": ring_track,
    }

class AnimatedButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if "background_color" not in kwargs:
            self.background_color = [0.16, 0.40, 0.68, 1]
        self.halign = "center"
        self.valign = "middle"
        self.padding = [dp(6), dp(4)]
        self.background_normal = ""
        self.background_down = ""
        self.background_disabled_normal = ""
        self._button_border = [0.55, 0.60, 0.70, 0.65]
        self.bind(
            size=self._update_text_size,
            pos=self._update_button_canvas,
            background_color=self._update_button_canvas,
            state=self._update_button_canvas
        )
        self._update_text_size()
        self._update_button_canvas()

    def _update_text_size(self, *args):
        self.text_size = (max(0, self.width - dp(12)), max(0, self.height - dp(8)))

    def _update_button_canvas(self, *args):
        self.canvas.before.clear()
        fill = list(self.background_color)
        if self.state == "down":
            fill = [max(0, channel * 0.78) if idx < 3 else channel for idx, channel in enumerate(fill)]
        with self.canvas.before:
            Color(*fill)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            Color(*self._button_border)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(10)), width=dp(0.8))

    def set_theme_style(self, fill, text, border):
        try:
            self.background_color = list(fill)
            self.color = list(text)
            self._button_border = list(border)
            self._update_button_canvas()
            try:
                self.canvas.ask_update()
            except Exception:
                pass
        except Exception:
            logger.exception("Failed to apply theme style to AnimatedButton")

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            anim = Animation(opacity=0.7, d=0.08, t='out_quad')
            anim.start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            anim = Animation(opacity=1.0, d=0.12, t='out_quad')
            anim.start(self)
        return super().on_touch_up(touch)

class CenteredTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._update_padding, font_size=self._update_padding)

    def _update_padding(self, *args):
        pad_y = (self.height - self.line_height) / 2
        self.padding = [0, max(0, pad_y), 0, 0]

class ColorPreviewBox(FloatLayout):
    def __init__(self, initial_color=None, **kwargs):
        super().__init__(**kwargs)
        self.current_color = list(initial_color if initial_color is not None else [1, 1, 1, 1])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def set_color(self, color_vec):
        self.current_color = color_vec
        self._update_canvas()

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.current_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
            Color(0.8, 0.8, 0.8, 1)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 8), width=1)

class TimerRingDisplay(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.progress = 1.0
        self.timer_text = "00:00:00"
        self.primary_color = (0.2, 0.6, 1.0, 1)
        self.track_color = (0.2, 0.22, 0.26, 1)
        self.text_color = (1, 1, 1, 1)
        self.label = Label(text=self.timer_text, font_size='32sp', bold=True, color=self.text_color, pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.add_widget(self.label)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def set_ring_colors(self, primary, track):
        self.primary_color = primary
        self.track_color = track
        self._update_canvas()

    def set_font_color(self, color):
        self.text_color = color
        self.label.color = color
        try:
            self.label.canvas.ask_update()
        except Exception:
            pass

    def set_timer_data(self, text_val, current_sec, total_sec):
        self.label.text = text_val
        if total_sec > 0:
            self.progress = max(0.0, min(1.0, current_sec / total_sec))
        else:
            self.progress = 0.0
        self._update_canvas()

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            cx, cy = self.center_x, self.center_y
            radius = min(self.width, self.height) * 0.35
            Color(*self.track_color)
            Line(circle=(cx, cy, radius), width=dp(6))
            if self.progress > 0:
                Color(*self.primary_color)
                angle_end = 360 * self.progress
                Line(circle=(cx, cy, radius, 0, angle_end), width=dp(7), cap='round')

class FocusBuddyApp(App):
    def build(self):
        self.title = "Focus Buddy"
        self.data_file = os.path.join(self.user_data_dir, DATA_FILE)
        self.selected_seconds = 0
        self.timer_seconds = 0
        self.timer_running = False
        self.timer_paused_by_shield = False
        self.shield_enabled = True
        self.is_face_down = None
        self.interrupted_popup = None
        self.is_on_break = False
        self.break_seconds = 0
        self.break_total_seconds = 0
        self.session_break_minutes = 0
        self.current_break_mins = 0
        self.show_break_controls = False
        self.primary_sound = None
        self.primary_sound_name = "None"
        self.secondary_sound = None
        self.secondary_sound_name = "None"
        self.global_volume = 0.8
        self.user_data = self.load_user_data()
        self.check_streak_decay()

        self.root_layout = FloatLayout(size=Window.size, pos=(0, 0))
        self._bg_color_instruction = None
        self._bg_rect = None
        self.root_layout.bind(pos=self._update_background_rect, size=self._update_background_rect)

        Window.bind(on_resize=self._on_window_resize)

        self.bg_image = Image(fit_mode="fill", size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self.root_layout.add_widget(self.bg_image)

        # tab_width is set explicitly to half the window width so the two tabs
        # (Timer / Stats & Custom) always span the full header row with no gap.
        self.panel = TabbedPanel(do_default_tab=False, tab_width=Window.width / 2, tab_height=dp(40), size_hint=(1, 1), background_color=(0, 0, 0, 0.4))

        self.ring_display = TimerRingDisplay(size_hint_y=1.0)
        self.header_label = Label(font_size='11sp', bold=True, halign='left', valign='middle')
        self.stats_summary = Label(font_size='13sp', halign='center', bold=True, size_hint_y=0.2)
        self.history_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)

        # create tabs
        self.panel.add_widget(self.create_focus_tab())
        self.panel.add_widget(self.create_stats_tab())
        self.root_layout.add_widget(self.panel)

        # Restyle the tab headers (selected vs. unselected shade) whenever the
        # active tab changes. Listening on current_tab (rather than binding to
        # each header's on_release) avoids interfering with Kivy's own
        # tab-switching handler.
        self.panel.bind(current_tab=lambda inst, val: Clock.schedule_once(lambda dt: self._style_tabs(self.get_active_palette()), 0))

        if HAS_PLYER:
            try:
                accelerometer.enable()
                Clock.schedule_interval(self.check_sensor_orientation, 0.5)
            except Exception:
                logger.exception("Failed to enable accelerometer or schedule sensor check")

        self.request_android_permissions()
        self.apply_saved_theme()

        return self.root_layout

    def _on_window_resize(self, window, width, height):
        try:
            if self._bg_rect is not None:
                self._bg_rect.pos = (0, 0)
                self._bg_rect.size = Window.size
        except Exception:
            pass
        try:
            # keep the two tabs spanning the full width whenever the window changes size
            if getattr(self, "panel", None) is not None:
                self.panel.tab_width = width / 2
        except Exception:
            pass

    def request_android_permissions(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_MEDIA_IMAGES])
            except Exception:
                logger.exception("Permission request failed")

    def request_dnd_permission(self):
        if platform == 'android':
            try:
                from jnius import autoclass
                Context = autoclass('android.content.Context')
                Intent = autoclass('android.content.Intent')
                Settings = autoclass('android.provider.Settings')
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
                if not nm.isNotificationPolicyAccessGranted():
                    intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
                    activity.startActivity(intent)
            except Exception:
                logger.exception("DND permission intent failed")

    def open_security_settings(self):
        if platform == 'android':
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Settings = autoclass('android.provider.Settings')
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                intent = Intent(Settings.ACTION_SECURITY_SETTINGS)
                activity.startActivity(intent)
            except Exception:
                logger.exception("Security settings intent failed")

    def load_user_data(self):
        default_theme = {
            "theme_id": "classic",
            "primary": [0.2, 0.6, 1.0, 1],
            "text_color": [1.0, 1.0, 1.0, 1],
            "bg_type": "color",
            "bg_color": [0.12, 0.14, 0.18, 1],
            "bg_path": ""
        }
        default = {
            "exp": 0, "streak": 0, "last_completed_date": "",
            "total_minutes": 0, "sessions_completed": 0, "history": [],
            "theme": default_theme,
            "unlocked_themes": ["classic"],
            "last_manual_unlock_level": -1
        }
        data_path = self.data_file
        if (not os.path.exists(data_path) and os.path.exists(DATA_FILE)):
            data_path = DATA_FILE
        if os.path.exists(data_path):
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("exp", 0)
                data.setdefault("streak", 0)
                data.setdefault("last_completed_date", "")
                data.setdefault("total_minutes", 0)
                data.setdefault("sessions_completed", 0)
                data.setdefault("history", [])
                data.setdefault("unlocked_themes", ["classic"])
                if not isinstance(data["unlocked_themes"], list):
                    data["unlocked_themes"] = ["classic"]
                if "classic" not in data["unlocked_themes"]:
                    data["unlocked_themes"].insert(0, "classic")
                if "theme" not in data or isinstance(data["theme"], str):
                    data["theme"] = default_theme
                else:
                    for k, v in default_theme.items():
                        data["theme"].setdefault(k, v)
                    if "theme_id" not in data["theme"]:
                        data["theme"]["theme_id"] = "custom"
                data.setdefault("last_manual_unlock_level", -1)
                if data_path != self.data_file:
                    try:
                        data_dirname = os.path.dirname(self.data_file)
                        if data_dirname:
                            os.makedirs(data_dirname, exist_ok=True)
                        shutil.copy2(data_path, self.data_file)
                    except OSError as exc:
                        logger.exception(f"Could not migrate user data: {exc}")
                return data
            except Exception:
                logger.exception("Failed to load user data; using defaults")
                return default
        return default

    def save_user_data(self):
        data_dir = os.path.dirname(self.data_file) or "."
        try:
            if data_dir:
                os.makedirs(data_dir, exist_ok=True)
        except OSError:
            logger.exception("Could not ensure data directory exists; falling back to current directory")
            data_dir = "."
        fd, temp_path = tempfile.mkstemp(prefix=".user_data_", suffix=".tmp", dir=data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.user_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.data_file)
        except OSError as exc:
            logger.exception(f"Could not save user data: {exc}")
            try:
                os.unlink(temp_path)
            except OSError:
                logger.exception("Failed to remove temporary user data file")

    def load_safe_texture(self, file_path):
        try:
            with PILImage.open(file_path) as img:
                img.load()
                clean_img = (img.convert("RGBA") if img.mode != "RGBA" else img.copy())
                buf = io.BytesIO()
                clean_img.save(buf, format="PNG")
                buf.seek(0)
                return CoreImage(buf, ext="png").texture
        except Exception:
            logger.exception(f"Failed to load texture: {file_path}")
            return None

    def _update_background_rect(self, *args):
        if self._bg_rect is not None:
            try:
                self._bg_rect.pos = (0, 0)
                self._bg_rect.size = Window.size
            except Exception:
                self._bg_rect.pos = self.root_layout.pos
                self._bg_rect.size = self.root_layout.size

    def get_unlocked_theme_ids(self):
        """Return the user's unlocked theme ids (ensure 'classic' present)."""
        unlocked = self.user_data.get("unlocked_themes", ["classic"])
        if not isinstance(unlocked, list):
            unlocked = ["classic"]
            self.user_data["unlocked_themes"] = unlocked
        if "classic" not in unlocked:
            unlocked.insert(0, "classic")
            self.user_data["unlocked_themes"] = unlocked
        return unlocked

    def _walk_widgets(self, widget):
        yield widget
        for child in widget.children:
            yield from self._walk_widgets(child)

    def _paint_surface(self, widget, color, radius=16):
        if widget is None:
            return
        surface_color = list(color)
        if len(surface_color) > 3:
            surface_color[3] = min(surface_color[3], 0.58)
        widget.canvas.before.clear()
        with widget.canvas.before:
            Color(*surface_color)
            RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
        if not getattr(widget, "_theme_surface_bound", False):
            widget.bind(pos=lambda inst, value: self._paint_surface(inst, self.get_active_palette()["surface"], radius),
                        size=lambda inst, value: self._paint_surface(inst, self.get_active_palette()["surface"], radius))
            widget._theme_surface_bound = True

    def _style_tabs(self, palette):
        """Style the TabbedPanel headers to match the active theme's accent color,
        the same color used by the other themed buttons, with the currently
        selected tab shown in the slightly-darker 'pressed' shade."""
        try:
            current = self.panel.current_tab
        except Exception:
            current = None
        try:
            for tab in self.panel.tab_list:
                try:
                    tab.background_normal = ""
                    tab.background_down = ""
                    is_current = (tab is current)
                    tab.background_color = list(palette["button_down"] if is_current else palette["button"])
                    tab.color = list(palette["button_text"])
                    try:
                        tab.font_size = '13sp'
                    except Exception:
                        pass
                    try:
                        tab.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.panel.background_color = [0, 0, 0, 0]
        except Exception:
            pass

    def style_theme_widgets(self, palette):
        for widget in self._walk_widgets(self.root_layout):
            if isinstance(widget, AnimatedButton):
                try:
                    widget.set_theme_style(palette["button"], palette["button_text"], palette["border"])
                    widget.background_color = list(palette["button"])
                    widget.color = list(palette["button_text"])
                    try:
                        widget.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    logger.exception("Failed to style AnimatedButton")
            elif isinstance(widget, TextInput):
                try:
                    widget.background_normal = ""
                    widget.background_active = ""
                    widget.background_color = palette["card"]
                    widget.foreground_color = palette["text"]
                    widget.cursor_color = palette["primary"]
                    try:
                        widget.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    logger.exception("Failed to style TextInput")
            elif isinstance(widget, Label):
                try:
                    widget.color = palette["text"]
                    try:
                        widget.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    pass
            elif widget.__class__.__name__ in ("TabbedPanelHeader", "TabbedPanelContent"):
                try:
                    if hasattr(widget, "background_normal"):
                        widget.background_normal = ""
                    if hasattr(widget, "background_down"):
                        widget.background_down = ""
                    if hasattr(widget, "color"):
                        widget.color = palette.get("button_text", [1,1,1,1])
                    try:
                        widget.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    logger.exception("Failed to style tab header/content")

        self._style_tabs(palette)
        self._paint_surface(getattr(self, "focus_layout", None), palette["surface"], 18)
        self._paint_surface(getattr(self, "stats_layout", None), palette["surface"], 18)

    def get_theme_by_id(self, theme_id):
        theme = COLOR_THEME_BY_ID.get(theme_id)
        if theme:
            return build_full_palette_from_colors(theme.get("primary"), theme.get("text"))
        classic = COLOR_THEME_BY_ID.get("classic")
        return build_full_palette_from_colors(classic.get("primary"), classic.get("text"))

    def get_active_palette(self):
        saved_theme = self.user_data.get("theme", {})
        theme_id = saved_theme.get("theme_id", "classic")
        if theme_id in COLOR_THEME_BY_ID:
            return self.get_theme_by_id(theme_id)
        primary = saved_theme.get("primary", [0.2, 0.6, 1.0, 1])
        text = saved_theme.get("text_color", [1, 1, 1, 1])
        return build_full_palette_from_colors(primary, text)

    def apply_saved_theme(self):
        theme = self.user_data.get("theme", {})
        if isinstance(theme, str):
            theme = {
                "theme_id": "classic",
                "primary": [0.2, 0.6, 1.0, 1],
                "text_color": [1.0, 1.0, 1.0, 1],
                "bg_type": "color",
                "bg_color": [0.12, 0.14, 0.18, 1],
                "bg_path": ""
            }
            self.user_data["theme"] = theme

        self.get_unlocked_theme_ids()
        active_id = theme.get("theme_id", "classic")
        if (active_id not in COLOR_THEME_BY_ID and active_id != "custom"):
            theme["theme_id"] = "classic"

        palette = self.get_active_palette()
        primary = palette["primary"]
        text_col = palette["text"]
        theme["primary"] = list(primary)
        theme["text_color"] = list(text_col)
        theme["bg_color"] = list(palette.get("background", [0.12, 0.14, 0.18, 1]))

        # ring & header text
        self.ring_display.set_ring_colors(primary, palette["ring_track"])
        self.ring_display.set_font_color(text_col)
        try:
            self.header_label.color = text_col
            self.stats_summary.color = text_col
        except Exception:
            pass

        # background handling
        if (theme.get("bg_type") == "image" and theme.get("bg_path") and os.path.exists(theme["bg_path"])):
            safe_tex = self.load_safe_texture(theme["bg_path"])
            if safe_tex:
                self.bg_image.texture = safe_tex
                self.bg_image.source = ""
                self.bg_image.opacity = 1
                self.bg_image.canvas.ask_update()
            else:
                self.bg_image.texture = None
                self.bg_image.opacity = 0
        else:
            self.bg_image.texture = None
            self.bg_image.opacity = 0

        bg_c = theme.get("bg_color", [0.12, 0.14, 0.18, 1])
        if self._bg_color_instruction is None:
            with self.root_layout.canvas.before:
                self._bg_color_instruction = Color(*bg_c)
                self._bg_rect = Rectangle(pos=(0, 0), size=Window.size)
        else:
            self._bg_color_instruction.rgba = bg_c
            self._update_background_rect()

        # Style widgets
        self.style_theme_widgets(palette)
        self.refresh_history_ui()

        # Force immediate restyling for header buttons + tabs
        def style_btn(btn, fill, text, border):
            try:
                btn.set_theme_style(fill, text, border)
                try:
                    btn.font_size = '11sp'
                except Exception:
                    pass
                try:
                    btn._update_button_canvas()
                    btn.canvas.ask_update()
                except Exception:
                    pass
            except Exception:
                pass

        header_items = {
            "sound1_btn": getattr(self, "sound1_btn", None),
            "sound2_btn": getattr(self, "sound2_btn", None),
            "shield_btn": getattr(self, "shield_btn", None),
            "btn_break_toggle": getattr(self, "btn_break_toggle", None),
            "set_custom_btn": getattr(self, "set_custom_btn", None),
            "start_break_btn": getattr(self, "start_break_btn", None),
            "action_btn": getattr(self, "action_btn", None),
        }
        for name, w in header_items.items():
            if isinstance(w, AnimatedButton):
                if name == "shield_btn":
                    if getattr(self, "shield_enabled", True):
                        style_btn(w, palette["primary"], palette["button_text"], palette["border"])
                    else:
                        style_btn(w, palette["button_down"], palette["button_text"], palette["border"])
                else:
                    style_btn(w, palette["button"], palette["button_text"], palette["border"])

        self._style_tabs(palette)

        Clock.schedule_once(lambda dt: self._force_theme_refresh(), 0.03)

    def _force_theme_refresh(self, *args):
        palette = self.get_active_palette()
        try:
            self.ring_display.set_ring_colors(palette["primary"], palette["ring_track"])
            self.ring_display.set_font_color(palette["text"])
        except Exception:
            logger.exception("Failed to update ring display colors")
        try:
            self.header_label.color = palette["text"]
            self.stats_summary.color = palette["text"]
        except Exception:
            pass

        self.style_theme_widgets(palette)

        for attr in ("sound1_btn", "sound2_btn", "shield_btn", "btn_break_toggle", "start_break_btn", "action_btn", "set_custom_btn"):
            w = getattr(self, attr, None)
            if isinstance(w, AnimatedButton):
                try:
                    if attr == "shield_btn":
                        if getattr(self, "shield_enabled", True):
                            w.set_theme_style(palette["primary"], palette["button_text"], palette["border"])
                        else:
                            w.set_theme_style(palette["button_down"], palette["button_text"], palette["border"])
                    else:
                        w.set_theme_style(palette["button"], palette["button_text"], palette["border"])
                    w._update_button_canvas()
                    try:
                        w.canvas.ask_update()
                    except Exception:
                        pass
                except Exception:
                    pass

        self._style_tabs(palette)

    def unlock_new_themes(self):
        return []

    def get_level_info(self):
        level = (self.user_data["exp"] // 100) + 1
        current_level_exp = self.user_data["exp"] % 100
        return level, current_level_exp

    def check_streak_decay(self):
        last_date_str = self.user_data.get("last_completed_date")
        if last_date_str:
            try:
                last_date = date.fromisoformat(last_date_str)
                if (date.today() - last_date).days > 1:
                    self.user_data["streak"] = 0
                    self.save_user_data()
            except Exception:
                logger.exception("Error checking streak decay")

    def set_native_dnd(self, enable):
        # Android only — attempt to set interruption filter if allowed
        if platform == 'android':
            try:
                from jnius import autoclass
                Context = autoclass("android.content.Context")
                NotificationManager = autoclass("android.app.NotificationManager")
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
                if nm and nm.isNotificationPolicyAccessGranted():
                    mode = (NotificationManager.INTERRUPTION_FILTER_NONE if enable else NotificationManager.INTERRUPTION_FILTER_ALL)
                    nm.setInterruptionFilter(mode)
            except Exception:
                logger.exception("Android DND Error")

    def set_app_pinning(self, enable):
        if platform == 'android':
            try:
                from jnius import autoclass
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                if enable:
                    activity.startLockTask()
                else:
                    activity.stopLockTask()
            except Exception:
                logger.exception("Android App Pinning Error")

    def _load_sound_from_file(self, filename):
        if not filename:
            return None
        filepath = os.path.join("assets", filename)
        if not os.path.exists(filepath):
            return None
        try:
            sound_obj = SoundLoader.load(filepath)
            return sound_obj
        except Exception:
            logger.exception(f"Failed to load sound: {filepath}")
            return None

    def _cycle_sound(self, slot):
        if slot not in ("primary", "secondary"):
            return
        curr_name_attr = f"{slot}_sound_name"
        sound_attr = f"{slot}_sound"
        btn_attr = f"sound1_btn" if slot == "primary" else "sound2_btn"
        curr_idx = 0
        curr_name = getattr(self, curr_name_attr, "None")
        for i, item in enumerate(AVAILABLE_SOUNDS):
            if item[0] == curr_name:
                curr_idx = i
                break
        next_idx = (curr_idx + 1) % len(AVAILABLE_SOUNDS)
        s_name, s_file = AVAILABLE_SOUNDS[next_idx]
        prev_sound = getattr(self, sound_attr, None)
        if prev_sound:
            try:
                prev_sound.stop()
            except Exception:
                logger.exception("Failed to stop previous sound")
        setattr(self, sound_attr, None)
        setattr(self, curr_name_attr, s_name)
        sound_obj = self._load_sound_from_file(s_file) if s_file else None
        if sound_obj:
            setattr(self, sound_attr, sound_obj)
        def finalize_sound(dt):
            snd = getattr(self, sound_attr, None)
            if snd:
                try:
                    snd.loop = True
                except Exception:
                    pass
                snd.volume = self.global_volume
                if (not self.shield_enabled or self.is_face_down or not HAS_PLYER):
                    try:
                        snd.play()
                    except Exception:
                        logger.exception("Failed to play sound")
        Clock.schedule_once(finalize_sound, 0.05)
        btn = getattr(self, btn_attr, None)
        if btn:
            try:
                btn.text = f"{'S1' if slot == 'primary' else 'S2'}: {s_name}"
            except Exception:
                pass

    def cycle_primary_sound(self, instance):
        self._cycle_sound("primary")

    def cycle_secondary_sound(self, instance):
        self._cycle_sound("secondary")

    def update_volume(self, instance, value):
        self.global_volume = value
        if self.primary_sound:
            try:
                self.primary_sound.volume = self.global_volume
            except Exception:
                logger.exception("Failed to set primary sound volume")
        if self.secondary_sound:
            try:
                self.secondary_sound.volume = self.global_volume
            except Exception:
                logger.exception("Failed to set secondary sound volume")

    def stop_all_sounds(self):
        if self.primary_sound:
            try:
                self.primary_sound.stop()
            except Exception:
                logger.exception("Failed to stop primary sound")
        if self.secondary_sound:
            try:
                self.secondary_sound.stop()
            except Exception:
                logger.exception("Failed to stop secondary sound")

    def play_all_sounds(self):
        if (self.primary_sound and self.primary_sound_name != "None"):
            try:
                self.primary_sound.play()
            except Exception:
                logger.exception("Failed to play primary sound")
        if (self.secondary_sound and self.secondary_sound_name != "None"):
            try:
                self.secondary_sound.play()
            except Exception:
                logger.exception("Failed to play secondary sound")

    def show_interrupted_popup(self):
        if (self.interrupted_popup is not None or self.is_on_break):
            return
        palette = self.get_active_palette()
        content = BoxLayout(orientation="vertical", padding=[dp(18), dp(14)], spacing=dp(7))
        with content.canvas.before:
            Color(*palette["surface"])
            self.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(16)])
            Color(*palette["primary"])
            self.border = Line(rounded_rectangle=(content.x, content.y, content.width, content.height, dp(16)), width=dp(1.5))
        def update_rect(instance, value):
            self.rect.pos = instance.pos
            self.rect.size = instance.size
            self.border.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(16))
        content.bind(pos=update_rect, size=update_rect)
        icon_label = Label(text="!", font_size="26sp", bold=True, color=palette["primary"], size_hint_y=None, height=dp(32))
        title_label = Label(text="Focus Shield Paused", font_size="18sp", bold=True, color=palette["text"], halign="center", valign="middle", size_hint_y=None, height=dp(34))
        desc_label = Label(text=("The timer is paused while your phone is face-up.\nTurn it face-down to continue."), font_size="13sp", halign="center", valign="middle", color=palette["muted"], size_hint_y=None, height=dp(58))
        title_label.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
        desc_label.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
        content.add_widget(icon_label); content.add_widget(title_label); content.add_widget(desc_label)
        content.opacity = 0
        self.interrupted_popup = Popup(title="", separator_height=0, content=content, size_hint=(0.9, None), height=dp(220), auto_dismiss=False, background="")
        self.interrupted_popup.open()
        pop_anim = Animation(opacity=1, d=0.25, t="out_cubic")
        pop_anim.start(content)

    def dismiss_interrupted_popup(self):
        if self.interrupted_popup:
            anim = Animation(opacity=0, d=0.18, t="in_cubic")
            def on_complete(*args):
                if self.interrupted_popup:
                    self.interrupted_popup.dismiss()
                    self.interrupted_popup = None
            anim.bind(on_complete=on_complete)
            anim.start(self.interrupted_popup.content)

    def check_sensor_orientation(self, dt):
        if (not HAS_PLYER or not self.shield_enabled or not self.timer_running or self.is_on_break):
            return
        try:
            val = accelerometer.acceleration
            if val and val[2] is not None:
                if val[2] < ACCEL_FACE_DOWN_THRESHOLD:
                    self.set_face_down_state(True)
                else:
                    self.set_face_down_state(False)
        except Exception:
            logger.exception("Error reading accelerometer")

    def set_face_down_state(self, is_down):
        if self.is_face_down == is_down:
            return
        self.is_face_down = is_down
        if self.is_face_down:
            self.timer_paused_by_shield = False
            self.dismiss_interrupted_popup()
            self.play_all_sounds()
        else:
            if (self.timer_running and self.shield_enabled and not self.is_on_break):
                self.timer_paused_by_shield = True
                self.show_interrupted_popup()
            self.stop_all_sounds()

    def create_focus_tab(self):
        tab = TabbedPanelHeader(text="Timer")
        self.focus_layout = BoxLayout(orientation="vertical", padding=[12, 10, 12, 12], spacing=10)

        header_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=6)
        level, cur_exp = self.get_level_info()
        self.header_label.text = (f"Lvl {level} ({cur_exp}/100) | " f"🔥 {self.user_data['streak']}d")
        self.header_label.font_size = '11sp'
        self.header_label.size_hint_x = 0.36
        self.header_label.bind(size=self.header_label.setter("text_size"))

        buttons_box = BoxLayout(orientation="horizontal", spacing=6, size_hint_x=0.64)
        self.sound1_btn = AnimatedButton(text="S1: Off", font_size="10sp", bold=True, size_hint_x=0.25)
        self.sound1_btn.bind(on_release=self.cycle_primary_sound)
        self.sound2_btn = AnimatedButton(text="S2: Off", font_size="10sp", bold=True, size_hint_x=0.25)
        self.sound2_btn.bind(on_release=self.cycle_secondary_sound)
        self.shield_btn = AnimatedButton(text="Shield: ON", font_size="10sp", bold=True, size_hint_x=0.50)
        self.shield_btn.bind(on_release=self.toggle_shield)

        buttons_box.add_widget(self.sound1_btn)
        buttons_box.add_widget(self.sound2_btn)
        buttons_box.add_widget(self.shield_btn)

        header_row.add_widget(self.header_label)
        header_row.add_widget(buttons_box)
        self.focus_layout.add_widget(header_row)

        self.btn_break_toggle = AnimatedButton(text="☕ Take a Break", font_size="12sp", bold=True, size_hint_y=None, height=dp(38))
        self.btn_break_toggle.bind(on_press=self.toggle_break_panel)
        self.focus_layout.add_widget(self.btn_break_toggle)

        self.break_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=8, padding=[5, 0])
        self.break_slider_label = Label(text="Break: 5m", font_size="12sp", size_hint_x=0.3, bold=True)
        self.break_slider = Slider(min=0, max=30, value=5, step=1, size_hint_x=0.45)
        self.break_slider.bind(value=self.on_break_slider_change)
        self.start_break_btn = AnimatedButton(text="Start Break", font_size="11sp", size_hint_x=0.25, bold=True)
        self.start_break_btn.bind(on_press=self.start_break_session)
        self.break_box.add_widget(self.break_slider_label); self.break_box.add_widget(self.break_slider); self.break_box.add_widget(self.start_break_btn)

        self.focus_layout.add_widget(self.ring_display)

        vol_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=8, padding=[10, 0])
        vol_label = Label(text="🔊", font_size="14sp", size_hint_x=0.1)
        self.vol_slider = Slider(min=0.0, max=1.0, value=0.8, size_hint_x=0.9)
        self.vol_slider.bind(value=self.update_volume)
        vol_layout.add_widget(vol_label); vol_layout.add_widget(self.vol_slider)
        self.focus_layout.add_widget(vol_layout)

        self.custom_time_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=6)
        self.hours_input = CenteredTextInput(text="", hint_text="00", multiline=False, input_filter="int", font_size="22sp", halign="center", size_hint_x=0.25)
        hours_label = Label(text="h", font_size="18sp", size_hint_x=0.08, bold=True)
        self.mins_input = CenteredTextInput(text="", hint_text="00", multiline=False, input_filter="int", font_size="22sp", halign="center", size_hint_x=0.25)
        mins_label = Label(text="m", font_size="18sp", size_hint_x=0.08, bold=True)

        self.set_custom_btn = AnimatedButton(text="Set Time", font_size="15sp", size_hint_x=0.34, bold=True)
        self.set_custom_btn.bind(on_press=self.apply_custom_time)

        self.custom_time_layout.add_widget(self.hours_input); self.custom_time_layout.add_widget(hours_label); self.custom_time_layout.add_widget(self.mins_input); self.custom_time_layout.add_widget(mins_label); self.custom_time_layout.add_widget(self.set_custom_btn)
        self.focus_layout.add_widget(self.custom_time_layout)

        self.action_btn = AnimatedButton(text="Start Session", font_size="18sp", size_hint_y=None, height=dp(55), bold=True)
        self.action_btn.bind(on_press=self.toggle_timer)
        self.focus_layout.add_widget(self.action_btn)

        tab.content = self.focus_layout
        return tab

    def apply_custom_time(self, instance):
        try:
            h = (int(self.hours_input.text) if self.hours_input.text else 0)
            m = (int(self.mins_input.text) if self.mins_input.text else 0)
            total_sec = (h * 3600) + (m * 60)
            if total_sec > 0:
                self.selected_seconds = total_sec
                self.timer_seconds = total_sec
                self.update_timer_label(total_sec)
        except ValueError:
            pass

    def toggle_timer(self, instance):
        if not self.timer_running:
            if self.timer_seconds > 0:
                self.request_dnd_permission()
                self.timer_running = True
                self.action_btn.text = "Pause Session"
                self.set_native_dnd(True)
                self.set_app_pinning(True)
                Clock.schedule_interval(self.update_timer, 1)
        else:
            self.timer_running = False
            self.timer_paused_by_shield = False
            self.action_btn.text = "Resume Session"
            self.set_native_dnd(False)
            self.set_app_pinning(False)
            Clock.unschedule(self.update_timer)
            self.stop_all_sounds()

    def update_timer(self, dt):
        if self.timer_paused_by_shield:
            return
        if self.timer_seconds > 0:
            self.timer_seconds -= 1
            self.update_timer_label(self.timer_seconds)
        else:
            Clock.unschedule(self.update_timer)
            self.timer_running = False
            self.timer_paused_by_shield = False
            self.action_btn.text = "Start Session"
            self.set_native_dnd(False)
            self.set_app_pinning(False)
            self.stop_all_sounds()
            mins_completed = max(1, self.selected_seconds // 60)
            exp_gained = mins_completed * 2
            self.user_data["exp"] += exp_gained
            newly_unlocked = self.unlock_new_themes()
            self.user_data["total_minutes"] += mins_completed
            self.user_data["sessions_completed"] += 1
            today_str = date.today().isoformat()
            if (self.user_data.get("last_completed_date") != today_str):
                self.user_data["streak"] += 1
                self.user_data["last_completed_date"] = today_str
            audio_used = []
            if self.primary_sound_name != "None":
                audio_used.append(self.primary_sound_name)
            if self.secondary_sound_name != "None":
                audio_used.append(self.secondary_sound_name)
            self.user_data["history"].append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mins": mins_completed,
                "break_mins": self.session_break_minutes,
                "exp": exp_gained,
                "audio": (", ".join(audio_used) if audio_used else None)
            })
            self.session_break_minutes = 0
            self.save_user_data()
            self.apply_saved_theme()
            self.refresh_history_ui()
            if newly_unlocked:
                Clock.schedule_once(lambda dt: self.show_theme_unlock_popup(newly_unlocked), 0.15)

    def unlock_new_themes(self):
        return []

    def show_theme_unlock_popup(self, themes):
        if not themes:
            return
        palette = self.get_active_palette()
        content = BoxLayout(orientation="vertical", padding=[dp(18), dp(14)], spacing=dp(8))
        title = Label(text="✦ New Color Theme unlocked", font_size="18sp", bold=True, color=palette["text"], size_hint_y=None, height=dp(34))
        content.add_widget(title)
        for theme in themes:
            reward = Label(text=f"🎨 {theme['name']}\n{theme['description']}", font_size="13sp", halign="center", valign="middle", color=palette["primary"], size_hint_y=None, height=dp(48))
            reward.bind(size=reward.setter("text_size"))
            content.add_widget(reward)
        close_btn = AnimatedButton(text="Open Theme Collection", font_size="13sp", bold=True, size_hint_y=None, height=dp(42))
        close_btn.set_theme_style(palette["button"], palette["button_text"], palette["border"])
        popup = Popup(title="", separator_height=0, content=content, size_hint=(0.88, None), height=dp(250), auto_dismiss=True)
        def open_collection(instance):
            popup.dismiss()
            self.open_color_picker_popup(instance)
        close_btn.bind(on_release=open_collection)
        content.add_widget(close_btn)
        popup.open()

    def update_timer_label(self, total_sec):
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        time_str = (f"{hrs:02d}:{mins:02d}:{secs:02d}")
        self.ring_display.set_timer_data(time_str, total_sec, self.selected_seconds)

    def toggle_break_panel(self, instance):
        self.show_break_controls = (not self.show_break_controls)
        if self.show_break_controls:
            self.focus_layout.add_widget(self.break_box, index=len(self.focus_layout.children) - 2)
            try:
                self.btn_break_toggle.set_theme_style(self.get_active_palette()["primary"], self.get_active_palette()["button_text"], self.get_active_palette()["border"])
            except Exception:
                pass
        else:
            if (self.break_box in self.focus_layout.children):
                self.focus_layout.remove_widget(self.break_box)
            try:
                self.btn_break_toggle.set_theme_style(self.get_active_palette()["button"], self.get_active_palette()["button_text"], self.get_active_palette()["border"])
            except Exception:
                pass

    def on_break_slider_change(self, instance, value):
        self.break_slider_label.text = (f"Break: {int(value)}m")

    def start_break_session(self, instance):
        break_mins = int(self.break_slider.value)
        if break_mins <= 0:
            return
        self.is_on_break = True
        self.current_break_mins = break_mins
        self.break_seconds = break_mins * 60
        self.break_total_seconds = self.break_seconds
        self.set_native_dnd(False)
        self.set_app_pinning(False)
        self.dismiss_interrupted_popup()
        self.stop_all_sounds()
        Clock.unschedule(self.update_timer)
        self.action_btn.text = "On Break..."
        self.action_btn.disabled = True
        Clock.schedule_interval(self.update_break_timer, 1)

    def update_break_timer(self, dt):
        if self.break_seconds > 0:
            self.break_seconds -= 1
            hrs = self.break_seconds // 3600
            mins = (self.break_seconds % 3600) // 60
            secs = self.break_seconds % 60
            time_str = (f"☕ {hrs:02d}:{mins:02d}:{secs:02d}")
            self.ring_display.set_timer_data(time_str, self.break_seconds, self.break_total_seconds)
        else:
            Clock.unschedule(self.update_break_timer)
            self.is_on_break = False
            self.action_btn.disabled = False
            self.session_break_minutes += (self.current_break_mins)
            self.current_break_mins = 0
            if self.timer_running:
                self.set_native_dnd(True)
                self.set_app_pinning(True)
                self.action_btn.text = "Pause Session"
                Clock.schedule_interval(self.update_timer, 1)
            else:
                self.action_btn.text = "Start Session"
                self.update_timer_label(self.timer_seconds)

    def toggle_shield(self, instance):
        self.shield_enabled = (not self.shield_enabled)
        palette = self.get_active_palette()
        if self.shield_enabled:
            self.shield_btn.text = "Shield: ON"
            try:
                self.shield_btn.set_theme_style(palette["primary"], palette["button_text"], palette["border"])
            except Exception:
                pass
        else:
            self.shield_btn.text = "Shield: OFF"
            self.timer_paused_by_shield = False
            try:
                self.shield_btn.set_theme_style(palette["button_down"], palette["button_text"], palette["border"])
            except Exception:
                pass

        # force redraw
        try:
            self.shield_btn._update_button_canvas()
            self.shield_btn.canvas.ask_update()
        except Exception:
            pass

        self.dismiss_interrupted_popup()

        if (not self.shield_enabled and self.timer_running and not self.is_on_break):
            self.play_all_sounds()
        elif (self.shield_enabled and self.timer_running and not self.is_face_down and not self.is_on_break):
            self.timer_paused_by_shield = True
            self.show_interrupted_popup()

    def get_stats_text(self):
        lvl, exp = self.get_level_info()
        unlocked_count = len(self.get_unlocked_theme_ids())
        locked_themes = [theme for theme in COLOR_THEMES if theme["id"] not in self.user_data["unlocked_themes"]]
        if locked_themes:
            next_theme = locked_themes[0]
            reward_line = (f"Themes: {unlocked_count}/{len(COLOR_THEMES)} • Next: {next_theme['name']} at {next_theme['unlock_exp']} XP")
        else:
            reward_line = "Themes: All earned ✦"
        return (f"Level {lvl} | Total XP: {self.user_data['exp']}\n"
                f"Sessions: {self.user_data['sessions_completed']} | Total Time: {self.user_data['total_minutes']} mins\n"
                f"{reward_line}")

    def refresh_history_ui(self):
        self.history_grid.clear_widgets()
        self.stats_summary.text = self.get_stats_text()
        history_list = self.user_data.get("history", [])
        if not history_list:
            empty_lbl = Label(text="No completed sessions yet.", font_size="12sp", color=self.get_active_palette()["muted"], size_hint_y=None, height=dp(30))
            self.history_grid.add_widget(empty_lbl)
            return
        for item in reversed(history_list):
            item_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(55), padding=6, spacing=2)
            with item_box.canvas.before:
                Color(*self.get_active_palette()["card"])
                RoundedRectangle(pos=item_box.pos, size=item_box.size, radius=[dp(10)])
            item_box.bind(pos=lambda inst, val: self._update_item_canvas(inst), size=lambda inst, val: self._update_item_canvas(inst))
            top_txt = (f"⏱️ {item.get('mins', 0)} mins")
            if item.get("break_mins", 0) > 0:
                top_txt += (f" (+{item['break_mins']}m break)")
            top_txt += (f" • +{item.get('exp', 0)} XP")
            lbl_top = Label(text=top_txt, font_size="11sp", bold=True, halign="left", size_hint_y=0.5)
            lbl_top.bind(size=lbl_top.setter("text_size"))
            date_str = item.get("date", "")
            audio_str = (f" • 🎵 {item['audio']}" if item.get("audio") else "")
            lbl_sub = Label(text=f"📅 {date_str}{audio_str}", font_size="9sp", color=self.get_active_palette()["muted"], halign="left", size_hint_y=0.5)
            lbl_sub.bind(size=lbl_sub.setter("text_size"))
            item_box.add_widget(lbl_top); item_box.add_widget(lbl_sub)
            self.history_grid.add_widget(item_box)

    def _update_item_canvas(self, instance):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(*self.get_active_palette()["card"])
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(10)])

    def create_stats_tab(self):
        tab = TabbedPanelHeader(text="Stats & Custom")
        layout = BoxLayout(orientation="vertical", padding=10, spacing=8)
        self.stats_layout = layout
        self.stats_summary.text = self.get_stats_text()
        layout.add_widget(self.stats_summary)
        custom_modal_btn = AnimatedButton(text="🎨 Theme & Colors Customizer", font_size="12sp", bold=True, size_hint_y=0.1)
        custom_modal_btn.bind(on_release=self.open_color_picker_popup)
        layout.add_widget(custom_modal_btn)
        log_title = Label(text="📜 Recent Session Logs", font_size="13sp", bold=True, size_hint_y=0.08)
        layout.add_widget(log_title)
        self.history_scroll = ScrollView(size_hint_y=0.62)
        self.history_grid.bind(minimum_height=self.history_grid.setter("height"))
        self.history_scroll.add_widget(self.history_grid)
        layout.add_widget(self.history_scroll)
        self.refresh_history_ui()
        tab.content = layout
        return tab

    def open_color_picker_popup(self, instance):
        content = BoxLayout(orientation="vertical", padding=12, spacing=10, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(content)
        theme_title = Label(text="🏆 Reward Color Themes", font_size="14sp", bold=True, color=self.get_active_palette()["primary"], size_hint_y=None, height=dp(24))
        content.add_widget(theme_title)
        theme_hint = Label(text=("Complete focus sessions to earn new color themes. Themes change the app's accent and text colors."), font_size="10sp", color=self.get_active_palette()["muted"], halign="left", valign="middle", size_hint_y=None, height=dp(52))
        theme_hint.bind(width=lambda label, value: setattr(label, "text_size", (value, None)))
        content.add_widget(theme_hint)
        theme_grid = GridLayout(cols=2, spacing=dp(7), size_hint_y=None)
        theme_grid.bind(minimum_height=theme_grid.setter("height"))
        content.add_widget(theme_grid)

        def manual_unlock_available():
            level, _ = self.get_level_info()
            last_manual = self.user_data.get("last_manual_unlock_level", -1)
            return level > last_manual

        def select_theme(theme_id):
            if theme_id == "custom":
                self.user_data["theme"]["theme_id"] = "custom"
                self.apply_saved_theme()
                self.save_user_data()
                render_theme_cards()
                Clock.schedule_once(self._force_theme_refresh, 0)
                return
            unlocked_ids = self.get_unlocked_theme_ids()
            if theme_id in unlocked_ids:
                self.user_data["theme"]["theme_id"] = theme_id
                self.apply_saved_theme()
                self.save_user_data()
                render_theme_cards()
                Clock.schedule_once(self._force_theme_refresh, 0)
                return
            if manual_unlock_available():
                level, _ = self.get_level_info()
                self.user_data.setdefault("unlocked_themes", []).append(theme_id)
                self.user_data["last_manual_unlock_level"] = level
                self.user_data["theme"]["theme_id"] = theme_id
                self.save_user_data()
                self.apply_saved_theme()
                render_theme_cards()
                Clock.schedule_once(self._force_theme_refresh, 0)
                popup = Popup(title="", content=Label(text=f"Unlocked {COLOR_THEME_BY_ID[theme_id]['name']}!"), size_hint=(0.7, None), height=dp(120), auto_dismiss=True)
                popup.open()
                return
            return

        def render_theme_cards():
            theme_grid.clear_widgets()
            selected_id = self.user_data["theme"].get("theme_id", "classic")
            unlocked_ids = self.get_unlocked_theme_ids()
            available_cards = [{"id": "custom", "name": "Custom palette", "description": "Your text-color slider", "unlock_exp": 0}] + COLOR_THEMES
            manual_available = manual_unlock_available()
            for theme in available_cards:
                is_unlocked = (theme["id"] == "custom" or theme["id"] in unlocked_ids)
                is_selected = theme["id"] == selected_id
                if is_selected:
                    prefix = "✓ "
                elif is_unlocked:
                    prefix = "◆ "
                else:
                    prefix = "🔒 "
                if is_unlocked:
                    subtitle = theme.get("description", "")
                else:
                    if manual_available:
                        subtitle = "Locked — Tap to unlock now"
                    else:
                        subtitle = "Locked"
                theme_btn = AnimatedButton(text=f"{prefix}{theme.get('name')}\n{subtitle}", font_size="10sp", bold=is_selected, size_hint_y=None, height=dp(60), disabled=(not is_unlocked and not manual_available))
                if theme["id"] in COLOR_THEME_BY_ID:
                    t = COLOR_THEME_BY_ID[theme["id"]]
                    card_palette = build_full_palette_from_colors(t.get("primary"), t.get("text"))
                else:
                    card_palette = self.get_active_palette()
                theme_btn.set_theme_style(card_palette["button"], card_palette["button_text"], card_palette["border"])
                theme_btn.bind(on_release=lambda btn, theme_id=theme["id"]: select_theme(theme_id))
                theme_grid.add_widget(theme_btn)

        render_theme_cards()

        content.add_widget(Label(text="Text Font Color Picker", font_size="12sp", bold=True, size_hint_y=None, height=dp(20)))
        font_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=10)
        current_font = self.user_data["theme"]["text_color"]
        font_preview = ColorPreviewBox(initial_color=current_font, size_hint_x=0.2)
        font_hue = colorsys.rgb_to_hsv(current_font[0], current_font[1], current_font[2])[0]
        font_slider = Slider(min=0, max=1, value=font_hue, size_hint_x=0.6)
        def update_font(inst, val):
            r, g, b = colorsys.hsv_to_rgb(val, 0.85, 0.95)
            new_col = [r, g, b, 1]
            font_preview.set_color(new_col)
            self.user_data["theme"]["theme_id"] = "custom"
            self.user_data["theme"]["text_color"] = new_col
            self.apply_saved_theme()
            self.save_user_data()
            Clock.schedule_once(self._force_theme_refresh, 0)
        font_slider.bind(value=update_font)
        preset_box = BoxLayout(orientation="vertical", size_hint_x=0.2, spacing=4)
        btn_white = AnimatedButton(text="White", font_size="10sp", size_hint_y=0.5)
        btn_black = AnimatedButton(text="Black", font_size="10sp", size_hint_y=0.5)
        def set_white(inst):
            new_col = [1, 1, 1, 1]
            font_preview.set_color(new_col)
            self.user_data["theme"]["theme_id"] = "custom"
            self.user_data["theme"]["text_color"] = new_col
            self.apply_saved_theme()
            self.save_user_data()
            Clock.schedule_once(self._force_theme_refresh, 0)
        def set_black(inst):
            new_col = [0, 0, 0, 1]
            font_preview.set_color(new_col)
            self.user_data["theme"]["theme_id"] = "custom"
            self.user_data["theme"]["text_color"] = new_col
            self.apply_saved_theme()
            self.save_user_data()
            Clock.schedule_once(self._force_theme_refresh, 0)
        btn_white.bind(on_release=set_white)
        btn_black.bind(on_release=set_black)
        preset_box.add_widget(btn_white)
        preset_box.add_widget(btn_black)
        font_box.add_widget(font_preview)
        font_box.add_widget(font_slider)
        font_box.add_widget(preset_box)
        content.add_widget(font_box)

        content.add_widget(Label(text="Optional Personal Background", font_size="12sp", bold=True, size_hint_y=None, height=dp(20)))
        bg_btn_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(35), spacing=8)
        btn_gallery = AnimatedButton(text="🖼️ Choose Image", font_size="11sp", bold=True)
        btn_gallery.set_theme_style(self.get_active_palette()["button"], self.get_active_palette()["button_text"], self.get_active_palette()["border"])
        btn_clear_bg = AnimatedButton(text="Use Theme Color", font_size="11sp")
        btn_clear_bg.set_theme_style(self.get_active_palette()["button"], self.get_active_palette()["button_text"], self.get_active_palette()["border"])
        def choose_custom_bg(inst):
            if HAS_PLYER:
                try:
                    filechooser.open_file(on_selection=self._on_bg_file_selected)
                except Exception:
                    logger.exception("Plyer filechooser failed; falling back to visual picker")
                    self.show_visual_image_picker()
            else:
                self.show_visual_image_picker()
        def clear_bg(inst):
            self.user_data["theme"]["bg_type"] = "color"
            self.user_data["theme"]["bg_path"] = ""
            self.apply_saved_theme()
            self.save_user_data()
            Clock.schedule_once(self._force_theme_refresh, 0)
        btn_gallery.bind(on_release=choose_custom_bg)
        btn_clear_bg.bind(on_release=clear_bg)
        bg_btn_box.add_widget(btn_gallery)
        bg_btn_box.add_widget(btn_clear_bg)
        content.add_widget(bg_btn_box)

        popup = Popup(title="Appearance Customizer", content=scroll, size_hint=(0.94, 0.88))
        popup.open()

    def get_root_directory(self):
        if platform == "android":
            return "/sdcard"
        return os.path.expanduser("~")

    def _on_bg_file_selected(self, selection):
        if selection and len(selection) > 0:
            image_path = selection[0]
            if os.path.isfile(image_path):
                Clock.schedule_once(lambda dt: self._apply_selected_background(image_path), 0)

    def _apply_selected_background(self, image_path):
        if os.path.isfile(image_path):
            self.user_data["theme"]["bg_type"] = "image"
            self.user_data["theme"]["bg_path"] = image_path
            self.apply_saved_theme()
            self.bg_image.canvas.ask_update()
            self.save_user_data()
            Clock.schedule_once(self._force_theme_refresh, 0)

    def show_visual_image_picker(self):
        self.current_folder = (self.get_root_directory())
        content = BoxLayout(orientation="vertical", padding=8, spacing=6)
        path_label = Label(text=self.current_folder, font_size="10sp", size_hint_y=None, height=dp(20), halign="left")
        path_label.bind(size=path_label.setter("text_size"))
        content.add_widget(path_label)
        top_nav = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(30), spacing=5)
        btn_up = AnimatedButton(text="⬆ Up Directory", font_size="11sp")
        top_nav.add_widget(btn_up)
        content.add_widget(top_nav)
        scroll = ScrollView(size_hint_y=0.8)
        grid = GridLayout(cols=2, spacing=10, size_hint_y=None, padding=5)
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)
        content.add_widget(scroll)
        popup = Popup(title="File & Folder Picker", content=content, size_hint=(0.95, 0.9))
        def load_directory(target_path):
            self.current_folder = target_path
            path_label.text = target_path
            grid.clear_widgets()
            valid_exts = (".png", ".jpg", ".jpeg", ".webp")
            try:
                items = sorted(os.listdir(target_path))
            except (PermissionError, OSError):
                grid.add_widget(Label(text="⚠️ Permission Denied", font_size="12sp"))
                return
            except Exception:
                logger.exception("Cannot open folder")
                grid.add_widget(Label(text="⚠️ Cannot open folder", font_size="12sp"))
                return
            dirs = []; files = []
            for item in items:
                if (item.startswith(".") or item.startswith("~$")):
                    continue
                full_item_path = os.path.join(target_path, item)
                try:
                    if os.path.isdir(full_item_path):
                        dirs.append(item)
                    elif item.lower().endswith(valid_exts):
                        files.append(item)
                except OSError:
                    continue
            for d in dirs:
                full_path = os.path.join(target_path, d)
                btn = AnimatedButton(text=f"📁 {d}", font_size="11sp", bold=True, size_hint_y=None, height=dp(60))
                def make_dir_cb(p):
                    return lambda inst: load_directory(p)
                btn.bind(on_release=make_dir_cb(full_path))
                grid.add_widget(btn)
            for f in files:
                full_path = os.path.join(target_path, f)
                tex = self.load_safe_texture(full_path)
                card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(130), padding=4, spacing=2)
                with card.canvas.before:
                    Color(0.2, 0.22, 0.28, 0.8)
                    RoundedRectangle(pos=card.pos, size=card.size, radius=[8])
                def update_card_bg(inst, val):
                    inst.canvas.before.clear()
                    with inst.canvas.before:
                        Color(0.2, 0.22, 0.28, 0.8)
                        RoundedRectangle(pos=inst.pos, size=inst.size, radius=[8])
                card.bind(pos=update_card_bg, size=update_card_bg)
                if tex:
                    img_widget = Image(texture=tex, fit_mode="contain", size_hint_y=0.75)
                else:
                    img_widget = Label(text="🖼️", font_size="24sp", size_hint_y=0.75)
                name_lbl = Label(text=f, font_size="9sp", size_hint_y=0.25, halign="center", valign="middle", shorten=True, shorten_from="right")
                name_lbl.bind(size=name_lbl.setter("text_size"))
                card.add_widget(img_widget); card.add_widget(name_lbl)
                # Transparent tap-catcher overlaid on the thumbnail. Must stay fully
                # invisible (no fill, no border) or it hides the image beneath it.
                select_btn = Button(text="", background_normal="", background_down="", background_color=(0, 0, 0, 0), size_hint=(1, 1))
                cell = FloatLayout(size_hint_y=None, height=dp(130))
                card.size_hint = (1, 1); card.pos_hint = {"x": 0, "y": 0}
                select_btn.pos_hint = {"x": 0, "y": 0}
                cell.add_widget(card); cell.add_widget(select_btn)
                def make_file_cb(p):
                    return lambda inst: (self._on_bg_file_selected([p]), popup.dismiss())
                select_btn.bind(on_release=make_file_cb(full_path))
                grid.add_widget(cell)
            if not dirs and not files:
                grid.add_widget(Label(text=("Folder is empty or has no images"), font_size="12sp"))
        def go_up(inst):
            parent = os.path.dirname(self.current_folder)
            if (parent and os.path.exists(parent)):
                load_directory(parent)
        btn_up.bind(on_release=go_up)
        load_directory(self.current_folder)
        popup.open()

if __name__ == "__main__":
    FocusBuddyApp().run()
