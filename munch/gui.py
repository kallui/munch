"""MUNCH main window — Neo-Brutalist Tkinter UI.

Flat, loud colors; thick black borders; hard-offset "sticker" shadows;
bold uppercase type. No gradients, no rounded corners, no glow.
"""

import os
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from munch import calibration, config, icons, settings
from munch.cheat_sheet import CheatSheet
from munch.gesture_recognizer import GestureRecognizer, palm_center
from munch.hand_tracker import HandTracker
from munch.keyboard_controller import KeyboardController
from munch.keyboard_overlay import KeyboardOverlay
from munch.mouse_controller import MouseController
from munch.overlay import CalibrationOverlay, CursorHud
from munch.settings_window import SettingsWindow, detect_cameras
from munch.side_dock import SideDock
from munch.speech_to_text import SpeechToText
from munch.theme import (
    BG, BLUE, BORDER_W, FONT_BUTTON, FONT_STATUS, FONT_SUB, FONT_TITLE,
    GREEN, INK, PINK, SHADOW_OFFSET, YELLOW,
)
from munch.widgets import RoundedButton, hover_tint

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")

# If the camera read fails this many consecutive frames, treat it as
# disconnected and show that state instead of silently doing nothing.
_CAMERA_FAILURE_LIMIT = 15
_CAMERA_RECONNECT_INTERVAL_MS = 2000

# Preview panel + status/toggle strips all share this width for a tidy,
# compact window instead of the earlier oversized layout.
PANEL_W = config.FRAME_WIDTH


def _shadow_panel(parent, width, height, bg):
    """A flat color panel with a thick black border and a hard-offset
    black shadow behind it — the core neo-brutalist "sticker" look."""
    container = tk.Frame(parent, bg=BG, width=width + SHADOW_OFFSET, height=height + SHADOW_OFFSET)
    container.pack_propagate(False)

    shadow = tk.Frame(container, bg=INK, width=width, height=height)
    shadow.place(x=SHADOW_OFFSET, y=SHADOW_OFFSET)

    front = tk.Frame(
        container, bg=bg, width=width, height=height,
        highlightbackground=INK, highlightthickness=BORDER_W,
    )
    front.place(x=0, y=0)

    return container, front


class MunchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MUNCH")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.screen_w = root.winfo_screenwidth()
        self.screen_h = root.winfo_screenheight()

        self._settings = settings.load()

        self.tracker = HandTracker()
        self.recognizer = GestureRecognizer()
        self.mouse = MouseController(self.screen_w, self.screen_h, zone=calibration.load_zone())
        self.camera_index = self._settings.get("camera_index", config.CAMERA_INDEX)
        self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cursor_hud = CursorHud(root)
        self._set_window_icon()

        self.munch_on = False
        self._last_frame_time = time.monotonic()
        self._fps = 0.0
        self._last_status_word = None
        self._settings_window = None
        self._cheat_sheet = None
        self._available_cameras = None  # probed once, lazily, on first Settings open; cached after

        self.show_overlay_var = tk.BooleanVar(value=self._settings.get("show_overlay", True))

        self.last_landmarks = None
        self._calibration_step = 0  # 0 = idle, 1 = awaiting corner 1, 2 = awaiting corner 2
        self._calibration_points = []
        self._calibration_overlay = None

        # Keyboard + dictation
        self.keyboard = KeyboardController()
        self.speech = SpeechToText()
        self._keyboard_overlay = None
        self.side_dock = SideDock(root, self._toggle_keyboard, self._toggle_mic)
        self._dock_visible = False

        # Camera robustness: a handful of consecutive bad reads is just
        # noise, but a long run means the device actually dropped — show
        # that state and retry periodically instead of freezing silently.
        self._camera_fail_streak = 0
        self._camera_lost = False
        self._last_reconnect_attempt = 0.0

        self._build_ui()
        self._loop()

    def _set_window_icon(self):
        try:
            icon_image = ImageTk.PhotoImage(Image.open(_ICON_PATH))
            self.root.iconphoto(True, icon_image)
            self._icon_image = icon_image  # keep a reference alive (avoid GC)
        except Exception:
            pass  # missing/unreadable icon asset shouldn't stop the app from starting

    def _build_icon_button(self, parent, icon_name, on_click, panel_bg=YELLOW):
        """A small rounded icon button using a real Tabler Icons glyph
        (see munch/icons.py) and the shared sticker-button interaction
        (see munch/widgets.py) instead of a hand-drawn flat square."""
        size = 28
        return RoundedButton(
            parent, size, size, color="white", on_click=on_click,
            icon_image=icons.load_icon(icon_name, INK, 18), bg=panel_bg,
        )

    def _open_cheat_sheet(self):
        if self._cheat_sheet is not None:
            try:
                self._cheat_sheet.win.lift()
                return
            except tk.TclError:
                self._cheat_sheet = None
        self._cheat_sheet = CheatSheet(self.root, self.recognizer)

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG, padx=14, pady=14)
        outer.pack()

        # Header (with a small settings gear in the corner). Height is
        # sized from Impact's actual measured line height (56px at this
        # size) + the subtitle's line + padding — Impact is a much taller
        # face than a normal Segoe UI weight, so a fixed guess clips the
        # subtitle under it if the title font ever changes again.
        header_container, header = _shadow_panel(outer, PANEL_W, 96, YELLOW)
        header_container.pack(pady=(0, 10))

        header_text = tk.Frame(header, bg=YELLOW)
        header_text.place(x=10, y=0, relheight=1.0)
        tk.Label(header_text, text="MUNCH", font=FONT_TITLE, bg=YELLOW, fg=INK).pack(anchor="w", pady=(8, 0))
        tk.Label(
            header_text, text="Motion-based User Navigation & Cursor Handling",
            font=FONT_SUB, bg=YELLOW, fg=INK,
        ).pack(anchor="w")

        self._build_icon_button(header, "settings", self._open_settings).place(
            relx=1.0, x=-10, rely=0.5, anchor="e"
        )
        self._build_icon_button(header, "info", self._open_cheat_sheet).place(
            relx=1.0, x=-50, rely=0.5, anchor="e"
        )

        # Webcam preview
        preview_container, preview_panel = _shadow_panel(
            outer, config.FRAME_WIDTH, config.FRAME_HEIGHT, INK
        )
        preview_container.pack(pady=(0, 10))
        self.video_label = tk.Label(preview_panel, bg=INK, bd=0)
        self.video_label.place(x=0, y=0, width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT)

        # One unified control card — status readout + the enable/disable
        # action share a single bordered sticker (one shadow, proportioned
        # to the whole card) instead of two separately-shadowed boxes.
        # Stacking a thin status strip in its own full sticker made its
        # border/shadow read as disproportionately heavy next to so little
        # content; a thin INK divider between the two tiers reads as one
        # deliberate card instead.
        status_h, divider_h, button_h = 34, 3, 48
        control_container, control_front = _shadow_panel(
            outer, PANEL_W, status_h + divider_h + button_h, INK
        )
        control_container.pack()

        status_frame = tk.Frame(control_front, bg=BLUE, width=PANEL_W, height=status_h)
        status_frame.place(x=0, y=0)
        status_row = tk.Frame(status_frame, bg=BLUE)
        # Left-aligned with fixed padding, not centered — centering would
        # shift the LED/text sideways every time the status word changes
        # length ("DISABLED" vs "ACTIVE" vs "STANDBY"), making the LED
        # jump around instead of sitting still.
        status_row.place(x=14, rely=0.5, anchor="w")

        self.status_led = tk.Canvas(status_row, width=14, height=14, bg=BLUE, highlightthickness=0)
        self.status_led.pack(side="left", padx=(0, 7))
        self._status_led_dot = self.status_led.create_oval(2, 2, 12, 12, fill="#888888", outline=INK)

        self.status_label = tk.Label(
            status_row, text="STANDBY   FPS: 0.0",
            font=FONT_STATUS, bg=BLUE, fg=INK,
        )
        self.status_label.pack(side="left")

        # Toggle button: ENABLE/DISABLE is the overall on/off; once
        # enabled, the status tier above shows STANDBY until the wake
        # gesture moves it to ACTIVE. A flat, full-bleed color strip —
        # no corner rounding, no shadow of its own — so it reads as part
        # of one card whose only shadow is the card's own outer one,
        # instead of a button nested inside a button.
        self._toggle_color = PINK
        self.toggle_button = tk.Label(
            control_front, text="▶  ENABLE MUNCH", font=FONT_BUTTON,
            bg=PINK, fg=INK, cursor="hand2",
        )
        self.toggle_button.place(x=0, y=status_h + divider_h, width=PANEL_W, height=button_h)
        self.toggle_button.bind("<Button-1>", lambda _e: self._toggle())
        self.toggle_button.bind("<Enter>", lambda _e: self.toggle_button.config(bg=hover_tint(self._toggle_color)))
        self.toggle_button.bind("<Leave>", lambda _e: self.toggle_button.config(bg=self._toggle_color))

    def _toggle(self):
        self.munch_on = not self.munch_on
        if self.munch_on:
            self.mouse.reset_smoothing()
            self.recognizer.reset_wake()  # always start a fresh session in standby
            self._toggle_color = GREEN
            self.toggle_button.config(bg=GREEN, text="■  DISABLE MUNCH")
        else:
            self._toggle_color = PINK
            self.toggle_button.config(bg=PINK, text="▶  ENABLE MUNCH")

    def _on_overlay_setting_changed(self):
        self._settings["show_overlay"] = self.show_overlay_var.get()
        settings.save(self._settings)
        if not self.show_overlay_var.get():
            self.cursor_hud.hide()

    def _open_settings(self):
        if self._settings_window is not None:
            try:
                self._settings_window.win.lift()
                return
            except tk.TclError:
                self._settings_window = None
        if self._available_cameras is None:
            self._available_cameras = detect_cameras()
        self._settings_window = SettingsWindow(
            self.root, self.recognizer, self.mouse,
            on_calibrate=self._on_calibrate_click,
            show_overlay_var=self.show_overlay_var,
            on_overlay_changed=self._on_overlay_setting_changed,
            camera_index=self.camera_index,
            available_cameras=self._available_cameras,
            on_camera_change=self._switch_camera,
        )

    def _switch_camera(self, new_index):
        if new_index == self.camera_index:
            return
        if self.capture.isOpened():
            self.capture.release()
        self.capture = cv2.VideoCapture(new_index, cv2.CAP_DSHOW)
        self.camera_index = new_index
        self._settings["camera_index"] = new_index
        settings.save(self._settings)

    # ------------------------------------------------------------------
    # On-screen keyboard + dictation, both reachable from the side dock
    # that only appears while MUNCH is armed (see _update_dock_visibility).
    def _toggle_keyboard(self):
        if self._keyboard_overlay is not None:
            self._keyboard_overlay.close()
            return
        self._keyboard_overlay = KeyboardOverlay(self.root, self.keyboard, self._on_keyboard_closed)
        self.side_dock.set_keyboard_state(True)

    def _on_keyboard_closed(self):
        self._keyboard_overlay = None
        self.side_dock.set_keyboard_state(False)

    def _toggle_mic(self):
        if self.speech.is_recording():
            self.side_dock.set_mic_state("transcribing")
            self.speech.stop_recording_and_transcribe(self._on_transcription_ready)
        else:
            self.speech.start_recording()
            self.side_dock.set_mic_state("recording")

    def _on_transcription_ready(self, text):
        # Called from the transcription background thread — hop back onto
        # the Tk thread before touching any widget or typing anything.
        self.root.after(0, lambda: self._finish_transcription(text))

    def _finish_transcription(self, text):
        self.side_dock.set_mic_state("idle")
        if text:
            self.keyboard.type_text(text)

    def _update_dock_visibility(self):
        should_show = self.munch_on and self.recognizer.armed
        if should_show and not self._dock_visible:
            self.side_dock.show()
            self._dock_visible = True
        elif not should_show and self._dock_visible:
            self.side_dock.hide()
            self._dock_visible = False

        if not should_show:
            # Dropping out of ARMED (disarmed, or MUNCH disabled outright)
            # means you've lost the gesture control that opened these —
            # leaving the keyboard open or a recording running would be
            # stuck state with no way back in without re-arming first.
            if self._keyboard_overlay is not None:
                self._toggle_keyboard()
            if self.speech.is_recording():
                self.speech.stop_recording_and_transcribe(lambda _text: None)
                self.side_dock.set_mic_state("idle")

    # ------------------------------------------------------------------
    # Calibration: started from Settings, but both corners are confirmed
    # with a quick thumb+index pinch (the same gesture as a left click)
    # so you don't need to touch the app again mid-flow.
    def _on_calibrate_click(self):
        if self._calibration_step != 0:
            return

        self._calibration_points = []
        self._calibration_step = 1
        self._calibration_overlay = CalibrationOverlay(self.root, on_cancel=self._cancel_calibration)
        self._calibration_overlay.set_text(
            "Quick pinch (thumb + index) at the top-left\nof your comfortable reach."
        )

    def _cancel_calibration(self):
        self._calibration_step = 0
        self._calibration_points = []
        if self._calibration_overlay:
            self._calibration_overlay.destroy()
            self._calibration_overlay = None

    def _handle_calibration_events(self, events):
        for event in events:
            if event[0] == "left_click":
                self._capture_calibration_point()
                break

    def _capture_calibration_point(self):
        if self.last_landmarks is None:
            return
        point = palm_center(self.last_landmarks)
        self._calibration_points.append((point[0], point[1]))

        if self._calibration_step == 1:
            self._calibration_step = 2
            self._calibration_overlay.set_text(
                "Top-left captured. Now pinch at the bottom-right."
            )
            return

        (x1, y1), (x2, y2) = self._calibration_points
        zone = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if calibration.is_valid(zone):
            calibration.save_zone(zone)
            self.mouse.set_zone(zone)
            self._calibration_overlay.set_text("Calibrated.")
        else:
            self._calibration_overlay.set_text("Corners too close. Try again.")

        self._calibration_step = 0
        self._calibration_points = []
        self.root.after(900, self._close_calibration_overlay)

    def _close_calibration_overlay(self):
        if self._calibration_overlay:
            self._calibration_overlay.destroy()
            self._calibration_overlay = None

    # ------------------------------------------------------------------
    def _loop(self):
        ok, frame = self.capture.read()

        if ok:
            self._camera_fail_streak = 0
            self._camera_lost = False
            try:
                frame = cv2.flip(frame, 1)
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))

                landmarks, annotated = self.tracker.process(frame)
                self.last_landmarks = landmarks
                events = self.recognizer.update(landmarks, bypass_arm=(self._calibration_step != 0))

                if self._calibration_step != 0:
                    self._handle_calibration_events(events)
                    norm_pos = palm_center(landmarks) if landmarks else None
                    self._calibration_overlay.update_tracking(norm_pos)
                elif self.munch_on:
                    self.mouse.handle_events(events)

                self._update_cursor_hud()
                self._render_frame(annotated)
            except Exception:
                # A single bad frame (corrupt read, a model hiccup)
                # shouldn't take the whole app down — skip it and
                # continue on the next tick.
                pass
        else:
            self._camera_fail_streak += 1
            if self._camera_fail_streak >= _CAMERA_FAILURE_LIMIT:
                self._camera_lost = True
                self._try_reconnect_camera()

        self._update_dock_visibility()
        self._update_status()
        self.root.after(config.LOOP_INTERVAL_MS, self._loop)

    def _try_reconnect_camera(self):
        now = time.monotonic()
        if now - self._last_reconnect_attempt < _CAMERA_RECONNECT_INTERVAL_MS / 1000:
            return
        self._last_reconnect_attempt = now
        if self.capture.isOpened():
            self.capture.release()
        self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

    def _update_cursor_hud(self):
        show = (
            self.munch_on
            and self.show_overlay_var.get()
            and self._calibration_step == 0
            and self.recognizer.current_gesture != "idle"
        )
        if show:
            x, y = self.mouse.get_position()
            self.cursor_hud.update(
                x, y, self.recognizer.current_gesture, self.recognizer.wake_progress,
                self.recognizer.last_scroll_ticks,
            )
        else:
            self.cursor_hud.hide()

    def _render_frame(self, frame_bgr):
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(image=photo)
        self._current_photo = photo  # keep a reference alive (avoid GC)

    def _update_status(self):
        now = time.monotonic()
        dt = now - self._last_frame_time
        self._last_frame_time = now
        if dt > 0:
            instant_fps = 1.0 / dt
            self._fps += (instant_fps - self._fps) * 0.2

        if self._camera_lost:
            led_color, word = "#FF3864", "CAMERA LOST"
        elif not self.munch_on:
            led_color, word = "#888888", "DISABLED"
        elif self.recognizer.armed:
            led_color, word = GREEN, "ACTIVE"
        else:
            led_color, word = YELLOW, "STANDBY"

        if word != self._last_status_word:
            self.status_led.itemconfig(self._status_led_dot, fill=led_color)
            self._last_status_word = word

        self.status_label.configure(text=f"{word}   FPS: {self._fps:0.1f}")

    # ------------------------------------------------------------------
    def _on_close(self):
        if self.capture.isOpened():
            self.capture.release()
        self.tracker.close()
        self.cursor_hud.destroy()
        self.side_dock.destroy()
        if self._keyboard_overlay:
            self._keyboard_overlay.close()
        if self._calibration_overlay:
            self._calibration_overlay.destroy()
        if self._settings_window:
            self._settings_window.close()
        if self._cheat_sheet:
            self._cheat_sheet.close()
        self.root.destroy()


def run():
    root = tk.Tk()
    MunchApp(root)
    root.mainloop()
