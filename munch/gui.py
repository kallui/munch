"""MUNCH main window — Neo-Brutalist Tkinter UI.

Flat, loud colors; thick black borders; hard-offset "sticker" shadows;
bold uppercase type. No gradients, no rounded corners, no glow.
"""

import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from munch import calibration, config, settings
from munch.gesture_recognizer import GestureRecognizer, palm_center
from munch.hand_tracker import HandTracker
from munch.mouse_controller import MouseController
from munch.overlay import CalibrationOverlay, CursorHud
from munch.settings_window import SettingsWindow, detect_cameras
from munch.theme import (
    BG, BLUE, BORDER_W, FONT_BUTTON, FONT_STATUS, FONT_SUB, FONT_TITLE,
    GREEN, INK, PINK, SHADOW_OFFSET, YELLOW,
)

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

        self.munch_on = False
        self._last_frame_time = time.monotonic()
        self._fps = 0.0
        self._last_status_word = None
        self._settings_window = None
        self._available_cameras = None  # probed once, lazily, on first Settings open; cached after

        self.show_overlay_var = tk.BooleanVar(value=self._settings.get("show_overlay", True))

        self.last_landmarks = None
        self._calibration_step = 0  # 0 = idle, 1 = awaiting corner 1, 2 = awaiting corner 2
        self._calibration_points = []
        self._calibration_overlay = None

        self._build_ui()
        self._loop()

    def _build_settings_icon(self, parent):
        """A flat, hand-drawn "sliders" icon — three adjustable rows with
        knobs at different positions, the universal settings glyph — in
        place of a gear character, which renders inconsistently across
        fonts and never quite matched the rest of the app's flat,
        geometric, bordered-shape visual language."""
        size = 32
        canvas = tk.Canvas(parent, width=size, height=size, bg=INK, highlightthickness=0, cursor="hand2")
        for y, knob_x in ((10, 12), (16, 21), (22, 16)):
            canvas.create_line(6, y, size - 6, y, fill=YELLOW, width=2)
            canvas.create_oval(knob_x - 3, y - 3, knob_x + 3, y + 3, fill=YELLOW, outline=INK, width=1)
        canvas.bind("<Button-1>", lambda _event: self._open_settings())
        return canvas

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
            header_text, text="Motion User Navigation & Cursor Handling",
            font=FONT_SUB, bg=YELLOW, fg=INK,
        ).pack(anchor="w")

        self._build_settings_icon(header).place(relx=1.0, x=-10, rely=0.5, anchor="e")

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
        # gesture moves it to ACTIVE.
        self._toggle_panel = tk.Frame(control_front, bg=PINK, width=PANEL_W, height=button_h)
        self._toggle_panel.place(x=0, y=status_h + divider_h)
        self.toggle_button = tk.Button(
            self._toggle_panel, text="▶  ENABLE MUNCH", font=FONT_BUTTON,
            bg=PINK, fg=INK, activebackground=PINK, activeforeground=INK,
            relief="flat", bd=0, cursor="hand2", command=self._toggle,
        )
        self.toggle_button.place(x=0, y=0, width=PANEL_W, height=button_h)

    def _toggle(self):
        self.munch_on = not self.munch_on
        if self.munch_on:
            self.mouse.reset_smoothing()
            self.recognizer.reset_wake()  # always start a fresh session in standby
            self.toggle_button.configure(text="■  DISABLE MUNCH", bg=GREEN)
            self._toggle_panel.configure(bg=GREEN)
        else:
            self.toggle_button.configure(text="▶  ENABLE MUNCH", bg=PINK)
            self._toggle_panel.configure(bg=PINK)

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
            self.root, self.recognizer,
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
            self._update_status()

        self.root.after(config.LOOP_INTERVAL_MS, self._loop)

    def _update_cursor_hud(self):
        show = (
            self.munch_on
            and self.show_overlay_var.get()
            and self._calibration_step == 0
            and self.recognizer.current_gesture != "idle"
        )
        if show:
            x, y = self.mouse.get_position()
            self.cursor_hud.update(x, y, self.recognizer.current_gesture, self.recognizer.wake_progress)
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

        if not self.munch_on:
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
        if self._calibration_overlay:
            self._calibration_overlay.destroy()
        self.root.destroy()


def run():
    root = tk.Tk()
    MunchApp(root)
    root.mainloop()
