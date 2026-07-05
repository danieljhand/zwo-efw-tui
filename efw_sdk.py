"""
ZWO EFW SDK wrapper using ctypes.

Provides a thin, safe Python interface over the native C library.
"""

import ctypes
import ctypes.util
import os
import platform
import sys
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Platform / library detection
# ---------------------------------------------------------------------------

# Local lib/ directory — populated by scripts/install_sdk.sh.
# Not tracked in git; see README for setup instructions.
_LIB_DIR = Path(__file__).resolve().parent / "lib"


def _find_lib() -> Path:
    """Locate the EFW SDK shared library.

    Search order:
      1. lib/<platform>/ alongside this file (populated by install_sdk.sh)
      2. EFW_SDK_DIR environment variable pointing to the SDK lib/ directory
      3. System library paths via ctypes.util.find_library

    Raises OSError for unsupported platforms, FileNotFoundError if the
    library cannot be located.
    """
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin":
        subdir = "mac_arm64" if "arm" in machine else "mac_x64"
        lib_name = "libEFWFilter.dylib"
    elif system == "Linux":
        raise OSError(
            "Linux is not yet supported by this project.\n"
            "macOS (arm64 and x86_64) is the only supported platform at this time."
        )
    elif system == "Windows":
        raise OSError(
            "Windows is not yet supported by this project.\n"
            "macOS (arm64 and x86_64) is the only supported platform at this time."
        )
    else:
        raise OSError(f"Unsupported platform: {system} ({machine})")

    # 1. Local lib/ directory (install_sdk.sh)
    local = _LIB_DIR / subdir / lib_name
    if local.exists():
        return local

    # 2. EFW_SDK_DIR environment variable
    sdk_env = os.environ.get("EFW_SDK_DIR")
    if sdk_env:
        env_path = Path(sdk_env) / subdir / lib_name
        if env_path.exists():
            return env_path

    # 3. System library paths
    found = ctypes.util.find_library("EFWFilter")
    if found:
        return Path(found)

    raise FileNotFoundError(
        f"EFW SDK library not found ({system}/{machine}).\n"
        f"  Expected at: {local}\n"
        f"  Run:         ./scripts/install_sdk.sh <path-to-extracted-sdk>\n"
        f"  Or set:      EFW_SDK_DIR=<sdk-root>/efw/lib\n"
        f"  Download:    https://releaselog.zwoastro.com/efw"
    )


# ---------------------------------------------------------------------------
# Load library and bind function signatures
# ---------------------------------------------------------------------------

_lib_path = _find_lib()
_lib = ctypes.CDLL(str(_lib_path))

# --- Structs ---


class EFW_INFO(ctypes.Structure):
    _fields_ = [
        ("ID", ctypes.c_int),
        ("Name", ctypes.c_char * 64),
        ("slotNum", ctypes.c_int),
    ]


class EFW_SN(ctypes.Structure):
    _fields_ = [("id", ctypes.c_ubyte * 8)]


# --- Error codes ---


class EFWError(Exception):
    """Raised when an EFW SDK call returns a non-success error code."""

    def __init__(self, code: int, func_name: str):
        self.code = code
        self.func_name = func_name
        messages = {
            0: "Success",
            1: "Invalid index",
            2: "Invalid ID",
            3: "Invalid value",
            4: "Device removed",
            5: "Device is moving",
            6: "Error state",
            7: "General error",
            8: "Not supported",
            9: "Invalid length",
            10: "Device closed",
            -1: "End of error codes",
        }
        super().__init__(f"{func_name} failed (code {code}): {messages.get(code, 'Unknown')}")


# --- Bind functions ---


def _errcheck(result: int, func, args: tuple, **kwargs) -> tuple:
    """ctypes errcheck — raises EFWError on non-zero return."""
    if result != 0:
        raise EFWError(result, func.__name__)
    return args


# Helper to bind a function with errcheck
def _bind(name: str, restype, argtypes: list):
    fn = getattr(_lib, name)
    fn.restype = restype
    fn.argtypes = argtypes
    fn.errcheck = _errcheck
    return fn


# Core device functions
# EFWGetNum returns the device count directly (not an error code), so we bind it without errcheck
fn = getattr(_lib, "EFWGetNum")
fn.restype = ctypes.c_int
fn.argtypes = []
efw_get_num = fn
efw_get_id = _bind("EFWGetID", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(ctypes.c_int)])
efw_open = _bind("EFWOpen", ctypes.c_int, [ctypes.c_int])
efw_close = _bind("EFWClose", ctypes.c_int, [ctypes.c_int])
efw_get_property = _bind("EFWGetProperty", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(EFW_INFO)])
efw_get_position = _bind("EFWGetPosition", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(ctypes.c_int)])
efw_set_position = _bind("EFWSetPosition", ctypes.c_int, [ctypes.c_int, ctypes.c_int])
efw_calibrate = _bind("EFWCalibrate", ctypes.c_int, [ctypes.c_int])
efw_get_direction = _bind("EFWGetDirection", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)])
efw_set_direction = _bind("EFWSetDirection", ctypes.c_int, [ctypes.c_int, ctypes.c_bool])
efw_get_hw_error_code = _bind("EFWGetHWErrorCode", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(ctypes.c_int)])
efw_get_firmware_version = _bind(
    "EFWGetFirmwareVersion", ctypes.c_int,
    [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte)],
)
efw_get_serial_number = _bind("EFWGetSerialNumber", ctypes.c_int, [ctypes.c_int, ctypes.POINTER(EFW_SN)])
efw_set_id = _bind("EFWSetID", ctypes.c_int, [ctypes.c_int, EFW_SN])

# Version string — caller does NOT free the pointer
_efw_get_sdk_version = getattr(_lib, "EFWGetSDKVersion")
_efw_get_sdk_version.restype = ctypes.c_char_p
_efw_get_sdk_version.argtypes = []


# ---------------------------------------------------------------------------
# Python-friendly API
# ---------------------------------------------------------------------------


class EFWDevice:
    """High-level wrapper around a single EFW filter wheel."""

    def __init__(self):
        self._id: int = -1
        self._info: Optional[EFW_INFO] = None
        self._last_position: int = 0

    # -- Discovery --

    @staticmethod
    def discover() -> List[int]:
        """Return list of device IDs currently connected."""
        n = efw_get_num()
        if n <= 0:
            return []
        ids = []
        for i in range(n):
            pid = ctypes.c_int()
            efw_get_id(i, ctypes.byref(pid))
            ids.append(pid.value)
        return ids

    # -- Lifecycle --

    def open(self, device_id: int) -> None:
        """Open the filter wheel and retrieve its properties."""
        efw_open(device_id)
        self._id = device_id

        info = EFW_INFO()
        efw_get_property(device_id, ctypes.byref(info))
        self._info = info

        # Calibrate on first open
        try:
            efw_calibrate(device_id)
        except EFWError:
            # Calibration may fail if already calibrated or moving — not fatal
            pass

    def close(self) -> None:
        """Close the filter wheel."""
        if self._id >= 0:
            try:
                efw_close(self._id)
            except EFWError:
                pass
            self._id = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- Properties --

    @property
    def device_id(self) -> int:
        return self._id

    @property
    def slot_num(self) -> int:
        if self._info is None:
            return 0
        return self._info.slotNum

    @property
    def device_name(self) -> str:
        if self._info is None:
            return "Unknown"
        return self._info.Name.decode("utf-8", errors="replace").strip("\x00")

    @property
    def sdk_version(self) -> str:
        raw = _efw_get_sdk_version()
        if raw is None:
            return "Unknown"
        parts = raw.decode("utf-8").strip().split(",")
        return ".".join(p.strip() for p in parts)

    def firmware_version(self) -> str:
        major = ctypes.c_ubyte()
        minor = ctypes.c_ubyte()
        build = ctypes.c_ubyte()
        efw_get_firmware_version(self._id, ctypes.byref(major), ctypes.byref(minor), ctypes.byref(build))
        return f"{major.value}.{minor.value}.{build.value}"

    def serial_number(self) -> str:
        sn = EFW_SN()
        try:
            efw_get_serial_number(self._id, ctypes.byref(sn))
            return "".join(f"{b:02X}" for b in sn.id)
        except EFWError:
            return "N/A"

    # -- Position --

    def get_position(self) -> int:
        """Return current slot position (0-based).

        Returns the last known position if the device reports -1 (moving).
        """
        pos = ctypes.c_int()
        try:
            efw_get_position(self._id, ctypes.byref(pos))
            if pos.value >= 0:
                self._last_position = pos.value
        except EFWError:
            pass
        return self._last_position

    def set_position(self, slot: int) -> None:
        """Move the wheel to the given 0-based slot."""
        efw_set_position(self._id, slot)
        self._last_position = slot

    def calibrate(self) -> None:
        """Re-calibrate the filter wheel."""
        efw_calibrate(self._id)

    # -- Direction --

    def get_direction(self) -> bool:
        val = ctypes.c_bool()
        efw_get_direction(self._id, ctypes.byref(val))
        return bool(val.value)

    def set_direction(self, unidirectional: bool) -> None:
        efw_set_direction(self._id, unidirectional)
