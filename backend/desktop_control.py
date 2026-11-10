import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import sys

BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
NAME = "Local\\iTime-" + hashlib.sha256(str(BASE).casefold().encode()).hexdigest()[:20]
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
for name, args, result in (
    ("CreateMutexW", [ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR],wintypes.HANDLE),
    ("OpenMutexW",[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR],wintypes.HANDLE),
    ("CreateEventW",[ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR],wintypes.HANDLE),
    ("OpenEventW",[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR],wintypes.HANDLE),
    ("SetEvent",[wintypes.HANDLE],wintypes.BOOL),
    ("ReleaseMutex",[wintypes.HANDLE],wintypes.BOOL),
    ("CloseHandle",[wintypes.HANDLE],wintypes.BOOL),
    ("WaitForSingleObject",[wintypes.HANDLE,wintypes.DWORD],wintypes.DWORD),
):
    function = getattr(kernel,name)
    function.argtypes, function.restype = args,result

def message(text, error=False):
    ctypes.windll.user32.MessageBoxW(None,text,"iTime 工时管理",0x10 if error else 0x40)

def stop():
    event = kernel.OpenEventW(0x100002,False,NAME+"-stop")
    if not event:
        message("当前没有由本目录启动的服务。")
        return
    mutex = kernel.OpenMutexW(0x100001,False,NAME+"-running")
    try:
        if not kernel.SetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        result = kernel.WaitForSingleObject(mutex,30000) if mutex else 0
        if result in (0,0x80):
            if mutex: kernel.ReleaseMutex(mutex)
            message("前后端服务已关闭。")
        else:
            message("关闭请求已发送，服务仍在处理任务，请稍后再检查。",True)
    finally:
        kernel.CloseHandle(event)
        if mutex: kernel.CloseHandle(mutex)

def check_control():
    import uuid
    name = NAME + "-check-" + uuid.uuid4().hex
    mutex = kernel.CreateMutexW(None, True, name)
    assert mutex
    event = duplicate = None
    try:
        duplicate = kernel.CreateMutexW(None, False, name)
        assert duplicate and ctypes.get_last_error() == 183
        event = kernel.CreateEventW(None, True, False, name+"-event")
        assert event and kernel.WaitForSingleObject(event, 0) == 258
        assert kernel.SetEvent(event)
        assert kernel.WaitForSingleObject(event, 0) == 0
    finally:
        if event: kernel.CloseHandle(event)
        if duplicate: kernel.CloseHandle(duplicate)
        kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)
    return True
