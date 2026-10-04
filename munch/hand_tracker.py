"""Thin wrapper around MediaPipe's HandLandmarker (Tasks API) for
single-hand landmark detection, with manual overlay drawing (the old
mediapipe.solutions drawing helpers no longer exist in this API)."""

import os
import time

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from munch import config

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "hand_landmarker.task")

_CONNECTIONS = vision.HandLandmarksConnections.HAND_CONNECTIONS
_LANDMARK_COLOR = (0, 255, 255)   # yellow-ish (BGR) dots
_CONNECTION_COLOR = (255, 0, 180)  # pink (BGR) lines


class HandTracker:
    def __init__(self):
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=config.MAX_NUM_HANDS,
            min_hand_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._start_time = time.monotonic()

    def process(self, frame_bgr):
        """Returns (landmarks_or_None, annotated_frame_bgr).

        landmarks is a list of 21 (x, y, z) normalized tuples for the first
        detected hand, or None if no hand is detected.
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        timestamp_ms = int((time.monotonic() - self._start_time) * 1000)

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        annotated = frame_bgr
        landmarks = None

        if result.hand_landmarks:
            hand = result.hand_landmarks[0]
            landmarks = [(lm.x, lm.y, lm.z) for lm in hand]
            self._draw(annotated, landmarks)

        return landmarks, annotated

    @staticmethod
    def _draw(frame, landmarks):
        h, w = frame.shape[:2]
        points = [(int(x * w), int(y * h)) for x, y, _ in landmarks]

        for connection in _CONNECTIONS:
            cv2.line(frame, points[connection.start], points[connection.end], _CONNECTION_COLOR, 2)
        for point in points:
            cv2.circle(frame, point, 4, _LANDMARK_COLOR, -1)

    def close(self):
        self._landmarker.close()
