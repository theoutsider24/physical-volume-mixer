import serial
import time
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

DELIMITER = "#"

SYSTEM_SOUNDS = 0
MASTER_VOLUME = 1
active_pid = MASTER_VOLUME

button_down = False
volume_val = 0


devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume_control = cast(interface, POINTER(IAudioEndpointVolume))

ser = serial.Serial("COM3", 9600, timeout=0.02)


class ApplicationClosedException(Exception):
    pass


def get_sessions_without_duplicate_pids():
    sessions = AudioUtilities.GetAllSessions()
    seen_pids = set()
    new_list = []
    for sess in sessions:
        if not sess.Process or sess.Process.pid not in seen_pids:
            new_list.append(sess)
            if sess.Process:
                seen_pids.add(sess.Process.pid)
    return new_list


def get_session_by_pid(pid):
    # The first element is system sounds which doesn't have a pid
    try:
        return list(
            filter(lambda x: x.Process.pid == pid, get_sessions_without_duplicate_pids()[1:])
        )[-1]
    except:
        raise ApplicationClosedException


def set_active_session_volume(volume):
    if get_active_session_mute() == 1:
        set_active_session_mute(0)
    if active_pid == MASTER_VOLUME:
        volume_control.SetMasterVolumeLevelScalar(volume, None)
    elif active_pid == SYSTEM_SOUNDS:
        get_sessions_without_duplicate_pids()[0].SimpleAudioVolume.SetMasterVolume(volume, None)
    else:
        get_session_by_pid(active_pid).SimpleAudioVolume.SetMasterVolume(volume, None)


def get_active_session_volume():
    if get_active_session_mute() == 1:
        return 0
    if active_pid == MASTER_VOLUME:
        return volume_control.GetMasterVolumeLevelScalar()
    elif active_pid == SYSTEM_SOUNDS:
        return get_sessions_without_duplicate_pids()[0].SimpleAudioVolume.GetMasterVolume()
    else:
        return get_session_by_pid(active_pid).SimpleAudioVolume.GetMasterVolume()


def get_active_session_mute():
    if active_pid == MASTER_VOLUME:
        return volume_control.GetMute()
    elif active_pid == SYSTEM_SOUNDS:
        return get_sessions_without_duplicate_pids()[0].SimpleAudioVolume.GetMute()
    else:
        return get_session_by_pid(active_pid).SimpleAudioVolume.GetMute()


def set_active_session_mute(mute):
    assert mute in [0, 1]
    if active_pid == MASTER_VOLUME:
        return volume_control.SetMute(mute, None)
    elif active_pid == SYSTEM_SOUNDS:
        return get_sessions_without_duplicate_pids()[0].SimpleAudioVolume.SetMute(mute, None)
    else:
        return get_session_by_pid(active_pid).SimpleAudioVolume.SetMute(mute, None)


def get_active_session_name():
    if active_pid == MASTER_VOLUME:
        return "Master"
    elif active_pid == SYSTEM_SOUNDS:
        return "System Sounds"
    else:
        process_name = str(get_session_by_pid(active_pid).Process.name())
        if process_name.endswith(".exe"):
            process_name = process_name[:-4]
        return process_name.title()


def get_next_session():
    global active_pid
    all_sessions = get_sessions_without_duplicate_pids()
    if active_pid == MASTER_VOLUME:
        active_pid = SYSTEM_SOUNDS
    elif active_pid == SYSTEM_SOUNDS:
        if len(all_sessions) > 1:
            active_pid = all_sessions[1].Process.pid
        else:
            active_pid = MASTER_VOLUME
    else:
        next_pid_found = False
        for i, sess in enumerate(all_sessions):
            if i == 0:
                continue
            if next_pid_found:
                break
            if sess.Process.pid == active_pid:
                if i == len(all_sessions) - 1:
                    # last one, loop back
                    active_pid = MASTER_VOLUME
                    next_pid_found = True
                else:
                    active_pid = all_sessions[i + 1].Process.pid
                    next_pid_found = True
        if not next_pid_found:
            active_pid = MASTER_VOLUME


def get_last_session():
    global active_pid
    all_sessions = get_sessions_without_duplicate_pids()
    if active_pid == MASTER_VOLUME:
        if len(all_sessions) > 1:
            active_pid = all_sessions[-1].Process.pid
        else:
            active_pid = SYSTEM_SOUNDS
    elif active_pid == SYSTEM_SOUNDS:
        active_pid = MASTER_VOLUME
    else:
        next_pid_found = False
        for i, sess in enumerate(all_sessions):
            if i == 0:
                continue
            if next_pid_found:
                break
            if sess.Process.pid == active_pid:
                if i == 1:
                    # first one, step back
                    active_pid = SYSTEM_SOUNDS
                    next_pid_found = True
                else:
                    active_pid = all_sessions[i - 1].Process.pid
                    next_pid_found = True
        if not next_pid_found:
            active_pid = MASTER_VOLUME


def set_volume_scalar(volume):
    volume = min(max(volume, 0), 1)
    volume_control.SetMasterVolumeLevelScalar(volume, None)


def set_mute(mute):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
        volume.SetMute(mute, None)


def sendLine(prefix, line):
    ser.write((prefix + ":" + str(line) + DELIMITER).encode())


def sendState():
    vol = int(get_active_session_volume() * 100)
    sendLine("VOL", vol)
    sendLine("APP", get_active_session_name())


def listen_and_respond():
    global button_down, volume_val, active_pid
    sendState()
    while True:
        val = ser.readline().strip().decode()
        try:
            if "CLICK+" in val:
                print(f"Changing session+: {active_pid}")
                get_next_session()
                sendState()
                volume_val = 0
            elif "CLICK-" in val:
                print(f"Changing session-: {active_pid}")
                get_last_session()
                print(active_pid)
                sendState()
                volume_val = 0
            elif "MUTE" in val:
                if get_active_session_mute():
                    set_active_session_mute(0)
                else:
                    set_active_session_mute(1)
            elif "INIT" in val:
                sendState()
            elif val:
                print(f"Incoming: {val}")
                set_active_session_volume(int(val) / 100)
            else:
                vol = int(get_active_session_volume() * 100)
                if vol != volume_val:
                    sendLine("VOL", vol)
                    print(vol)
                    volume_val = vol
        except ApplicationClosedException:
            active_pid = MASTER_VOLUME


time.sleep(2)  # wait for the serial connection to initialize

listen_and_respond()
