# pocket-terminal

![pocket-terminal-img](https://github.com/user-attachments/assets/e03fbf27-39b0-47f3-a39c-cc5e455ce42d)

Transforms your Raspberry Pi Zero into a fully portable, self-contained Linux terminal with a compact 1.44" LCD display and joystick controls. No external monitor, keyboard, or mouse required.

- Youtube Video: (YouTube link here)
- Website Guide: https://vassilis.ioannou/projects/pocket-terminal.html

---

## Features

- Dual terminal sessions – switch between two independent terminals
- Background process execution with visual “running” indicator
- On-screen virtual keyboard with full character and symbol support
- Command history navigation (left/right to browse previous commands)
- Per-terminal state: directory, history, and output preserved per session
- Hardware joystick + 3 buttons for full control
- Auto-start on boot via systemd service
- One-command installation and simple update command
- Long-press hardware shutdown for safe power-off

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

- **Joystick**
- Up / Down: Scroll terminal or move in the keyboard
- Left / Right: Navigate command history (terminal mode) or move keyboard cursor
- Press: Toggle on-screen keyboard

- **KEY1**
- Long press (~5 seconds): Shutdown the Pi safely

- **KEY2**
- Short press: Switch between Terminal 1 and Terminal 2

- **KEY3**
- In terminal mode: Execute current command, or stop a running command
- In keyboard mode: “Press” the selected key (character, SPC, BSP, CLR, arrows)

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
