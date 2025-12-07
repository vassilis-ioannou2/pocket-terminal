#!/bin/bash
echo "Updating terminal..."
git pull origin main
cp terminal.py ~/terminal/
sudo systemctl restart terminal.service
echo "Update complete!"
