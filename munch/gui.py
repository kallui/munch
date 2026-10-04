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

# --- Neo-brutalist palette ---
BG = "#F5F1E6"       # paper background
INK = "#111111"      # near-black, used for borders/text
YELLOW = "#FFD400"
PINK = "#FF3DAE"
BLUE = "#3A86FF"
GREEN = "#06D6A0"
RED = "#FF3864"
PURPLE = "#8338EC"

FONT_TITLE = ("Segoe UI Black", 26, "bold")
FONT_SUB = ("Segoe UI", 10, "bold")
FONT_STATUS = ("Consolas", 12, "bold")
FONT_BUTTON = ("Segoe UI", 16, "bold")

BORDER_W = 4
SHADOW_OFFSET = 6


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

        self.tracker = HandTracker()
        self.recognizer = GestureRecognizer()
        self.mouse = MouseController(self.screen_w, self.screen_h, zone=calibration.load_zone())
        self.capture = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cursor_hud = CursorHud(root)

        self._settings = settings.load()
        self.munch_on = False
        self._last_frame_time = time.monotonic()
        self._fps = 0.0
        self._last_status_word = None

        self.last_landmarks = None
        self._calibration_step = 0  # 0 = idle, 1 = awaiting corner 1, 2 = awaiting corner 2
        self._calibration_points = []
        self._calibration_overlay = None

        self._build_ui()
        self._loop()

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=BG, padx=20, pady=20)
        outer.pack()

        # Header
        header_container, header = _shadow_panel(outer, 600, 90, YELLOW)
        header_container.pack(pady=(0, 16))
        tk.Label(header, text="MUNCH", font=FONT_TITLE, bg=YELLOW, fg=INK).pack(pady=(10, 0))
        tk.Label(
            header,
            text="MOTION USER NAVIGATION & CURSOR HANDLING",
            font=FONT_SUB, bg=YELLOW, fg=INK,
        ).pack()

        # Webcam preview
        preview_container, preview_panel = _shadow_panel(
            outer, config.FRAME_WIDTH, config.FRAME_HEIGHT, INK
        )
        preview_container.pack(pady=(0, 16))
        self.video_label = tk.Label(preview_panel, bg=INK, bd=0)
        self.video_label.place(x=0, y=0, width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT)

        # Status strip: a small LED (grey = watching, green = armed) plus
        # a calm, rarely-changing status word and FPS — no raw per-frame
        # gesture name here, since that changes every frame and just reads
        # as noise.
        status_container, status_panel = _shadow_panel(outer, 600, 44, BLUE)
        status_container.pack(pady=(0, 16))
        status_row = tk.Frame(status_panel, bg=BLUE)
        status_row.pack(expand=True)

        self.status_led = tk.Canvas(status_row, width=16, height=16, bg=BLUE, highlightthickness=0)
        self.status_led.pack(side="left", padx=(0, 8))
        self._status_led_dot = self.status_led.create_oval(3, 3, 13, 13, fill="#888888", outline=INK)

        self.status_label = tk.Label(
            status_row, text="WATCHING   FPS: 0.0",
            font=FONT_STATUS, bg=BLUE, fg=INK,
        )
        self.status_label.pack(side="left")

        # Toggle button
        toggle_container, toggle_panel = _shadow_panel(outer, 600, 64, PINK)
        toggle_container.pack()
        self.toggle_button = tk.Button(
            toggle_panel, text="▶  START MUNCH MODE", font=FONT_BUTTON,
            bg=PINK, fg=INK, activebackground=PINK, activeforeground=INK,
            relief="flat", bd=0, cursor="hand2", command=self._toggle,
        )
        self.toggle_button.place(x=0, y=0, width=600, height=64)
        self._toggle_panel = toggle_panel

        # Calibrate button
        calib_container, calib_panel = _shadow_panel(outer, 600, 56, PURPLE)
        calib_container.pack(pady=(16, 0))
        self.calib_button = tk.Button(
            calib_panel, text="⌖  CALIBRATE REACH", font=FONT_BUTTON,
            bg=PURPLE, fg="white", activebackground=PURPLE, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", command=self._on_calibrate_click,
        )
        self.calib_button.place(x=0, y=0, width=600, height=56)

        # Overlay toggle
        self.show_overlay_var = tk.BooleanVar(value=self._settings.get("show_overlay", True))
        overlay_check = tk.Checkbutton(
            outer, text="SHOW GESTURE OVERLAY ON CURSOR", variable=self.show_overlay_var,
            command=self._on_overlay_setting_changed, font=FONT_SUB,
            bg=BG, fg=INK, activebackground=BG, selectcolor=BG, bd=0,
            highlightthickness=0,
        )
        overlay_check.pack(pady=(14, 0))

    def _toggle(self):
        self.munch_on = not self.munch_on
        if self.munch_on:
            self.mouse.reset_smoothing()
            self.recognizer.reset_wake()  # always start a fresh session "watching"
            self.toggle_button.configure(text="■  STOP MUNCH MODE", bg=GREEN)
            self._toggle_panel.configure(bg=GREEN)
        else:
            self.toggle_button.configure(text="▶  START MUNCH MODE", bg=PINK)
            self._toggle_panel.configure(bg=PINK)

    def _on_overlay_setting_changed(self):
        self._settings["show_overlay"] = self.show_overlay_var.get()
        settings.save(self._settings)
        if not self.show_overlay_var.get():
            self.cursor_hud.hide()

    # ------------------------------------------------------------------
    # Calibration: started by one button click, but both corners are
    # confirmed with a quick thumb+index pinch (the same gesture as a
    # left click) so you don't need to touch the app again mid-flow.
    def _on_calibrate_click(self):
        if self._calibration_step != 0:
            return

        self._calibration_points = []
        self._calibration_step = 1
        self._calibration_overlay = CalibrationOverlay(self.root, on_cancel=self._cancel_calibration)
        self._calibration_overlay.set_text(
            "QUICK PINCH (THUMB + INDEX)\nAT ONE CORNER OF YOUR COMFORTABLE REACH"
        )
        self.calib_button.configure(text="CALIBRATING… (ESC TO CANCEL)")

    def _cancel_calibration(self):
        self._calibration_step = 0
        self._calibration_points = []
        if self._calibration_overlay:
            self._calibration_overlay.destroy()
            self._calibration_overlay = None
        self.calib_button.configure(text="⌖  CALIBRATE REACH")

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
                "CORNER 1 CAPTURED ✓\nNOW QUICK-PINCH AT THE OPPOSITE CORNER"
            )
            return

        (x1, y1), (x2, y2) = self._calibration_points
        zone = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if calibration.is_valid(zone):
            calibration.save_zone(zone)
            self.mouse.set_zone(zone)
            self._calibration_overlay.set_text("✓  CALIBRATED")
        else:
            self._calibration_overlay.set_text("CORNERS TOO CLOSE — TRY AGAIN")

        self._calibration_step = 0
        self._calibration_points = []
        self.calib_button.configure(text="⌖  CALIBRATE REACH")
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
            led_color, word = "#888888", "MUNCH OFF"
        elif self.recognizer.armed:
            led_color, word = GREEN, "ARMED"
        else:
            led_color, word = "#888888", "WATCHING"

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
