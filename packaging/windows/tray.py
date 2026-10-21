import ctypes
import os
import subprocess
import sys
import webbrowser
import winreg
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
PORT = 8000
URL = f"http://localhost:{PORT}"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Pinakes"
NO_WINDOW = 0x08000000

server: subprocess.Popen | None = None
job = None


def data_dir() -> Path:
    custom = os.environ.get("PINAKES_DATA_DIR")
    base = Path(custom) if custom else Path(os.environ["APPDATA"]) / "pinakes"
    base.mkdir(parents=True, exist_ok=True)
    return base


def single_instance() -> bool:
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\PinakesTray")
    return ctypes.windll.kernel32.GetLastError() != 183


class LimitInfo(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class ExtendedInfo(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", LimitInfo),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def bind_to_job(proc: subprocess.Popen) -> None:
    """系統匣結束時讓服務一併結束。"""
    global job
    kernel = ctypes.windll.kernel32
    kernel.CreateJobObjectW.restype = ctypes.c_void_p
    job = kernel.CreateJobObjectW(None, None)
    info = ExtendedInfo()
    info.BasicLimitInformation.LimitFlags = 0x2000
    kernel.SetInformationJobObject(
        ctypes.c_void_p(job), 9, ctypes.byref(info), ctypes.sizeof(info)
    )
    kernel.AssignProcessToJobObject(ctypes.c_void_p(job), ctypes.c_void_p(int(proc._handle)))


def start_server() -> None:
    global server
    env = os.environ.copy()
    env["PATH"] = str(ROOT / "ffmpeg" / "bin") + os.pathsep + env.get("PATH", "")
    log = open(data_dir() / "pinakes.log", "ab")
    server = subprocess.Popen(
        [
            str(ROOT / "python" / "python.exe"), "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0", "--port", str(PORT),
        ],
        cwd=ROOT / "backend", env=env, stdout=log, stderr=log,
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
    )
    bind_to_job(server)


def stop_server() -> None:
    if server and server.poll() is None:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()


def autostart_on() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def toggle_autostart(icon, item) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if autostart_on():
            winreg.DeleteValue(key, APP_NAME)
        else:
            exe = Path(sys.executable).with_name("pythonw.exe")
            cmd = f'"{exe}" "{ROOT / "tray.py"}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(79, 70, 229, 255))
    draw.polygon([(24, 18), (24, 46), (48, 32)], fill=(255, 255, 255, 255))
    return img


def open_web(icon=None, item=None) -> None:
    webbrowser.open(URL)


def open_logs(icon, item) -> None:
    os.startfile(data_dir())


def quit_app(icon, item) -> None:
    stop_server()
    icon.stop()


def main() -> None:
    if not single_instance():
        open_web()
        return
    start_server()
    menu = pystray.Menu(
        pystray.MenuItem("開啟 Pinakes", open_web, default=True),
        pystray.MenuItem("開機自動啟動", toggle_autostart, checked=lambda item: autostart_on()),
        pystray.MenuItem("開啟資料與記錄資料夾", open_logs),
        pystray.MenuItem("結束", quit_app),
    )
    icon = pystray.Icon(APP_NAME, make_icon(), "Pinakes", menu)
    icon.run()
    stop_server()


if __name__ == "__main__":
    main()
