#!/bin/bash

echo "Installing Raspberry Pi LCD Terminal..."

sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y

sudo apt install python3-rpi.gpio python3-pil python3-numpy python3-spidev p7zip-full git -y

cd ~
wget https://files.waveshare.com/upload/f/fa/1.44inch-LCD-HAT-Code.7z
7z x 1.44inch-LCD-HAT-Code.7z

mkdir -p ~/terminal
cp ~/1.44inch-LCD-HAT-Code/RaspberryPi/python/LCD_1in44.py ~/terminal/
cp ~/1.44inch-LCD-HAT-Code/RaspberryPi/python/config.py ~/terminal/LCD_Config.py

cp terminal.py ~/terminal/

sudo cp terminal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable terminal.service

sudo raspi-config nonint do_spi 0

sudo raspi-config nonint do_boot_behaviour B2

echo "Installation complete! Reboot to start terminal."
echo "To update later, run: ./update.sh"
