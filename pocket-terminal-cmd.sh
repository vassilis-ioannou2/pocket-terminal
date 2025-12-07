#!/bin/bash

REPO_DIR="$HOME/pocket-terminal"
INSTALL_DIR="$HOME/terminal"
SERVICE_NAME="terminal.service"

case "$1" in
    update)
        echo "Updating pocket-terminal..."
        cd "$REPO_DIR" || exit 1
        git pull origin main
        cp terminal.py "$INSTALL_DIR/"
        sudo systemctl restart "$SERVICE_NAME"
        echo "✓ Update complete!"
        ;;
    
    enable)
        echo "Enabling auto-start on boot..."
        sudo systemctl enable "$SERVICE_NAME"
        echo "✓ pocket-terminal will start on boot"
        ;;
    
    disable)
        echo "Disabling auto-start on boot..."
        sudo systemctl disable "$SERVICE_NAME"
        echo "✓ pocket-terminal will NOT start on boot"
        ;;
    
    start)
        echo "Starting pocket-terminal..."
        sudo systemctl start "$SERVICE_NAME"
        echo "✓ Started"
        ;;
    
    stop)
        echo "Stopping pocket-terminal..."
        sudo systemctl stop "$SERVICE_NAME"
        echo "✓ Stopped"
        ;;
    
    restart)
        echo "Restarting pocket-terminal..."
        sudo systemctl restart "$SERVICE_NAME"
        echo "✓ Restarted"
        ;;
    
    status)
        sudo systemctl status "$SERVICE_NAME"
        ;;
    
    *)
        echo "pocket-terminal - Portable LCD Terminal Manager"
        echo ""
        echo "Available commands:"
        echo "  update   - Pull latest code from GitHub and restart"
        echo "  enable   - Enable auto-start on boot"
        echo "  disable  - Disable auto-start on boot"
        echo "  start    - Start the terminal now"
        echo "  stop     - Stop the terminal now"
        echo "  restart  - Restart the terminal now"
        echo "  status   - Show service status"
        echo ""
        echo "Usage: pocket-terminal <command>"
        ;;
esac
