import json
import os
import io
import colorsys
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
from kivy.utils import platform

try:
    from plyer import accelerometer, filechooser
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

AVAILABLE_SOUNDS = [
    ("None", None),
    ("Cicadas", "cicadas.mp3"),
    ("Heavy Rain", "heavyrain.mp3"),
    ("Mountains", "koukoutogo-mountains.mp3"),
    ("Mountain Spring", "mountain-spring.mp3"),
    ("Pine Forest", "pineforest.mp3"),
    ("Rain", "Rain.mp3"),
    ("Deep Space", "space.mp3"),
    ("Underwater", "underwater.mp3")
]

class AnimatedButton(Button):
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
    def __init__(self, initial_color=[1, 1, 1, 1], **kwargs):
        super().__init__(**kwargs)
        self.current_color = initial_color
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
        
        self.label = Label(
            text=self.timer_text,
            font_size='32sp',
            bold=True,
            color=self.text_color,
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.add_widget(self.label)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def set_ring_colors(self, primary, track):
        self.primary_color = primary
        self.track_color = track
        self._update_canvas()

    def set_font_color(self, color):
        self.text_color = color
        self.label.color = color

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

        # Store user data in Kivy's private app data directory.
        # Each installation/device gets its own user_data.json.
        self.data_file = os.path.join(
            self.user_data_dir,
            "user_data.json"
        )

        self.data_file = os.path.join(
            self.user_data_dir,
            "user_data.json"
        )

        self.selected_seconds = 0
        self.timer_seconds = 0
        self.timer_running = False
        self.shield_enabled = True
        self.is_face_down = False
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
        
        self.root_layout = FloatLayout()
        self.bg_image = Image(fit_mode="fill", size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self.root_layout.add_widget(self.bg_image)
        
        self.panel = TabbedPanel(
            do_default_tab=False,
            tab_width=dp(160),
            tab_height=dp(40),
            size_hint=(1, 1),
            background_color=(0, 0, 0, 0.4)
        )
        
        self.ring_display = TimerRingDisplay(size_hint_y=1.0)
        self.header_label = Label(font_size='11sp', bold=True, halign='left', valign='middle', size_hint_x=0.38)
        self.stats_summary = Label(font_size='13sp', halign='center', bold=True, size_hint_y=0.2)
        self.history_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        
        self.panel.add_widget(self.create_focus_tab())
        self.panel.add_widget(self.create_stats_tab())
        self.root_layout.add_widget(self.panel)
        
        if HAS_PLYER:
            try:
                accelerometer.enable()
                Clock.schedule_interval(self.check_sensor_orientation, 0.5)
            except Exception:
                pass
        
        self.request_android_permissions()
        self.apply_saved_theme()
        return self.root_layout

    def request_android_permissions(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_MEDIA_IMAGES
                ])
            except Exception as e:
                print(f"Permission Error: {e}")

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
            except Exception as e:
                print(f"DND Intent Error: {e}")

    def open_security_settings(self):
        if platform == 'android':
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Settings = autoclass('android.provider.Settings')
                activity = autoclass('org.kivy.android.PythonActivity').mActivity
                
                intent = Intent(Settings.ACTION_SECURITY_SETTINGS)
                activity.startActivity(intent)
            except Exception as e:
                print(f"Security Settings Intent Error: {e}")

    def load_user_data(self):
        default_theme = {
            "primary": [0.2, 0.6, 1.0, 1],
            "text_color": [1.0, 1.0, 1.0, 1],
            "bg_type": "color",
            "bg_color": [0.12, 0.14, 0.18, 1],
            "bg_path": ""
        }
        default = {
            "exp": 0, "streak": 0, "last_completed_date": "",
            "total_minutes": 0, "sessions_completed": 0, "history": [],
            "theme": default_theme
        }
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                data.setdefault("exp", 0)
                data.setdefault("streak", 0)
                data.setdefault("last_completed_date", "")
                data.setdefault("total_minutes", 0)
                data.setdefault("sessions_completed", 0)
                data.setdefault("history", [])
                
                if "theme" not in data or isinstance(data["theme"], str):
                    data["theme"] = default_theme
                else:
                    for k, v in default_theme.items():
                        data["theme"].setdefault(k, v)
                return data
            except Exception:
                return default
        return default

    def save_user_data(self):
        with open(self.data_file, "w") as f:
            json.dump(self.user_data, f)


    def load_safe_texture(self, file_path):
        try:
            with PILImage.open(file_path) as img:
                img.load()
                clean_img = (
                    img.convert("RGBA")
                    if img.mode != "RGBA"
                    else img.copy()
                )

                buf = io.BytesIO()
                clean_img.save(buf, format="PNG")
                buf.seek(0)

                return CoreImage(buf, ext="png").texture

        except Exception:
            return None


    def apply_saved_theme(self):
        theme = self.user_data.get("theme", {})

        if isinstance(theme, str):
            theme = {
                "primary": [0.2, 0.6, 1.0, 1],
                "text_color": [1.0, 1.0, 1.0, 1],
                "bg_type": "color",
                "bg_color": [0.12, 0.14, 0.18, 1],
                "bg_path": ""
            }

            self.user_data["theme"] = theme

        primary = theme.get(
            "primary",
            [0.2, 0.6, 1.0, 1]
        )

        text_col = theme.get(
            "text_color",
            [1.0, 1.0, 1.0, 1]
        )

        self.ring_display.set_ring_colors(
            primary,
            (0.2, 0.22, 0.26, 1)
        )

        self.ring_display.set_font_color(text_col)
        self.header_label.color = text_col
        self.stats_summary.color = text_col

        if (
            theme.get("bg_type") == "image"
            and theme.get("bg_path")
            and os.path.exists(theme["bg_path"])
        ):
            safe_tex = self.load_safe_texture(
                theme["bg_path"]
            )

            if safe_tex:
                self.bg_image.texture = safe_tex
                self.bg_image.opacity = 1
            else:
                self.bg_image.opacity = 0
        else:
            self.bg_image.opacity = 0

        bg_c = theme.get(
            "bg_color",
            [0.12, 0.14, 0.18, 1]
        )

        with self.root_layout.canvas.before:
            Color(*bg_c)
            Rectangle(
                pos=self.root_layout.pos,
                size=(800, 1280)
            )


    def get_level_info(self):
        level = (self.user_data["exp"] // 100) + 1
        current_level_exp = self.user_data["exp"] % 100

        return level, current_level_exp


    def check_streak_decay(self):
        last_date_str = self.user_data.get(
            "last_completed_date"
        )

        if last_date_str:
            try:
                last_date = date.fromisoformat(
                    last_date_str
                )

                if (date.today() - last_date).days > 1:
                    self.user_data["streak"] = 0
                    self.save_user_data()

            except Exception:
                pass


    def set_native_dnd(self, enable):
        if platform == "android":
            try:
                from jnius import autoclass

                Context = autoclass(
                    "android.content.Context"
                )

                NotificationManager = autoclass(
                    "android.app.NotificationManager"
                )

                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity

                nm = activity.getSystemService(
                    Context.NOTIFICATION_SERVICE
                )

                if nm.isNotificationPolicyAccessGranted():
                    mode = (
                        NotificationManager.INTERRUPTION_FILTER_NONE
                        if enable
                        else NotificationManager.INTERRUPTION_FILTER_ALL
                    )

                    nm.setInterruptionFilter(mode)

            except Exception as e:
                print(f"Android DND Error: {e}")


    def set_app_pinning(self, enable):
        if platform == "android":
            try:
                from jnius import autoclass

                activity = autoclass(
                    "org.kivy.android.PythonActivity"
                ).mActivity

                if enable:
                    activity.startLockTask()
                else:
                    activity.stopLockTask()

            except Exception as e:
                print(f"Android App Pinning Error: {e}")


    def cycle_primary_sound(self, instance):
        curr_idx = 0

        for i, item in enumerate(AVAILABLE_SOUNDS):
            if item[0] == self.primary_sound_name:
                curr_idx = i
                break

        next_idx = (
            curr_idx + 1
        ) % len(AVAILABLE_SOUNDS)

        s_name, s_file = AVAILABLE_SOUNDS[next_idx]

        if self.primary_sound:
            self.primary_sound.stop()

        self.primary_sound = None
        self.primary_sound_name = s_name

        filepath = (
            os.path.join("assets", s_file)
            if s_file
            else None
        )

        if filepath and os.path.exists(filepath):
            sound_obj = SoundLoader.load(filepath)

            if sound_obj:
                self.primary_sound = sound_obj

        def finalize_sound(dt):
            if self.primary_sound:
                self.primary_sound.loop = True
                self.primary_sound.volume = self.global_volume

                if (
                    not self.shield_enabled
                    or self.is_face_down
                    or not HAS_PLYER
                ):
                    self.primary_sound.play()

        Clock.schedule_once(
            finalize_sound,
            0.05
        )

        self.sound1_btn.text = f"S1: {s_name}"


    def cycle_secondary_sound(self, instance):
        curr_idx = 0

        for i, item in enumerate(AVAILABLE_SOUNDS):
            if item[0] == self.secondary_sound_name:
                curr_idx = i
                break

        next_idx = (
            curr_idx + 1
        ) % len(AVAILABLE_SOUNDS)

        s_name, s_file = AVAILABLE_SOUNDS[next_idx]

        if self.secondary_sound:
            self.secondary_sound.stop()

        self.secondary_sound = None
        self.secondary_sound_name = s_name

        filepath = (
            os.path.join("assets", s_file)
            if s_file
            else None
        )

        if filepath and os.path.exists(filepath):
            sound_obj = SoundLoader.load(filepath)

            if sound_obj:
                self.secondary_sound = sound_obj

        def finalize_sound(dt):
            if self.secondary_sound:
                self.secondary_sound.loop = True
                self.secondary_sound.volume = self.global_volume

                if (
                    not self.shield_enabled
                    or self.is_face_down
                    or not HAS_PLYER
                ):
                    self.secondary_sound.play()

        Clock.schedule_once(
            finalize_sound,
            0.05
        )

        self.sound2_btn.text = f"S2: {s_name}"


    def update_volume(self, instance, value):
        self.global_volume = value

        if self.primary_sound:
            self.primary_sound.volume = self.global_volume

        if self.secondary_sound:
            self.secondary_sound.volume = self.global_volume


    def stop_all_sounds(self):
        if self.primary_sound:
            self.primary_sound.stop()

        if self.secondary_sound:
            self.secondary_sound.stop()


    def play_all_sounds(self):
        if (
            self.primary_sound
            and self.primary_sound_name != "None"
        ):
            self.primary_sound.play()

        if (
            self.secondary_sound
            and self.secondary_sound_name != "None"
        ):
            self.secondary_sound.play()


    def show_interrupted_popup(self):
        if (
            self.interrupted_popup is not None
            or self.is_on_break
        ):
            return

        content = FloatLayout()

        with content.canvas.before:
            Color(0.12, 0.14, 0.18, 0.98)

            self.rect = RoundedRectangle(
                size=(310, 160),
                pos=(0, 0),
                radius=[16]
            )

            Color(0.9, 0.25, 0.25, 1)

            self.border = Line(
                rounded_rectangle=(
                    0,
                    0,
                    310,
                    160,
                    16
                ),
                width=1.5
            )

        def update_rect(instance, value):
            self.rect.pos = instance.pos
            self.rect.size = instance.size
            self.border.rounded_rectangle = (
                instance.x,
                instance.y,
                instance.width,
                instance.height,
                16
            )

        content.bind(
            pos=update_rect,
            size=update_rect
        )

        card_box = BoxLayout(
            orientation="vertical",
            padding=15,
            spacing=8
        )

        icon_label = Label(
            text="📳",
            font_size="28sp",
            size_hint_y=0.3
        )

        title_label = Label(
            text="Session Interrupted",
            font_size="20sp",
            bold=True,
            color=[1, 1, 1, 1],
            size_hint_y=0.3
        )

        desc_label = Label(
            text=(
                "Place phone face-down to continue\n"
                "and keep focus active."
            ),
            font_size="13sp",
            halign="center",
            color=[0.8, 0.8, 0.85, 1],
            size_hint_y=0.4
        )

        card_box.add_widget(icon_label)
        card_box.add_widget(title_label)
        card_box.add_widget(desc_label)

        content.add_widget(card_box)
        content.opacity = 0

        self.interrupted_popup = Popup(
            title="",
            separator_height=0,
            content=content,
            size_hint=(None, None),
            size=(310, 160),
            auto_dismiss=False,
            background=""
        )

        self.interrupted_popup.open()

        pop_anim = Animation(
            opacity=1,
            d=0.25,
            t="out_cubic"
        )

        pop_anim.start(content)


    def dismiss_interrupted_popup(self):
        if self.interrupted_popup:
            anim = Animation(
                opacity=0,
                d=0.18,
                t="in_cubic"
            )

            def on_complete(*args):
                if self.interrupted_popup:
                    self.interrupted_popup.dismiss()
                    self.interrupted_popup = None

            anim.bind(on_complete=on_complete)
            anim.start(
                self.interrupted_popup.content
            )


    def check_sensor_orientation(self, dt):
        if (
            not HAS_PLYER
            or not self.shield_enabled
            or not self.timer_running
            or self.is_on_break
        ):
            return

        try:
            val = accelerometer.acceleration

            if val and val[2] is not None:
                if val[2] < -7.0:
                    self.set_face_down_state(True)
                else:
                    self.set_face_down_state(False)

        except Exception:
            pass


    def set_face_down_state(self, is_down):
        if self.is_face_down == is_down:
            return

        self.is_face_down = is_down

        if self.is_face_down:
            self.dismiss_interrupted_popup()
            self.play_all_sounds()

        else:
            if (
                self.timer_running
                and self.shield_enabled
                and not self.is_on_break
            ):
                self.show_interrupted_popup()

            self.stop_all_sounds()


    def create_focus_tab(self):
        tab = TabbedPanelHeader(text="Timer")

        self.focus_layout = BoxLayout(
            orientation="vertical",
            padding=[12, 10, 12, 12],
            spacing=10
        )

        header_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=6
        )

        level, cur_exp = self.get_level_info()

        self.header_label.text = (
            f"Lvl {level} ({cur_exp}/100) | "
            f"🔥 {self.user_data['streak']}d"
        )

        self.header_label.bind(
            size=self.header_label.setter("text_size")
        )

        self.sound1_btn = AnimatedButton(
            text="S1: Off",
            font_size="9sp",
            bold=True,
            size_hint_x=0.22
        )

        self.sound1_btn.bind(
            on_release=self.cycle_primary_sound
        )

        self.sound2_btn = AnimatedButton(
            text="S2: Off",
            font_size="9sp",
            bold=True,
            size_hint_x=0.22
        )

        self.sound2_btn.bind(
            on_release=self.cycle_secondary_sound
        )

        self.shield_btn = AnimatedButton(
            text="Shield: ON",
            font_size="9sp",
            bold=True,
            size_hint_x=0.18,
            background_color=[0.2, 0.6, 1.0, 1]
        )

        self.shield_btn.bind(
            on_release=self.toggle_shield
        )

        header_row.add_widget(self.header_label)
        header_row.add_widget(self.sound1_btn)
        header_row.add_widget(self.sound2_btn)
        header_row.add_widget(self.shield_btn)

        self.focus_layout.add_widget(header_row)

        self.btn_break_toggle = AnimatedButton(
            text="☕ Take a Break",
            font_size="12sp",
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_color=[0.3, 0.3, 0.35, 1]
        )

        self.btn_break_toggle.bind(
            on_press=self.toggle_break_panel
        )

        self.focus_layout.add_widget(
            self.btn_break_toggle
        )

        self.break_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=8,
            padding=[5, 0]
        )

        self.break_slider_label = Label(
            text="Break: 5m",
            font_size="12sp",
            size_hint_x=0.3,
            bold=True
        )

        self.break_slider = Slider(
            min=0,
            max=30,
            value=5,
            step=1,
            size_hint_x=0.45
        )

        self.break_slider.bind(
            value=self.on_break_slider_change
        )

        self.start_break_btn = AnimatedButton(
            text="Start Break",
            font_size="11sp",
            size_hint_x=0.25,
            bold=True,
            background_color=[0.2, 0.7, 0.4, 1]
        )

        self.start_break_btn.bind(
            on_press=self.start_break_session
        )

        self.break_box.add_widget(
            self.break_slider_label
        )
        self.break_box.add_widget(
            self.break_slider
        )
        self.break_box.add_widget(
            self.start_break_btn
        )

        self.focus_layout.add_widget(
            self.ring_display
        )

        vol_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=8,
            padding=[10, 0]
        )

        vol_label = Label(
            text="🔊",
            font_size="14sp",
            size_hint_x=0.1
        )

        self.vol_slider = Slider(
            min=0.0,
            max=1.0,
            value=0.8,
            size_hint_x=0.9
        )

        self.vol_slider.bind(
            value=self.update_volume
        )

        vol_layout.add_widget(vol_label)
        vol_layout.add_widget(self.vol_slider)

        self.focus_layout.add_widget(
            vol_layout
        )

        self.custom_time_layout = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=6
        )

        self.hours_input = CenteredTextInput(
            text="",
            hint_text="00",
            multiline=False,
            input_filter="int",
            font_size="22sp",
            halign="center",
            size_hint_x=0.25
        )

        hours_label = Label(
            text="h",
            font_size="18sp",
            size_hint_x=0.08,
            bold=True
        )

        self.mins_input = CenteredTextInput(
            text="",
            hint_text="00",
            multiline=False,
            input_filter="int",
            font_size="22sp",
            halign="center",
            size_hint_x=0.25
        )

        mins_label = Label(
            text="m",
            font_size="18sp",
            size_hint_x=0.08,
            bold=True
        )

        set_custom_btn = AnimatedButton(
            text="Set Time",
            font_size="15sp",
            size_hint_x=0.34,
            bold=True
        )

        set_custom_btn.bind(
            on_press=self.apply_custom_time
        )

        self.custom_time_layout.add_widget(
            self.hours_input
        )
        self.custom_time_layout.add_widget(
            hours_label
        )
        self.custom_time_layout.add_widget(
            self.mins_input
        )
        self.custom_time_layout.add_widget(
            mins_label
        )
        self.custom_time_layout.add_widget(
            set_custom_btn
        )

        self.focus_layout.add_widget(
            self.custom_time_layout
        )

        self.action_btn = AnimatedButton(
            text="Start Session",
            font_size="18sp",
            size_hint_y=None,
            height=dp(55),
            bold=True
        )

        self.action_btn.bind(
            on_press=self.toggle_timer
        )

        self.focus_layout.add_widget(
            self.action_btn
        )

        tab.content = self.focus_layout

        return tab


    def apply_custom_time(self, instance):
        try:
            h = (
                int(self.hours_input.text)
                if self.hours_input.text
                else 0
            )

            m = (
                int(self.mins_input.text)
                if self.mins_input.text
                else 0
            )

            total_sec = (
                h * 3600
            ) + (
                m * 60
            )

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
                self.open_security_settings()

                self.timer_running = True
                self.action_btn.text = "Pause Session"

                self.set_native_dnd(True)
                self.set_app_pinning(True)

                Clock.schedule_interval(
                    self.update_timer,
                    1
                )

        else:
            self.timer_running = False
            self.action_btn.text = "Resume Session"

            self.set_native_dnd(False)
            self.set_app_pinning(False)

            Clock.unschedule(
                self.update_timer
            )

            self.stop_all_sounds()


    def update_timer(self, dt):
        if self.timer_seconds > 0:
            self.timer_seconds -= 1
            self.update_timer_label(
                self.timer_seconds
            )

        else:
            Clock.unschedule(
                self.update_timer
            )

            self.timer_running = False
            self.action_btn.text = "Start Session"

            self.set_native_dnd(False)
            self.set_app_pinning(False)
            self.stop_all_sounds()

            mins_completed = max(
                1,
                self.selected_seconds // 60
            )

            exp_gained = mins_completed * 2

            self.user_data["exp"] += exp_gained
            self.user_data["total_minutes"] += mins_completed
            self.user_data["sessions_completed"] += 1

            today_str = date.today().isoformat()

            if (
                self.user_data.get("last_completed_date")
                != today_str
            ):
                self.user_data["streak"] += 1
                self.user_data["last_completed_date"] = today_str

            audio_used = []

            if self.primary_sound_name != "None":
                audio_used.append(
                    self.primary_sound_name
                )

            if self.secondary_sound_name != "None":
                audio_used.append(
                    self.secondary_sound_name
                )

            self.user_data["history"].append(
                {
                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "mins": mins_completed,
                    "break_mins": self.session_break_minutes,
                    "exp": exp_gained,
                    "audio": (
                        ", ".join(audio_used)
                        if audio_used
                        else None
                    )
                }
            )

            self.session_break_minutes = 0

            self.save_user_data()
            self.apply_saved_theme()
            self.refresh_history_ui()


    def update_timer_label(self, total_sec):
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60

        time_str = (
            f"{hrs:02d}:{mins:02d}:{secs:02d}"
        )

        self.ring_display.set_timer_data(
            time_str,
            total_sec,
            self.selected_seconds
        )


    def toggle_break_panel(self, instance):
        self.show_break_controls = (
            not self.show_break_controls
        )

        if self.show_break_controls:
            self.focus_layout.add_widget(
                self.break_box,
                index=len(
                    self.focus_layout.children
                ) - 2
            )

            self.btn_break_toggle.background_color = [
                0.2,
                0.6,
                1.0,
                1
            ]

        else:
            if (
                self.break_box
                in self.focus_layout.children
            ):
                self.focus_layout.remove_widget(
                    self.break_box
                )

            self.btn_break_toggle.background_color = [
                0.3,
                0.3,
                0.35,
                1
            ]


    def on_break_slider_change(self, instance, value):
        self.break_slider_label.text = (
            f"Break: {int(value)}m"
        )


    def start_break_session(self, instance):
        break_mins = int(
            self.break_slider.value
        )

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

        Clock.unschedule(
            self.update_timer
        )

        self.action_btn.text = "On Break..."
        self.action_btn.disabled = True

        Clock.schedule_interval(
            self.update_break_timer,
            1
        )


    def update_break_timer(self, dt):
        if self.break_seconds > 0:
            self.break_seconds -= 1

            hrs = self.break_seconds // 3600
            mins = (self.break_seconds % 3600) // 60
            secs = self.break_seconds % 60

            time_str = (
                f"☕ {hrs:02d}:{mins:02d}:{secs:02d}"
            )

            self.ring_display.set_timer_data(
                time_str,
                self.break_seconds,
                self.break_total_seconds
            )

        else:
            Clock.unschedule(
                self.update_break_timer
            )

            self.is_on_break = False
            self.action_btn.disabled = False

            self.session_break_minutes += (
                self.current_break_mins
            )

            self.current_break_mins = 0

            if self.timer_running:
                self.set_native_dnd(True)
                self.set_app_pinning(True)

                self.action_btn.text = "Pause Session"

                Clock.schedule_interval(
                    self.update_timer,
                    1
                )

            else:
                self.action_btn.text = "Start Session"
                self.update_timer_label(
                    self.timer_seconds
                )


    def toggle_shield(self, instance):
        self.shield_enabled = (
            not self.shield_enabled
        )

        if self.shield_enabled:
            self.shield_btn.text = "Shield: ON"
            self.shield_btn.background_color = [
                0.2,
                0.6,
                1.0,
                1
            ]

        else:
            self.shield_btn.text = "Shield: OFF"
            self.shield_btn.background_color = [
                0.4,
                0.4,
                0.4,
                1
            ]

        self.dismiss_interrupted_popup()


    def get_stats_text(self):
        lvl, exp = self.get_level_info()

        return (
            f"Level {lvl} | Total XP: "
            f"{self.user_data['exp']}\n"
            f"Sessions: "
            f"{self.user_data['sessions_completed']} | "
            f"Total Time: "
            f"{self.user_data['total_minutes']} mins"
        )


    def refresh_history_ui(self):
        self.history_grid.clear_widgets()
        self.stats_summary.text = self.get_stats_text()

        history_list = self.user_data.get(
            "history",
            []
        )

        if not history_list:
            empty_lbl = Label(
                text="No completed sessions yet.",
                font_size="12sp",
                color=[0.7, 0.7, 0.7, 1],
                size_hint_y=None,
                height=dp(30)
            )

            self.history_grid.add_widget(
                empty_lbl
            )

            return

        for item in reversed(history_list):
            item_box = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(55),
                padding=6,
                spacing=2
            )

            with item_box.canvas.before:
                Color(
                    0.2,
                    0.22,
                    0.28,
                    0.6
                )

                RoundedRectangle(
                    pos=item_box.pos,
                    size=item_box.size,
                    radius=[6]
                )

            item_box.bind(
                pos=lambda inst, val:
                    self._update_item_canvas(inst),
                size=lambda inst, val:
                    self._update_item_canvas(inst)
            )

            top_txt = (
                f"⏱️ {item.get('mins', 0)} mins"
            )

            if item.get("break_mins", 0) > 0:
                top_txt += (
                    f" (+{item['break_mins']}m break)"
                )

            top_txt += (
                f" • +{item.get('exp', 0)} XP"
            )

            lbl_top = Label(
                text=top_txt,
                font_size="11sp",
                bold=True,
                halign="left",
                size_hint_y=0.5
            )

            lbl_top.bind(
                size=lbl_top.setter("text_size")
            )

            date_str = item.get(
                "date",
                ""
            )

            audio_str = (
                f" • 🎵 {item['audio']}"
                if item.get("audio")
                else ""
            )

            lbl_sub = Label(
                text=f"📅 {date_str}{audio_str}",
                font_size="9sp",
                color=[0.75, 0.8, 0.85, 1],
                halign="left",
                size_hint_y=0.5
            )

            lbl_sub.bind(
                size=lbl_sub.setter("text_size")
            )

            item_box.add_widget(lbl_top)
            item_box.add_widget(lbl_sub)

            self.history_grid.add_widget(
                item_box
            )


    def _update_item_canvas(self, instance):
        instance.canvas.before.clear()

        with instance.canvas.before:
            Color(
                0.2,
                0.22,
                0.28,
                0.6
            )

            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[6]
            )


    def create_stats_tab(self):
        tab = TabbedPanelHeader(
            text="Stats & Custom"
        )

        layout = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        self.stats_summary.text = (
            self.get_stats_text()
        )

        layout.add_widget(
            self.stats_summary
        )

        custom_modal_btn = AnimatedButton(
            text="🎨 Theme & Colors Customizer",
            font_size="12sp",
            bold=True,
            size_hint_y=0.1,
            background_color=[0.2, 0.6, 0.9, 1]
        )

        custom_modal_btn.bind(
            on_release=self.open_color_picker_popup
        )

        layout.add_widget(
            custom_modal_btn
        )

        log_title = Label(
            text="📜 Recent Session Logs",
            font_size="13sp",
            bold=True,
            size_hint_y=0.08
        )

        layout.add_widget(log_title)

        self.history_scroll = ScrollView(
            size_hint_y=0.62
        )

        self.history_grid.bind(
            minimum_height=self.history_grid.setter(
                "height"
            )
        )

        self.history_scroll.add_widget(
            self.history_grid
        )

        layout.add_widget(
            self.history_scroll
        )

        self.refresh_history_ui()

        tab.content = layout

        return tab


    def open_color_picker_popup(self, instance):
        content = BoxLayout(
            orientation="vertical",
            padding=12,
            spacing=10
        )

        content.add_widget(
            Label(
                text="Ring / Accent Color Picker",
                font_size="12sp",
                bold=True,
                size_hint_y=None,
                height=dp(20)
            )
        )

        accent_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=10
        )

        current_accent = self.user_data["theme"]["primary"]

        accent_preview = ColorPreviewBox(
            initial_color=current_accent,
            size_hint_x=0.2
        )

        hue_val = colorsys.rgb_to_hsv(
            current_accent[0],
            current_accent[1],
            current_accent[2]
        )[0]

        accent_slider = Slider(
            min=0,
            max=1,
            value=hue_val,
            size_hint_x=0.8
        )

        def update_accent(inst, val):
            r, g, b = colorsys.hsv_to_rgb(
                val,
                0.85,
                0.95
            )

            new_col = [r, g, b, 1]

            accent_preview.set_color(
                new_col
            )

            self.user_data["theme"]["primary"] = new_col
            self.apply_saved_theme()
            self.save_user_data()

        accent_slider.bind(
            value=update_accent
        )

        accent_box.add_widget(
            accent_preview
        )

        accent_box.add_widget(
            accent_slider
        )

        content.add_widget(
            accent_box
        )

        content.add_widget(
            Label(
                text="Text Font Color Picker",
                font_size="12sp",
                bold=True,
                size_hint_y=None,
                height=dp(20)
            )
        )

        font_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=10
        )

        current_font = self.user_data["theme"]["text_color"]

        font_preview = ColorPreviewBox(
            initial_color=current_font,
            size_hint_x=0.2
        )

        font_hue = colorsys.rgb_to_hsv(
            current_font[0],
            current_font[1],
            current_font[2]
        )[0]

        font_slider = Slider(
            min=0,
            max=1,
            value=font_hue,
            size_hint_x=0.8
        )

        def update_font(inst, val):
            r, g, b = colorsys.hsv_to_rgb(
                val,
                0.85,
                0.95
            )

            new_col = [r, g, b, 1]

            font_preview.set_color(
                new_col
            )

            self.user_data["theme"]["text_color"] = new_col
            self.apply_saved_theme()
            self.save_user_data()

        font_slider.bind(
            value=update_font
        )

        font_box.add_widget(
            font_preview
        )

        font_box.add_widget(
            font_slider
        )

        content.add_widget(
            font_box
        )

        content.add_widget(
            Label(
                text="Background Picture",
                font_size="12sp",
                bold=True,
                size_hint_y=None,
                height=dp(20)
            )
        )

        bg_btn_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(35),
            spacing=8
        )

        btn_gallery = AnimatedButton(
            text="🖼️ Gallery / Images",
            font_size="11sp",
            bold=True
        )

        btn_clear_bg = AnimatedButton(
            text="Clear Image",
            font_size="11sp"
        )

        def choose_custom_bg(inst):
            if HAS_PLYER:
                try:
                    filechooser.open_file(
                        on_selection=self._on_bg_file_selected
                    )
                except Exception:
                    self.show_visual_image_picker()
            else:
                self.show_visual_image_picker()

        def clear_bg(inst):
            self.user_data["theme"]["bg_type"] = "color"
            self.user_data["theme"]["bg_path"] = ""

            self.apply_saved_theme()
            self.save_user_data()

        btn_gallery.bind(
            on_release=choose_custom_bg
        )

        btn_clear_bg.bind(
            on_release=clear_bg
        )

        bg_btn_box.add_widget(
            btn_gallery
        )

        bg_btn_box.add_widget(
            btn_clear_bg
        )

        content.add_widget(
            bg_btn_box
        )

        popup = Popup(
            title="Appearance Customizer",
            content=content,
            size_hint=(0.9, 0.65)
        )

        popup.open()


    def get_root_directory(self):
        if platform == "android":
            return "/sdcard"

        return os.path.expanduser("~")


    def _on_bg_file_selected(self, selection):
        if selection and len(selection) > 0:
            image_path = selection[0]

            if os.path.exists(image_path):
                self.user_data["theme"]["bg_type"] = "image"
                self.user_data["theme"]["bg_path"] = image_path

                self.apply_saved_theme()
                self.save_user_data()


    def show_visual_image_picker(self):
        self.current_folder = (
            self.get_root_directory()
        )

        content = BoxLayout(
            orientation="vertical",
            padding=8,
            spacing=6
        )

        path_label = Label(
            text=self.current_folder,
            font_size="10sp",
            size_hint_y=None,
            height=dp(20),
            halign="left"
        )

        path_label.bind(
            size=path_label.setter("text_size")
        )

        content.add_widget(
            path_label
        )

        top_nav = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(30),
            spacing=5
        )

        btn_up = AnimatedButton(
            text="⬆ Up Directory",
            font_size="11sp"
        )

        top_nav.add_widget(btn_up)
        content.add_widget(top_nav)

        scroll = ScrollView(
            size_hint_y=0.8
        )

        grid = GridLayout(
            cols=2,
            spacing=10,
            size_hint_y=None,
            padding=5
        )

        grid.bind(
            minimum_height=grid.setter("height")
        )

        scroll.add_widget(grid)
        content.add_widget(scroll)

        popup = Popup(
            title="File & Folder Picker",
            content=content,
            size_hint=(0.95, 0.9)
        )

        def load_directory(target_path):
            self.current_folder = target_path
            path_label.text = target_path
            grid.clear_widgets()

            valid_exts = (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp"
            )

            try:
                items = sorted(
                    os.listdir(target_path)
                )

            except (PermissionError, OSError):
                grid.add_widget(
                    Label(
                        text="⚠️ Permission Denied",
                        font_size="12sp"
                    )
                )
                return

            except Exception:
                grid.add_widget(
                    Label(
                        text="⚠️ Cannot open folder",
                        font_size="12sp"
                    )
                )
                return

            dirs = []
            files = []

            for item in items:
                if (
                    item.startswith(".")
                    or item.startswith("~$")
                ):
                    continue

                full_item_path = os.path.join(
                    target_path,
                    item
                )

                try:
                    if os.path.isdir(full_item_path):
                        dirs.append(item)

                    elif item.lower().endswith(valid_exts):
                        files.append(item)

                except OSError:
                    continue

            for d in dirs:
                full_path = os.path.join(
                    target_path,
                    d
                )

                btn = AnimatedButton(
                    text=f"📁 {d}",
                    font_size="11sp",
                    bold=True,
                    size_hint_y=None,
                    height=dp(60),
                    background_color=[
                        0.25,
                        0.3,
                        0.4,
                        1
                    ]
                )

                def make_dir_cb(p):
                    return lambda inst: load_directory(p)

                btn.bind(
                    on_release=make_dir_cb(full_path)
                )

                grid.add_widget(btn)

            for f in files:
                full_path = os.path.join(
                    target_path,
                    f
                )

                tex = self.load_safe_texture(
                    full_path
                )

                card = BoxLayout(
                    orientation="vertical",
                    size_hint_y=None,
                    height=dp(130),
                    padding=4,
                    spacing=2
                )

                with card.canvas.before:
                    Color(
                        0.2,
                        0.22,
                        0.28,
                        0.8
                    )

                    RoundedRectangle(
                        pos=card.pos,
                        size=card.size,
                        radius=[8]
                    )

                def update_card_bg(inst, val):
                    inst.canvas.before.clear()

                    with inst.canvas.before:
                        Color(
                            0.2,
                            0.22,
                            0.28,
                            0.8
                        )

                        RoundedRectangle(
                            pos=inst.pos,
                            size=inst.size,
                            radius=[8]
                        )

                card.bind(
                    pos=update_card_bg,
                    size=update_card_bg
                )

                if tex:
                    img_widget = Image(
                        texture=tex,
                        fit_mode="contain",
                        size_hint_y=0.75
                    )
                else:
                    img_widget = Label(
                        text="🖼️",
                        font_size="24sp",
                        size_hint_y=0.75
                    )

                name_lbl = Label(
                    text=f,
                    font_size="9sp",
                    size_hint_y=0.25,
                    halign="center",
                    valign="middle",
                    shorten=True,
                    shorten_from="right"
                )

                name_lbl.bind(
                    size=name_lbl.setter("text_size")
                )

                card.add_widget(img_widget)
                card.add_widget(name_lbl)

                select_btn = AnimatedButton(
                    size_hint=(1, 1),
                    background_color=[
                        0,
                        0,
                        0,
                        0
                    ]
                )

                cell = FloatLayout(
                    size_hint_y=None,
                    height=dp(130)
                )

                card.size_hint = (1, 1)
                card.pos_hint = {
                    "x": 0,
                    "y": 0
                }

                select_btn.pos_hint = {
                    "x": 0,
                    "y": 0
                }

                cell.add_widget(card)
                cell.add_widget(select_btn)

                def make_file_cb(p):
                    return lambda inst: (
                        self._on_bg_file_selected([p]),
                        popup.dismiss()
                    )

                select_btn.bind(
                    on_release=make_file_cb(full_path)
                )

                grid.add_widget(cell)

            if not dirs and not files:
                grid.add_widget(
                    Label(
                        text=(
                            "Folder is empty or "
                            "has no images"
                        ),
                        font_size="12sp"
                    )
                )

        def go_up(inst):
            parent = os.path.dirname(
                self.current_folder
            )

            if (
                parent
                and os.path.exists(parent)
            ):
                load_directory(parent)

        btn_up.bind(
            on_release=go_up
        )

        load_directory(
            self.current_folder
        )

        popup.open()


if __name__ == "__main__":
    FocusBuddyApp().run()