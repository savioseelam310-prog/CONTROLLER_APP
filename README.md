# 🎮 Android PC Controller

Turn your Android phone into a game controller for your Windows PC!

Android PC Controller is designed to send controller inputs from an Android phone to a Windows computer using Wi-Fi or Bluetooth. The PC receiver translates these inputs into a virtual Xbox 360 controller for compatible games.

## ✨ Features

- 📱 Android phone as a PC game controller
- 📡 Wi-Fi communication using WebSockets
- 🔵 Bluetooth Classic communication using RFCOMM
- 🎮 Virtual Xbox 360 controller emulation
- 🕹️ Support for buttons, D-pad, analog sticks, and triggers
- 💻 Designed for Windows 10 and Windows 11

## 📥 Download the Android App

Download the latest APK from the GitHub Releases page:

**[Download the latest release](../../releases/latest)**

### Installation

1. Download the APK to your Android phone.
2. Open the downloaded APK.
3. Allow installation from your browser or file manager if Android requests permission.
4. Install and launch the application.

Only install APK files from sources you trust.

## 🖥️ PC Receiver Requirements

The Android application requires a compatible PC receiver to translate phone inputs into game controller inputs.

### Hardware

- Windows 10 or Windows 11 PC
- Android phone
- Wi-Fi adapter for Wi-Fi connections
- Bluetooth adapter for Bluetooth connections

### Software

- Python 3.11 or a compatible Python version
- Python packages listed in `requirements.txt`
- ViGEmBus virtual gamepad driver compatible with `vgamepad`
- Windows Bluetooth support for Bluetooth Classic RFCOMM

**Important:** The APK and PC receiver are separate components. The receiver and its dependencies must be obtained and installed separately unless they are distributed in a future release.

## 📦 Python Dependencies

The receiver uses:

- `websockets` — WebSocket server for Wi-Fi communication
- `vgamepad` — Virtual Xbox 360 gamepad emulation

The Python standard library provides the networking, JSON handling, threading, logging, and Windows Bluetooth integration.

## ⚙️ Receiver Setup

### 1. Install Python

Install Python from [python.org](https://www.python.org/downloads/).

On Windows, enable the option to add Python to PATH if offered.

### 2. Install the virtual gamepad driver

Install a compatible ViGEmBus driver required by `vgamepad`, following the package's installation instructions.

Without the required virtual gamepad driver, the receiver may fail to initialize the virtual controller.

### 3. Install Python dependencies

Open Command Prompt in the receiver folder and run:

```bash
python -m pip install -r requirements.txt
```

### 4. Start the receiver

Run:

```bash
python receiver_wifi_bluetooth.py
```

If your receiver file has a different name, use that filename instead.

The receiver logs its startup status and connection information in the terminal.

## 📡 Wi-Fi Connection

The receiver listens for WebSocket connections on port `8765`.

1. Connect the phone and PC to the same local network.
2. Start the receiver on the PC.
3. Find the PC's local IPv4 address using `ipconfig`.
4. Configure the Android app to connect to the PC's IP address and port `8765`, according to the app's connection settings.
5. Allow Python through Windows Firewall on trusted private networks if prompted.

The receiver endpoint is:

```text
ws://PC_IP_ADDRESS:8765
```

Replace `PC_IP_ADDRESS` with the computer's actual local IPv4 address.

## 🔵 Bluetooth Connection

The receiver implements Bluetooth Classic RFCOMM and attempts to advertise the controller service through Windows Winsock service discovery.

1. Enable Bluetooth on the PC and phone.
2. Pair the phone and PC through Windows Bluetooth settings if required.
3. Start the receiver.
4. Use the Bluetooth connection option in the Android app, if supported by your app build.
5. Follow the app's connection instructions.

Bluetooth requires compatible communication settings on both the Android app and the PC receiver. Pairing alone does not guarantee that the controller connection will work.

## 🎮 Controller Mapping

The receiver maps incoming events to a virtual Xbox 360 controller.

| Input | Virtual controller |
|---|---|
| A, B, X, Y | Face buttons |
| UP, DOWN, LEFT, RIGHT | D-pad |
| LB, RB | Shoulder buttons |
| L3, R3 | Stick clicks |
| START | Start |
| SELECT, BACK | Back |
| LT, RT | Analog triggers |
| Left and right sticks | Analog joysticks |
| GUIDE, XBOX | Guide button |

Games must support controller input or allow controller configuration.

## 🔧 Troubleshooting

### The receiver will not start

- Check that Python is installed.
- Install the dependencies from `requirements.txt`.
- Verify that the required virtual gamepad driver is installed.
- Run the receiver from its correct directory.

### Wi-Fi connection fails

- Ensure the phone and PC can communicate over the same network.
- Check the PC's IPv4 address.
- Verify that port `8765` is not blocked.
- Allow the receiver through Windows Firewall on trusted networks.

### Bluetooth connection fails

- Check that the PC has a working Bluetooth adapter.
- Verify the pairing and service-discovery configuration.
- Confirm that the Android app uses a compatible Bluetooth protocol.

### The game does not recognize the controller

- Verify that the virtual gamepad driver is working.
- Check Windows controller detection.
- Restart the receiver after installing the driver.
- Check whether the game supports virtual Xbox controllers.

## ⚠️ Limitations and Safety

- Bluetooth support depends on the Windows Bluetooth stack and compatibility between the app and receiver.
- Wi-Fi communication uses an unencrypted `ws://` connection. Use trusted networks only.
- The receiver is intended for use on a trusted local network.
- The receiver uses a shared virtual controller, so multiple connections may affect the same controller state.
- Some games may require additional configuration.
- The APK does not automatically install the PC receiver or virtual gamepad driver.

## 👨‍💻 Project

Created as a personal project to explore Android-to-PC game controller communication.

Contributions, bug reports, and suggestions are welcome.

## 📄 License

No license is granted unless one is explicitly added to this repository. Please contact the copyright holder before redistributing or modifying the project.
