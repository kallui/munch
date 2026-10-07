# Third-party notices

MUNCH is MIT-licensed (see [`LICENSE`](LICENSE)). The Windows build bundles
the open-source components below, each under its own license. Their full
license texts are available at the linked projects.

| Component | Used for | License |
| --- | --- | --- |
| [Python](https://www.python.org/) | Runtime | PSF License |
| [Tcl/Tk](https://www.tcl-lang.org/) (via Tkinter) | Windows and widgets | Tcl/Tk License (BSD-style) |
| [OpenCV](https://opencv.org/) (`opencv-python`) | Webcam capture | Apache License 2.0 |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | Hand tracking, including the bundled Hand Landmarker model | Apache License 2.0 |
| [pynput](https://github.com/moses-palmer/pynput) | Mouse and keyboard control | GNU LGPL v3 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Speech recognition, including the Silero VAD model | MIT License |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | Speech model runtime | MIT License |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Speech filter runtime | MIT License |
| [PyAV](https://github.com/PyAV-Org/PyAV) | Audio support for faster-whisper | BSD 3-Clause |
| [FFmpeg](https://ffmpeg.org/) (bundled by PyAV) | Audio decoding libraries | GNU LGPL v2.1+ |
| [Hugging Face Hub](https://github.com/huggingface/huggingface_hub) | Speech model download | Apache License 2.0 |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) / [PortAudio](https://www.portaudio.com/) | Microphone input | MIT License |
| [NumPy](https://numpy.org/) | Array math | BSD 3-Clause (and bundled permissive licenses) |
| [Pillow](https://python-pillow.org/) | Image drawing | MIT-CMU (HPND) |
| [pygrabber](https://github.com/bunkahle/pygrabber) | Camera names | MIT License |
| [resvg-py](https://github.com/baseplate-admin/resvg-py) | Icon rendering | MIT / Apache 2.0 |
| [pywin32](https://github.com/mhammond/pywin32) | Windows overlay behavior | PSF License |
| [Tabler Icons](https://tabler.io/icons) | UI icons | MIT License, see [`assets/icons/NOTICE.md`](assets/icons/NOTICE.md) |

**Downloaded on first use, not bundled:** the Whisper `base.en` speech model
([Systran/faster-whisper-base.en](https://huggingface.co/Systran/faster-whisper-base.en),
converted from OpenAI's [Whisper](https://github.com/openai/whisper)), MIT License.

**LGPL components (pynput, FFmpeg):** these are included unmodified. Their
source code is available from the projects linked above. Because MUNCH itself
is open source, you can rebuild the app from this repository with a modified
or newer version of either library (see the build steps in the README).
