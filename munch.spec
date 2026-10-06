# PyInstaller spec for MUNCH — a standalone, no-Python-required .exe.
#
# Several bundled packages ship native binaries / data files PyInstaller's
# static import analysis can't see on its own (mediapipe's model-loading
# C++ core, faster-whisper's ctranslate2 backend, sounddevice's bundled
# PortAudio, pygrabber's DirectShow glue) — collect_all pulls each
# package's full data/binary/hidden-import set rather than guessing.
#
# Build: .venv\Scripts\pyinstaller.exe munch.spec

from PyInstaller.utils.hooks import collect_all

block_cipher = None

_COLLECT_PACKAGES = [
    "mediapipe", "cv2", "faster_whisper", "ctranslate2", "onnxruntime",
    "sounddevice", "pygrabber", "pynput", "resvg_py", "win32gui", "win32con",
]

datas = [
    ("munch/models/hand_landmarker.task", "munch/models"),
    ("assets/icon.png", "assets"),
    ("assets/icons", "assets/icons"),
]
binaries = []
hiddenimports = []

for package in _COLLECT_PACKAGES:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MUNCH",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
