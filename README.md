# pocket-terminal


![pocket-terminal-img](https://github.com/user-attachments/assets/284afc49-bce0-482d-bce5-0feedb7a5668)


Transforms your Raspberry Pi Zero into a fully portable, self-contained Linux terminal with a compact 1.44" LCD display and joystick controls. No external monitor, keyboard, or mouse required.

- Youtube Video: (YouTube link here)
- Website Guide: https://vassilis.ioannou2/projects/pocket-terminal.html

---

## Features

- Full Linux terminal with live command output and interactive prompts
- Multi-line command input with automatic text wrapping
- On-screen virtual keyboard with letters, numbers, and symbols
- Caps Lock toggle for uppercase input
- Command history navigation with arrow keys
- Scrollable terminal output
- Multi-WLAN WiFi management (auto-detects all wireless adapters)
- Connect/disconnect networks with password entry per interface
- Three visual themes: dark mode, light mode, and orange mode
- Adjustable screen brightness (10-100%)
- System information display (model, temperature, firmware, uptime)
- Hardware joystick + 3 buttons for navigation and control
- Long-press shutdown (5 sec) and quick reboot on menu
- Auto-start on boot via systemd service
- One-command installation and updates

---

## Requirements

- Raspberry Pi Zero / Zero 2 (or any other Raspberry Pi)
- Waveshare 1.44" LCD HAT (https://www.waveshare.com/wiki/1.44inch_LCD_HAT)
- Raspberry Pi OS Lite (Normal or Legacy)
- User **must be named `pi`** for the prompts and home-directory logic to work correctly
- Network access for the initial install (to fetch scripts and dependencies)

---

## Installation

1. Flash Raspberry Pi OS to your SD card.
2. Enable SSH and connect to your Pi as user `pi`.
3. **Run the one-line installer: `curl -sSL https://raw.githubusercontent.com/vassilis-ioannou2/pocket-terminal/main/install.sh | bash`**
4. When the script finishes, reboot: `sudo reboot`

On the next boot, pocket-terminal will start automatically on the LCD.

---

## Controls

Controls:

- **Joystick**
  - Up / Down: Navigate menus, scroll terminal output, or move in keyboard
  - Left / Right: Navigate command history (terminal mode) or move keyboard cursor
  - Press: Toggle on-screen keyboard (terminal) or open keyboard (WiFi password)

- **KEY1**
  - Long press (~5 seconds): Shutdown the Pi safely
  - Short press on main menu: Reboot the Pi

- **KEY2**
  - Short press: Go back to previous menu or close keyboard

- **KEY3**
  - In menu: Open/select highlighted option
  - In terminal mode: Execute current command
  - In keyboard mode: Press the selected key (character, SPC, CAPS, BSP, CLR, arrows)
  - In WiFi: Toggle interface, WiFi on/off, disconnect, or connect to network

---

## Commands

After installation, you can manage pocket-terminal with a single command: `pocket-terminal <command>`


Available commands:

- `pocket-terminal update`  
  Pull the latest version from GitHub, copy the new `terminal.py`, and restart the service.

- `pocket-terminal enable`  
  Enable auto-start on boot (systemd service enabled).

- `pocket-terminal disable`  
  Disable auto-start on boot (systemd service disabled).

- `pocket-terminal start`  
  Start the terminal service immediately.

- `pocket-terminal stop`  
  Stop the terminal service.

- `pocket-terminal restart`  
  Restart the terminal service.

- `pocket-terminal status`  
  Show the systemd status for the terminal service.

- `pocket-terminal` (with no or unknown subcommand)  
  Print a short help message listing the available commands.

---

## License

MIT License
