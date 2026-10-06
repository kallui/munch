"""Translates gesture events into real OS mouse actions via pynput.

Owns screen-coordinate mapping (active zone -> full screen) and EMA
smoothing for cursor movement.
"""

from pynput.mouse import Button, Controller

from munch import calibration, tuning


class MouseController:
    def __init__(self, screen_width, screen_height, zone=None):
        self._mouse = Controller()
        self._screen_w = screen_width
        self._screen_h = screen_height
        self._smoothed_x = None
        self._smoothed_y = None
        self.tuning = tuning.load_tuning()

        self.set_zone(zone or calibration.default_zone())

    def set_tuning(self, new_tuning):
        if tuning.is_valid(new_tuning):
            self.tuning = dict(new_tuning)

    def set_zone(self, zone):
        """zone = (x_min, y_min, x_max, y_max) in normalized frame coords;
        this rectangle maps to the full screen. Lets each user's calibrated
        reach (independent of camera position/angle) drive the mapping
        instead of a one-size-fits-all margin."""
        self._zone_x_min, self._zone_y_min, self._zone_x_max, self._zone_y_max = zone

    def handle_events(self, events):
        for event in events:
            kind = event[0]
            if kind == "move":
                self._move(event[1], event[2])
            elif kind == "left_click":
                self._mouse.click(Button.left, 1)
            elif kind == "left_down":
                self._mouse.press(Button.left)
            elif kind == "left_up":
                self._mouse.release(Button.left)
            elif kind == "right_click":
                self._mouse.click(Button.right, 1)
            elif kind == "right_down":
                self._mouse.press(Button.right)
            elif kind == "right_up":
                self._mouse.release(Button.right)
            elif kind == "middle_click":
                self._mouse.click(Button.middle, 1)
            elif kind == "middle_down":
                self._mouse.press(Button.middle)
            elif kind == "middle_up":
                self._mouse.release(Button.middle)
            elif kind == "double_click":
                self._mouse.click(Button.left, 2)
            elif kind == "scroll":
                self._scroll(event[1])

    def reset_smoothing(self):
        self._smoothed_x = None
        self._smoothed_y = None

    def get_position(self):
        return self._mouse.position

    def _move(self, norm_x, norm_y):
        zx = self._clamp01((norm_x - self._zone_x_min) / (self._zone_x_max - self._zone_x_min))
        zy = self._clamp01((norm_y - self._zone_y_min) / (self._zone_y_max - self._zone_y_min))

        target_x = zx * self._screen_w
        target_y = zy * self._screen_h

        alpha = self.tuning["cursor_smoothing_alpha"]
        prev_x, prev_y = self._smoothed_x, self._smoothed_y
        if prev_x is None or prev_y is None:
            smoothed_x, smoothed_y = target_x, target_y
        else:
            smoothed_x = prev_x + (target_x - prev_x) * alpha
            smoothed_y = prev_y + (target_y - prev_y) * alpha

        self._smoothed_x, self._smoothed_y = smoothed_x, smoothed_y
        self._mouse.position = (int(smoothed_x), int(smoothed_y))

    def _scroll(self, ticks):
        # `ticks` is already a small per-frame amount (see
        # config.SCROLL_SPEED_SCALE / SCROLL_MAX_SPEED); sent every frame
        # while the scroll pose is held, giving continuous scrolling.
        self._mouse.scroll(0, ticks)

    @staticmethod
    def _clamp01(v):
        return max(0.0, min(1.0, v))
