import subprocess
from pathlib import Path

TEST_TIMEOUT = 15
VAAPI_DEVICE = "/dev/dri/renderD128"
ORDER = ("nvenc", "vaapi", "qsv")
ENCODERS = {"nvenc": "h264_nvenc", "vaapi": "h264_vaapi", "qsv": "h264_qsv"}

_cache: dict[tuple[str, str], str | None] = {}


def _list_encoders(ffmpeg: str) -> str:
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=TEST_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout


def pre_args(kind: str) -> list[str]:
    if kind == "vaapi":
        return ["-vaapi_device", VAAPI_DEVICE]
    if kind == "qsv":
        return ["-init_hw_device", "qsv=hw", "-filter_hw_device", "hw"]
    return []


def video_args(kind: str) -> list[str]:
    """回傳硬體編碼的影像參數。"""
    keys = ["-force_key_frames", "expr:gte(t,n_forced*4)"]
    if kind == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23",
                "-pix_fmt", "yuv420p", *keys]
    if kind == "vaapi":
        return ["-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-qp", "23", *keys]
    if kind == "qsv":
        return ["-vf", "format=nv12,hwupload=extra_hw_frames=64",
                "-c:v", "h264_qsv", "-global_quality", "23", *keys]
    raise ValueError(kind)


def _works(ffmpeg: str, kind: str) -> bool:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", *pre_args(kind),
           "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2:r=10"]
    cmd += video_args(kind) + ["-frames:v", "2", "-f", "null", "-"]
    try:
        done = subprocess.run(
            cmd, capture_output=True, timeout=TEST_TIMEOUT, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def detect(ffmpeg: str, preference: str = "auto") -> str | None:
    """依設定與實測結果選出可用的硬體編碼，沒有則回傳 None。"""
    if preference == "off":
        return None
    key = (ffmpeg, preference)
    if key in _cache:
        return _cache[key]
    listed = _list_encoders(ffmpeg)
    kinds = ORDER if preference == "auto" else (preference,)
    found = None
    for kind in kinds:
        if kind not in ENCODERS or ENCODERS[kind] not in listed:
            continue
        if kind == "vaapi" and not Path(VAAPI_DEVICE).exists():
            continue
        if _works(ffmpeg, kind):
            found = kind
            break
    _cache[key] = found
    return found


def reset() -> None:
    _cache.clear()
