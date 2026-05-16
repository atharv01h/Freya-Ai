# ============================================================
# skills/system.py — System Controls
# CPU, RAM, volume, shutdown, screenshot, sleep
# ============================================================

import subprocess
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("freya.skills.system")


def get_cpu_usage() -> str:
    import psutil
    cpu = psutil.cpu_percent(interval=1)
    return f"CPU is at {cpu:.1f}%."


def get_ram_usage() -> str:
    import psutil
    mem = psutil.virtual_memory()
    used = mem.used / (1024 ** 3)
    total = mem.total / (1024 ** 3)
    pct = mem.percent
    return f"RAM: {used:.1f} GB used of {total:.1f} GB ({pct:.0f}%)."


def get_system_stats() -> str:
    import psutil
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    ram_pct = mem.percent
    disk_pct = disk.percent
    return (
        f"System status — CPU: {cpu:.0f}%, "
        f"RAM: {ram_pct:.0f}%, "
        f"Disk C: {disk_pct:.0f}% used."
    )


def get_battery() -> str:
    import psutil
    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery sensor found."
    status = "charging" if battery.power_plugged else "discharging"
    return f"Battery at {battery.percent:.0f}%, {status}."


def take_screenshot(save_dir: str = "screenshots") -> str:
    try:
        import mss
        Path(save_dir).mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(Path(save_dir) / f"screenshot_{ts}.png")
        with mss.mss() as sct:
            sct.shot(output=path)
        return f"Screenshot saved to {path}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def volume_up(amount: int = 10) -> str:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        import math

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        current_db = volume.GetMasterVolumeLevel()
        # dB range is typically -65.25 to 0
        scalar = volume.GetMasterVolumeLevelScalar()
        new_scalar = min(1.0, scalar + amount / 100.0)
        volume.SetMasterVolumeLevelScalar(new_scalar, None)
        return f"Volume increased to {int(new_scalar * 100)}%."
    except ImportError:
        _press_volume_key("up", amount // 2)
        return f"Volume raised."
    except Exception as e:
        logger.error("Volume up error: %s", e)
        return "Couldn't adjust volume."


def volume_down(amount: int = 10) -> str:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = volume.GetMasterVolumeLevelScalar()
        new_scalar = max(0.0, scalar - amount / 100.0)
        volume.SetMasterVolumeLevelScalar(new_scalar, None)
        return f"Volume lowered to {int(new_scalar * 100)}%."
    except ImportError:
        _press_volume_key("down", amount // 2)
        return "Volume lowered."
    except Exception as e:
        logger.error("Volume down error: %s", e)
        return "Couldn't adjust volume."


def mute_volume() -> str:
    try:
        import pyautogui
        pyautogui.press("volumemute")
        return "Muted."
    except Exception as e:
        return f"Mute failed: {e}"


def _press_volume_key(direction: str, times: int):
    try:
        import pyautogui
        key = "volumeup" if direction == "up" else "volumedown"
        for _ in range(max(1, times)):
            pyautogui.press(key)
            time.sleep(0.05)
    except Exception as e:
        logger.error("Volume key press: %s", e)


def shutdown_pc() -> str:
    subprocess.run(["shutdown", "/s", "/t", "10"], shell=True)
    return "Shutting down in 10 seconds. Say 'cancel shutdown' to abort."


def cancel_shutdown() -> str:
    subprocess.run(["shutdown", "/a"], shell=True)
    return "Shutdown cancelled."


def restart_pc() -> str:
    subprocess.run(["shutdown", "/r", "/t", "10"], shell=True)
    return "Restarting in 10 seconds."


def sleep_pc() -> str:
    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return "Going to sleep."


def open_task_manager() -> str:
    subprocess.Popen("taskmgr.exe")
    return "Task Manager opened."


def list_running_processes(top: int = 10) -> str:
    import psutil
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            procs.append({
                "name": p.info["name"],
                "cpu": p.info["cpu_percent"],
                "ram_mb": p.info["memory_info"].rss / (1024 ** 2),
            })
        except Exception:
            pass
    procs.sort(key=lambda x: x["ram_mb"], reverse=True)
    lines = [f"{p['name']}: {p['ram_mb']:.0f} MB RAM" for p in procs[:top]]
    return "Top processes:\n" + "\n".join(lines)
