# ZWO Filter Wheel Controller

A terminal UI for controlling ZWO EFW electronic filter wheels on macOS.

```
╭─────────────────────────────────────────────────────────────╮
│ ZWO Filter Wheel Controller  EFW                            │
│ Slots: 7  |  SDK: 1.8.4  |  Firmware: 3.5.2                 │
│ Slot 3 — SII 7nm                                            │
│ ████████░░░░░░░░░░░░  3/7                                   │
│ Filters:                                                    │
│ 1  H Alpha 7nm        2  OIII 7nm                           │
│ 3  SII 7nm            4  Luminance                          │
│ 5  Red                6  Green                              │
│ 7  Blue                                                     │
│ 1–7 Move to slot  |  s Save config  |  r Reload  |  q Quit  │
│ ✓  Moved to Slot 3.                                         │
╰─────────────────────────────────────────────────────────────╯
```

The current slot is highlighted in the filter list. Status messages
appear in green; errors in red.

---

## Platform Support

| Platform | Status |
|---|---|
| macOS arm64 — Apple Silicon | ✓ Supported |
| macOS x86_64 — Intel | ✓ Supported |
| Linux | Not yet supported |
| Windows | Not yet supported |

---

## Features

- Automatic device discovery and calibration on startup
- Interactive filter slot naming, saved as JSON
- Real-time slot position display with a progress bar
- Colour-coded TUI — current slot, status messages, and menu hints are highlighted
- Filter config persisted to `filters.json` and reloaded on each run

---

## Requirements

- macOS 12 or later (arm64 or x86_64)
- Python 3.10 or later
- A ZWO EFW filter wheel connected via USB
- ZWO EFW SDK — **must be downloaded separately** (see Step 1)

---

## Installation

### Step 1 — Download and extract the ZWO EFW SDK

The SDK provides the hardware driver library required by this project.
It is **not bundled** in this repository and must be obtained directly from ZWO.

1. Go to the ZWO EFW SDK release page:  
   **https://releaselog.zwoastro.com/efw**

2. Download the macOS / Linux SDK archive (e.g. `EFW_linux_mac_SDK_V1.8.4.tar.bz2`).

3. Extract the archive:

   ```bash
   tar -xjf EFW_linux_mac_SDK_V1.8.4.tar.bz2
   ```

   Note the full path to the extracted folder — you will need it in Step 3.

---

### Step 2 — Clone this repository

```bash
git clone https://github.com/<your-username>/zwo-filter-wheel.git
cd zwo-filter-wheel
```

---

### Step 3 — Install the SDK library

Run the provided script, passing the path to the extracted SDK archive:

```bash
./scripts/install_sdk.sh /path/to/EFW_linux_mac_SDK_V1.8.4
```

This detects your macOS architecture (Apple Silicon or Intel) and copies the
correct shared library into the local `lib/` directory.

> `lib/` is listed in `.gitignore` and is never committed to the repository.

---

### Step 4 — Create a virtual environment and install Python dependencies

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

---

## Usage

```bash
source env/bin/activate   # if not already active
python main.py
```

On first run you will be prompted to enter a name for each filter slot.
Names are saved to `filters.json` and reloaded automatically on subsequent runs.

---

## Controls

| Key | Action |
|---|---|
| `1` – `9` | Move to the corresponding slot |
| `s` | Save the current filter configuration |
| `r` | Reload the filter configuration from disk |
| `q` | Quit |

---

## Configuration

Filter names are stored in `filters.json` in the project directory:

```json
{
  "1": "H Alpha 7nm",
  "2": "OIII 7nm",
  "3": "SII 7nm",
  "4": "Luminance",
  "5": "Red",
  "6": "Green",
  "7": "Blue"
}
```

The file is created automatically on first run and can be edited by hand.
Slot numbers are 1-based and correspond to the physical positions on the wheel.

---

## Project Structure

```
zwo-filter-wheel/
├── scripts/
│   └── install_sdk.sh    # copies the SDK library for your platform into lib/
├── efw_sdk.py            # ctypes wrapper around the ZWO EFW C library
├── efw_ui.py             # Rich terminal UI
├── main.py               # entry point
├── requirements.txt      # Python dependencies
├── LICENSE               # ZWO SDK licence (MIT-style)
└── README.md
```

`lib/` is created locally by `install_sdk.sh` and is not tracked in git:

```
lib/
└── mac_arm64/            # or mac_x64/ on Intel
    └── libEFWFilter.dylib
```

---

## Troubleshooting

### macOS: library blocked by system policy

macOS Gatekeeper will block the SDK library if it still carries the quarantine
extended attribute set when the archive was downloaded, or if its code signature
is not valid for the current process.

`install_sdk.sh` handles this automatically. If you installed the library
manually, or encounter the error after the fact, run these two commands:

```bash
# Remove the quarantine attribute
xattr -cr lib/mac_arm64/libEFWFilter.dylib        # Apple Silicon
xattr -cr lib/mac_x64/libEFWFilter.dylib          # Intel

# Apply an ad-hoc code signature
codesign --force --deep --sign - lib/mac_arm64/libEFWFilter.dylib   # Apple Silicon
codesign --force --deep --sign - lib/mac_x64/libEFWFilter.dylib     # Intel
```

The error presenting as this issue looks like:

```
OSError: dlopen(...libEFWFilter.dylib): code signature not valid for use
in process: library load disallowed by system policy
```

---

## SDK Licence

The ZWO EFW SDK is distributed under an MIT-style licence.
See [`LICENSE`](LICENSE) for the full text.

This project is not affiliated with or endorsed by ZWO (ZWOptical Co. Ltd).
