"""
Android PC Controller receiver
Windows 10/11 | Wi-Fi WebSocket + Bluetooth Classic RFCOMM

Wi-Fi protocol:
    WebSocket on 0.0.0.0:8765
    One JSON object per WebSocket message (same as original receiver)

Bluetooth protocol:
    RFCOMM, newline-delimited JSON (each JSON object ends with \n)
    Uses the same event fields and Xbox 360 virtual gamepad mapping.
    Registered via Windows Winsock SDP with both Custom UUID and SPP UUID.
"""

import asyncio
import ctypes
from ctypes import wintypes
import json
import logging
import socket
import threading
import uuid

import vgamepad as vg
from websockets.asyncio.server import serve

# ---------------- Configuration ----------------

HOST = "0.0.0.0"
PORT = 8765

BLUETOOTH_ENABLED = True
BLUETOOTH_SERVICE_NAME = "Android PC Controller"
BLUETOOTH_SERVICE_UUID = "7a1f3c20-8b6d-4e51-a2c9-5f0d7b3e9101"
BLUETOOTH_SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"
PREFERRED_BT_CHANNEL = 4

MAX_BT_MESSAGE_BYTES = 8192

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

gamepad = vg.VX360Gamepad()
gamepad_lock = threading.RLock()
connections_lock = threading.Lock()
active_connections = 0

BUTTONS = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "SELECT": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "L3": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "R3": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "XBOX": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
}


def _number(value, default=0.0):
    """Convert finite numeric input safely; reject booleans and NaN/inf."""
    import math

    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def handle_event(event, send_pong=None):
    """Apply one event to the shared virtual Xbox controller."""
    if not isinstance(event, dict):
        return

    msg_type = event.get("type", "button")

    if msg_type == "ping":
        if send_pong is not None:
            send_pong({
                "type": "pong",
                "timestamp": event.get("timestamp"),
            })
        return

    with gamepad_lock:
        # Analog joystick
        if msg_type in ("joystick", "stick"):
            stick = event.get("stick")
            x = max(-1.0, min(1.0, _number(event.get("x", 0.0))))
            y = max(-1.0, min(1.0, _number(event.get("y", 0.0))))

            if stick == "left":
                gamepad.left_joystick_float(x_value_float=x, y_value_float=y)
            elif stick == "right":
                gamepad.right_joystick_float(x_value_float=x, y_value_float=y)
            else:
                return

            gamepad.update()
            return

        # Analog triggers
        if msg_type == "trigger":
            trigger = event.get("trigger")
            value = max(0.0, min(1.0, _number(event.get("value", 0.0))))

            if trigger == "LT":
                gamepad.left_trigger_float(value_float=value)
            elif trigger == "RT":
                gamepad.right_trigger_float(value_float=value)
            else:
                return

            gamepad.update()
            return

        # Digital buttons and trigger-as-button events
        name = event.get("button")
        action = event.get("action")

        if not isinstance(name, str) or action not in ("pressed", "released"):
            return

        name = name.upper()
        pressed = action == "pressed"

        if name == "LT":
            gamepad.left_trigger_float(value_float=1.0 if pressed else 0.0)
        elif name == "RT":
            gamepad.right_trigger_float(value_float=1.0 if pressed else 0.0)
        elif name in BUTTONS:
            if pressed:
                gamepad.press_button(button=BUTTONS[name])
            else:
                gamepad.release_button(button=BUTTONS[name])
        else:
            return

        gamepad.update()


def connection_opened():
    global active_connections
    with connections_lock:
        active_connections += 1
        logging.info("Active controller connections: %s", active_connections)


def connection_closed():
    """Reset the virtual pad only after the last transport disconnects."""
    global active_connections
    with connections_lock:
        active_connections = max(0, active_connections - 1)
        remaining = active_connections

    if remaining == 0:
        with gamepad_lock:
            gamepad.reset()
            gamepad.update()
        logging.info("All phones disconnected; controller state reset")
    else:
        logging.info(
            "One client disconnected; %s connection(s) remain", remaining
        )


async def handle_client(websocket):
    """Existing Wi-Fi WebSocket endpoint; protocol preserved."""
    remote = getattr(websocket, "remote_address", None)
    logging.info("Wi-Fi phone connected: %s", remote)
    connection_opened()

    try:
        async for message in websocket:
            try:
                event = json.loads(message)
                handle_event(
                    event,
                    send_pong=lambda pong: asyncio.create_task(
                        websocket.send(json.dumps(pong))
                    ),
                )
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logging.warning("Invalid Wi-Fi message: %s", exc)
            except Exception:
                logging.exception("Error processing Wi-Fi controller event")
    finally:
        logging.info("Wi-Fi phone disconnected: %s", remote)
        connection_closed()


# ---------------- Windows Bluetooth Winsock SDP ----------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]

class SOCKADDR_BTH(ctypes.Structure):
    _fields_ = [
        ("addressFamily", wintypes.USHORT),
        ("btAddr", ctypes.c_ulonglong),
        ("serviceClassId", GUID),
        ("port", wintypes.ULONG)
    ]

class SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [
        ("lpSockaddr", ctypes.POINTER(SOCKADDR_BTH)),
        ("iSockaddrLength", wintypes.INT)
    ]

class CSADDR_INFO(ctypes.Structure):
    _fields_ = [
        ("LocalAddr", SOCKET_ADDRESS),
        ("RemoteAddr", SOCKET_ADDRESS),
        ("iSocketType", wintypes.INT),
        ("iProtocol", wintypes.INT)
    ]

class WSAQUERYSETW(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("lpszServiceInstanceName", wintypes.LPWSTR),
        ("lpServiceClassId", ctypes.POINTER(GUID)),
        ("lpVersion", ctypes.c_void_p),
        ("lpszComment", wintypes.LPWSTR),
        ("dwNameSpace", wintypes.DWORD),
        ("lpNSProviderId", ctypes.c_void_p),
        ("lpszContext", wintypes.LPWSTR),
        ("dwNumberOfProtocols", wintypes.DWORD),
        ("lpafpProtocols", ctypes.c_void_p),
        ("lpszQueryString", wintypes.LPWSTR),
        ("dwNumberOfCsAddrs", wintypes.DWORD),
        ("lpcsaBuffer", ctypes.POINTER(CSADDR_INFO)),
        ("dwOutputFlags", wintypes.DWORD),
        ("lpBlob", ctypes.c_void_p)
    ]


def _str_to_guid(s):
    return GUID.from_buffer_copy(uuid.UUID(s).bytes_le)


class SDPRecord:
    """Retains pointers in memory to prevent garbage collection while advertised."""
    def __init__(self, port_channel, service_name, service_uuid_str):
        self.sa = SOCKADDR_BTH()
        self.sa.addressFamily = 32  # AF_BTH
        self.sa.btAddr = 0
        self.sa.serviceClassId = _str_to_guid(service_uuid_str)
        self.sa.port = port_channel

        self.cs = CSADDR_INFO()
        self.cs.LocalAddr.lpSockaddr = ctypes.pointer(self.sa)
        self.cs.LocalAddr.iSockaddrLength = ctypes.sizeof(self.sa)
        self.cs.iSocketType = socket.SOCK_STREAM
        self.cs.iProtocol = socket.BTPROTO_RFCOMM

        self.guid = _str_to_guid(service_uuid_str)
        self.service_name = service_name

        self.qs = WSAQUERYSETW()
        self.qs.dwSize = ctypes.sizeof(self.qs)
        self.qs.lpszServiceInstanceName = self.service_name
        self.qs.lpServiceClassId = ctypes.pointer(self.guid)
        self.qs.dwNameSpace = 16  # NS_BTH
        self.qs.dwNumberOfCsAddrs = 1
        self.qs.lpcsaBuffer = ctypes.pointer(self.cs)

        ret = ctypes.windll.ws2_32.WSASetServiceW(ctypes.byref(self.qs), 0, 0)  # RNRSERVICE_REGISTER = 0
        if ret != 0:
            err = ctypes.windll.ws2_32.WSAGetLastError()
            raise OSError(f"WSASetServiceW register failed with code {err}")

    def unregister(self):
        try:
            ctypes.windll.ws2_32.WSASetServiceW(ctypes.byref(self.qs), 2, 0)  # RNRSERVICE_DELETE = 2
        except Exception:
            pass


def bluetooth_server():
    """Bluetooth Classic RFCOMM listener using native Windows Winsock."""
    if not (hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM")):
        logging.warning("Native AF_BLUETOOTH not supported in this Python environment.")
        return

    server = None
    sdp_records = []

    try:
        server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)

        # Try binding to PREFERRED_BT_CHANNEL (4) first, or fall back to BT_PORT_ANY (-1)
        try:
            server.bind(("00:00:00:00:00:00", PREFERRED_BT_CHANNEL))
        except Exception:
            server.bind(("00:00:00:00:00:00", -1))  # BT_PORT_ANY

        server.listen(1)
        bt_addr, channel = server.getsockname()
        logging.info("Bluetooth adapter local address: %s, RFCOMM channel: %s", bt_addr, channel)

        # Register Custom Controller UUID SDP record
        try:
            rec1 = SDPRecord(channel, BLUETOOTH_SERVICE_NAME, BLUETOOTH_SERVICE_UUID)
            sdp_records.append(rec1)
            logging.info("Bluetooth SDP registered for Custom UUID: %s", BLUETOOTH_SERVICE_UUID)
        except Exception as exc:
            logging.warning("SDP registration (Custom UUID) warning: %s", exc)

        # Register Standard SPP UUID SDP record
        try:
            rec2 = SDPRecord(channel, f"{BLUETOOTH_SERVICE_NAME} SPP", BLUETOOTH_SPP_UUID)
            sdp_records.append(rec2)
            logging.info("Bluetooth SDP registered for SPP UUID: %s", BLUETOOTH_SPP_UUID)
        except Exception as exc:
            logging.warning("SDP registration (SPP UUID) warning: %s", exc)

        logging.info("Bluetooth RFCOMM ready for phone connections on channel %s", channel)

        while True:
            client, address = server.accept()
            logging.info("Bluetooth phone connected: %s", address)
            connection_opened()

            threading.Thread(
                target=handle_bluetooth_client,
                args=(client, address),
                daemon=True,
            ).start()

    except Exception as exc:
        logging.error("Bluetooth server error: %s", exc)
    finally:
        for rec in sdp_records:
            rec.unregister()
        if server is not None:
            try:
                server.close()
            except Exception:
                pass


def handle_bluetooth_client(client, address):
    """Read newline-delimited JSON over RFCOMM."""
    buffer = bytearray()
    try:
        client.settimeout(3.0)
        while True:
            try:
                chunk = client.recv(4096)
            except (TimeoutError, OSError) as exc:
                # Socket timeout is expected when client is idle
                if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower() or getattr(exc, "winerror", None) == 10060:
                    continue
                raise

            if not chunk:
                break

            buffer.extend(chunk)
            if len(buffer) > MAX_BT_MESSAGE_BYTES and b"\n" not in buffer:
                logging.warning("Oversized Bluetooth message from %s", address)
                break

            while b"\n" in buffer:
                raw, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)

                if not raw.strip():
                    continue
                if len(raw) > MAX_BT_MESSAGE_BYTES:
                    logging.warning("Skipping oversized Bluetooth event")
                    continue

                try:
                    event = json.loads(raw.decode("utf-8"))
                    def _send_bt_pong(pong_obj):
                        try:
                            client.send((json.dumps(pong_obj) + "\n").encode("utf-8"))
                        except Exception:
                            pass
                    handle_event(event, send_pong=_send_bt_pong)
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    logging.warning("Invalid Bluetooth message: %s", exc)
                except Exception:
                    logging.exception("Error processing Bluetooth event")

    except Exception:
        logging.info("Bluetooth connection ended: %s", address)
    finally:
        try:
            client.close()
        except Exception:
            pass
        connection_closed()


async def main():
    logging.info("Android PC Controller receiver starting")
    logging.info("Wi-Fi WebSocket server: ws://<PC-IP>:%s", PORT)

    if BLUETOOTH_ENABLED:
        threading.Thread(
            target=bluetooth_server,
            name="Bluetooth RFCOMM server",
            daemon=True,
        ).start()

    async with serve(handle_client, HOST, PORT, ping_interval=20, ping_timeout=20):
        logging.info("Wi-Fi WebSocket listening on %s:%s", HOST, PORT)
        logging.info("Press Ctrl+C to stop")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Stopping receiver...")
    finally:
        with gamepad_lock:
            gamepad.reset()
            gamepad.update()
