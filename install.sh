#!/bin/bash

echo "Installing Raspberry Pi LCD Terminal..."

# Update system
sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y

# Install dependencies
sudo apt install python3-rpi.gpio python3-pil python3-numpy python3-spidev p7zip-full git -y

# Download and extract Waveshare drivers
cd ~
wget https://files.waveshare.com/upload/f/fa/1.44inch-LCD-HAT-Code.7z
7z x 1.44inch-LCD-HAT-Code.7z

# Create terminal directory
mkdir -p ~/terminal

# Copy Waveshare library files
cp ~/1.44inch-LCD-HAT-Code/RaspberryPi/python/LCD_1in44.py ~/terminal/
cp ~/1.44inch-LCD-HAT-Code/RaspberryPi/python/config.py ~/terminal/
cp ~/1.44inch-LCD-HAT-Code/RaspberryPi/python/config.py ~/terminal/LCD_Config.py

# Clone the repo for easy updates
git clone https://github.com/vassilis-ioannou2/pocket-terminal.git ~/pocket-terminal

# Copy terminal.py from repo
cp ~/pocket-terminal/terminal.py ~/terminal/

# Setup systemd service
sudo cp ~/pocket-terminal/terminal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable terminal.service

# Install pocket-terminal command
sudo cp ~/pocket-terminal/pocket-terminal-cmd.sh /usr/local/bin/pocket-terminal
sudo chmod +x /usr/local/bin/pocket-terminal

# Enable SPI
sudo raspi-config nonint do_spi 0

# Enable autologin
sudo raspi-config nonint do_boot_behaviour B2

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "Reboot to start the terminal:"
echo "  sudo reboot"
echo ""
echo "Available commands:"
echo "  pocket-terminal update   - Pull latest updates"
echo "  pocket-terminal enable   - Enable auto-start"
echo "  pocket-terminal disable  - Disable auto-start"
echo "  pocket-terminal status   - Check status"
echo ""
