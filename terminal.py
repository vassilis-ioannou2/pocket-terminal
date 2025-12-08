import LCD_1in44
import time
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import subprocess
import os
import pwd
import threading
import select
import pty
import termios
import struct
import fcntl

KEY_UP_PIN = 6
KEY_DOWN_PIN = 19
KEY_LEFT_PIN = 5
KEY_RIGHT_PIN = 26
KEY_PRESS_PIN = 13
KEY1_PIN = 21
KEY2_PIN = 20
KEY3_PIN = 16
BACKLIGHT_PIN = 24

class Terminal:
    def __init__(self):
        self.command_input = ""
        self.cursor_pos = 0
        self.output_lines = []
        self.command_history = []
        self.history_index = -1
        self.keyboard_visible = False
        self.kb_page = 0
        self.kb_row = 0
        self.kb_col = 0
        self.scroll_offset = 0
        self.pty_master = None
        self.pty_slave = None
        self.process = None
        self.read_thread = None
        self.caps_lock = False
        try:
            pi_home = pwd.getpwnam('pi').pw_dir
            self.working_dir = pi_home
        except:
            self.working_dir = "/home/pi"

class PocketTerminal:
    def __init__(self):
        self.LCD = LCD_1in44.LCD()
        self.LCD.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
        self.LCD.LCD_Clear()
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        
        input_pins = [KEY_UP_PIN, KEY_DOWN_PIN, KEY_LEFT_PIN, KEY_RIGHT_PIN,
                     KEY_PRESS_PIN, KEY1_PIN, KEY2_PIN, KEY3_PIN]
        for pin in input_pins:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        GPIO.setup(BACKLIGHT_PIN, GPIO.OUT)
        self.pwm = GPIO.PWM(BACKLIGHT_PIN, 1000)
        self.pwm.start(100)
        
        self.username = 'pi'
        try:
            pi_home = pwd.getpwnam('pi').pw_dir
            os.chdir(pi_home)
        except:
            os.chdir("/home/pi")
        
        self.current_screen = "menu"
        self.terminal = Terminal()
        self.menu_index = 0
        
        self.brightness = 100
        self.theme = "dark"
        
        self.themes = {
            "dark": {
                "bg": "BLACK",
                "fg": "WHITE",
                "title_bg": "BLUE",
                "title_fg": "WHITE",
                "select_bg": "YELLOW",
                "select_fg": "BLACK",
                "terminal_output": "GREEN",
                "prompt": "CYAN",
                "status_running": "ORANGE"
            },
            "light": {
                "bg": "WHITE",
                "fg": "BLACK",
                "title_bg": "LIGHTBLUE",
                "title_fg": "BLACK",
                "select_bg": "YELLOW",
                "select_fg": "BLACK",
                "terminal_output": "DARKGREEN",
                "prompt": "BLUE",
                "status_running": "ORANGE"
            },
            "orange": {
                "bg": "BLACK",
                "fg": "ORANGE",
                "title_bg": "ORANGE",
                "title_fg": "BLACK",
                "select_bg": "YELLOW",
                "select_fg": "BLACK",
                "terminal_output": "ORANGE",
                "prompt": "YELLOW",
                "status_running": "RED"
            }
        }
        
        self.available_wlans = self.detect_wlan_interfaces()
        self.current_wlan_idx = 0
        self.wlan_enabled = {}
        self.wifi_connected = {}
        self.wifi_networks = {}
        self.wifi_selected = 0
        self.wifi_menu_section = 0
        self.wifi_password_input = ""
        self.entering_wifi_password = False
        
        for wlan in self.available_wlans:
            self.wlan_enabled[wlan] = False
            self.wifi_connected[wlan] = None
            self.wifi_networks[wlan] = []
        self.check_all_wlan_status()
        
        self.settings_menu_index = 0
        self.in_theme_select = False
        self.theme_options = ["dark", "light", "orange"]
        self.theme_select_index = 0
        self.in_brightness_adjust = False
        
        self.system_info = {}
        
        self.keyboard_layouts = [
            [
                ['a','b','c','d','e','f','g','h','i','j'],
                ['k','l','m','n','o','p','q','r','s','t'],
                ['u','v','w','x','y','z','0','1','2','3'],
                ['4','5','6','7','8','9','.','-','_','/']
            ],
            [
                ['!','@','#','$','%','^','&','*','(',')'],
                ['[',']','{','}','<','>','|','\\',':',';'],
                ['"',"'",'`','~','+','=','?',',','!','@'],
                ['#','$','%','^','&','*','(',')','[',']']
            ]
        ]
        
        self.keyboard_bottom_row = ['<-','->','SPC','CAPS','BSP','CLR','MORE']
        
        self.button_prev = {}
        self.button_time = {}
        for pin in input_pins:
            self.button_prev[pin] = GPIO.HIGH
            self.button_time[pin] = 0
        
        self.key3_press_start = 0
        self.shutdown_threshold = 5.0
        self.reboot_threshold = 0.5
        
        self.running = True
        self.last_draw_time = 0
        self.needs_redraw = False
    
    def get_color(self, key):
        return self.themes[self.theme][key]
    
    def button_pressed(self, pin, debounce=0.15):
        current = GPIO.input(pin)
        if current == GPIO.LOW and self.button_prev[pin] == GPIO.HIGH:
            if time.time() - self.button_time[pin] >= debounce:
                self.button_prev[pin] = current
                self.button_time[pin] = time.time()
                return True
        self.button_prev[pin] = current
        return False
    
    def detect_wlan_interfaces(self):
        """Detect all available WLAN interfaces"""
        try:
            result = subprocess.run(['ls', '/sys/class/net/'], 
                                  capture_output=True, text=True, timeout=2)
            interfaces = result.stdout.strip().split('\n')
            wlans = sorted([iface for iface in interfaces if iface.startswith('wlan')])
            return wlans if wlans else ['wlan0']
        except:
            return ['wlan0']
    
    def get_current_wlan(self):
        """Get the currently selected WLAN interface name"""
        if self.current_wlan_idx < len(self.available_wlans):
            return self.available_wlans[self.current_wlan_idx]
        return self.available_wlans[0] if self.available_wlans else 'wlan0'
    
    def check_all_wlan_status(self):
        """Check status of all WLAN interfaces"""
        for wlan in self.available_wlans:
            try:
                result = subprocess.run(['nmcli', 'device', 'show', wlan],
                                      capture_output=True, text=True, timeout=2)
                
                if 'connected' in result.stdout.lower():
                    self.wlan_enabled[wlan] = True
                    conn_result = subprocess.run(['nmcli', '-t', '-f', 'ACTIVE,SSID', 
                                                 'device', 'wifi', 'list', 'ifname', wlan],
                                                capture_output=True, text=True, timeout=2)
                    for line in conn_result.stdout.strip().split('\n'):
                        if line.startswith('yes:'):
                            self.wifi_connected[wlan] = line.split(':', 1)[1]
                            break
                    else:
                        self.wifi_connected[wlan] = None
                else:
                    self.wlan_enabled[wlan] = False
                    self.wifi_connected[wlan] = None
            except:
                self.wlan_enabled[wlan] = False
                self.wifi_connected[wlan] = None
    
    def toggle_wlan(self, wlan):
        """Toggle WiFi on/off for specific interface"""
        try:
            if self.wlan_enabled[wlan]:
                subprocess.run(['sudo', 'nmcli', 'radio', 'wifi', 'off', 'ifname', wlan], timeout=5)
                self.wlan_enabled[wlan] = False
                self.wifi_connected[wlan] = None
            else:
                subprocess.run(['sudo', 'nmcli', 'radio', 'wifi', 'on', 'ifname', wlan], timeout=5)
                self.wlan_enabled[wlan] = True
        except:
            pass
    
    def scan_wifi(self, wlan):
        """Scan for WiFi networks on specific interface"""
        try:
            subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'rescan', 'ifname', wlan],
                          capture_output=True, text=True, timeout=5)
            time.sleep(1)
            
            result = subprocess.run(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'device', 'wifi', 
                                   'list', 'ifname', wlan],
                                  capture_output=True, text=True, timeout=5)
            networks = []
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2 and parts[0]:
                        ssid = parts[0]
                        signal = parts[1] if len(parts) > 1 else '0'
                        if ssid != self.wifi_connected.get(wlan):
                            networks.append({'ssid': ssid, 'signal': signal})
            
            seen = {}
            for net in networks:
                if net['ssid'] not in seen or int(net['signal']) > int(seen[net['ssid']]['signal']):
                    seen[net['ssid']] = net
            
            self.wifi_networks[wlan] = list(seen.values())
            self.wifi_networks[wlan].sort(key=lambda x: int(x['signal']), reverse=True)
        except:
            self.wifi_networks[wlan] = []
    
    def connect_wifi(self, wlan, ssid, password):
        """Connect to WiFi network"""
        try:
            subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 
                          'password', password, 'ifname', wlan], timeout=15, check=True)
            self.wifi_connected[wlan] = ssid
            self.wifi_networks[wlan] = [net for net in self.wifi_networks[wlan] if net['ssid'] != ssid]
        except:
            pass
    
    def disconnect_wifi(self, wlan):
        """Disconnect from current WiFi network"""
        try:
            subprocess.run(['sudo', 'nmcli', 'device', 'disconnect', wlan], timeout=5)
            if self.wifi_connected[wlan]:
                self.scan_wifi(wlan)
            self.wifi_connected[wlan] = None
        except:
            pass
    
    def get_system_info(self):
        info = {}
        try:
            with open('/proc/device-tree/model', 'r') as f:
                info['model'] = f.read().strip().replace('\x00', '')
        except:
            info['model'] = 'Unknown'
        
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=1)
            info['temp'] = result.stdout.strip()
        except:
            info['temp'] = 'N/A'
        
        try:
            result = subprocess.run(['uname', '-r'], 
                                  capture_output=True, text=True, timeout=1)
            info['firmware'] = result.stdout.strip()
        except:
            info['firmware'] = 'N/A'
        
        try:
            result = subprocess.run(['uptime', '-p'], 
                                  capture_output=True, text=True, timeout=1)
            info['uptime'] = result.stdout.strip()
        except:
            info['uptime'] = 'N/A'
        
        self.system_info = info
    
    # ==================== DRAWING ====================
    
    def draw_screen(self):
        image = Image.new("RGB", (128, 128), self.get_color("bg"))
        draw = ImageDraw.Draw(image)
        
        if self.current_screen == "menu":
            self.draw_main_menu(draw)
        elif self.current_screen == "terminal":
            self.draw_terminal(draw)
        elif self.current_screen == "wifi":
            self.draw_wifi(draw)
        elif self.current_screen == "settings":
            self.draw_settings(draw)
        elif self.current_screen == "about":
            self.draw_about(draw)
        
        self.LCD.LCD_ShowImage(image, 0, 0)
        self.last_draw_time = time.time()
        self.needs_redraw = False
    
    def draw_main_menu(self, draw):
        draw.rectangle([(0, 0), (127, 12)], fill=self.get_color("title_bg"))
        draw.text((15, 2), "POCKET TERMINAL", fill=self.get_color("title_fg"))
        
        menu_items = ["Terminal", "WiFi", "Settings", "About"]
        y = 25
        for i, item in enumerate(menu_items):
            if i == self.menu_index:
                draw.rectangle([(5, y), (122, y+15)], fill=self.get_color("select_bg"))
                draw.text((10, y+2), f"> {item}", fill=self.get_color("select_fg"))
            else:
                draw.text((10, y+2), f"  {item}", fill=self.get_color("fg"))
            y += 18
        
        draw.text((5, 112), "Up/Dn:Nav K3:Open", fill=self.get_color("prompt"))
    
    def draw_terminal(self, draw):
        term = self.terminal
        
        draw.rectangle([(0, 0), (127, 10)], fill=self.get_color("title_bg"))
        draw.text((2, 1), "TERMINAL", fill=self.get_color("title_fg"))
        
        if term.keyboard_visible:
            self.draw_terminal_with_keyboard(draw, term)
        else:
            self.draw_terminal_only(draw, term)
    
    def draw_terminal_only(self, draw, term):
        max_lines = 6
        total_lines = len(term.output_lines)
        start_idx = max(0, total_lines - max_lines - term.scroll_offset)
        end_idx = total_lines - term.scroll_offset
        visible_lines = term.output_lines[start_idx:end_idx]
        
        y_pos = 12
        for line in visible_lines:
            draw.text((2, y_pos), line[:21], fill=self.get_color("terminal_output"))
            y_pos += 13
        
        draw.rectangle([(0, 90), (127, 127)], fill=self.get_color("bg"))
        
        prompt = f"{self.username}$"
        display_text = term.command_input.replace(' ', '_')
        
        wrapped_lines = []
        first_line_width = 18
        other_line_width = 21
        
        if len(display_text) <= first_line_width:
            wrapped_lines.append(display_text)
        else:
            wrapped_lines.append(display_text[:first_line_width])
            remaining = display_text[first_line_width:]
            while remaining:
                wrapped_lines.append(remaining[:other_line_width])
                remaining = remaining[other_line_width:]
        
        visible_wrapped = wrapped_lines[-3:]
        
        y = 92
        draw.text((2, y), prompt, fill=self.get_color("prompt"))
        
        if visible_wrapped:
            draw.text((len(prompt)*6 + 4, y), visible_wrapped[0], fill=self.get_color("fg"))
        
        for line in visible_wrapped[1:]:
            y += 11
            draw.text((2, y), line, fill=self.get_color("fg"))
        
        if int(time.time() * 2) % 2 == 0:
            chars_before = term.cursor_pos
            
            if chars_before <= first_line_width:
                cursor_line = 0
                cursor_offset = chars_before
            else:
                chars_after_first = chars_before - first_line_width
                cursor_line = 1 + (chars_after_first // other_line_width)
                cursor_offset = chars_after_first % other_line_width
            
            visible_line_idx = cursor_line - (len(wrapped_lines) - len(visible_wrapped))
            
            if 0 <= visible_line_idx < len(visible_wrapped):
                cursor_y = 92 + (visible_line_idx * 11)
                
                if visible_line_idx == 0:
                    cursor_x = len(prompt)*6 + 4 + (cursor_offset * 6)
                else:
                    cursor_x = 2 + (cursor_offset * 6)
                
                draw.rectangle([(cursor_x, cursor_y), (cursor_x+5, cursor_y+10)], fill="YELLOW")
        
        draw.text((2, 115), "Joy:KB K2:Menu K3:Run", fill=self.get_color("prompt"))
    
    def draw_terminal_with_keyboard(self, draw, term):
        if term.output_lines:
            draw.text((2, 12), term.output_lines[-1][:21], fill=self.get_color("terminal_output"))
        
        prompt = f"{self.username}$"
        display_text = term.command_input.replace(' ', '_')
        
        first_line_width = 18
        other_line_width = 21
        
        wrapped_lines = []
        if len(display_text) <= first_line_width:
            wrapped_lines.append(display_text)
        else:
            wrapped_lines.append(display_text[:first_line_width])
            remaining = display_text[first_line_width:]
            while remaining:
                wrapped_lines.append(remaining[:other_line_width])
                remaining = remaining[other_line_width:]
        
        visible_input_lines = wrapped_lines[-2:]
        
        y = 24
        for idx, line in enumerate(visible_input_lines):
            if idx == 0 and len(wrapped_lines) == len(visible_input_lines):
                draw.text((2, y), prompt, fill=self.get_color("prompt"))
                draw.text((len(prompt)*6+4, y), line, fill=self.get_color("fg"))
            else:
                draw.text((2, y), line, fill=self.get_color("fg"))
            y += 10
        
        chars_before = term.cursor_pos
        
        if chars_before <= first_line_width:
            cursor_line = 0
            cursor_offset = chars_before
        else:
            chars_after_first = chars_before - first_line_width
            cursor_line = 1 + (chars_after_first // other_line_width)
            cursor_offset = chars_after_first % other_line_width
        
        visible_line_idx = cursor_line - (len(wrapped_lines) - len(visible_input_lines))
        
        if 0 <= visible_line_idx < len(visible_input_lines):
            cursor_y = 24 + (visible_line_idx * 10)
            
            if visible_line_idx == 0 and len(wrapped_lines) == len(visible_input_lines):
                cursor_x = len(prompt)*6 + 4 + (cursor_offset * 6)
            else:
                cursor_x = 2 + (cursor_offset * 6)
            
            draw.line([(cursor_x, cursor_y), (cursor_x, cursor_y+9)], fill="YELLOW", width=2)
        
        separator_y = 24 + (len(visible_input_lines) * 10) + 2
        draw.line([(0, separator_y), (127, separator_y)], fill=self.get_color("prompt"))
        
        current_layout = self.keyboard_layouts[term.kb_page]
        
        y_kb = separator_y + 2
        for r, row in enumerate(current_layout):
            x_kb = 2
            for c, key in enumerate(row):
                key_width = 11
                
                display_key = key
                if term.caps_lock and key.isalpha():
                    display_key = key.upper()
                
                if r == term.kb_row and c == term.kb_col:
                    draw.rectangle([(x_kb, y_kb), (x_kb+key_width, y_kb+13)], 
                                 fill=self.get_color("select_bg"))
                    draw.text((x_kb+3, y_kb+2), display_key, fill=self.get_color("select_fg"))
                else:
                    draw.rectangle([(x_kb, y_kb), (x_kb+key_width, y_kb+13)], 
                                 outline=self.get_color("fg"))
                    draw.text((x_kb+3, y_kb+2), display_key, fill=self.get_color("fg"))
                
                x_kb += key_width + 1
            y_kb += 14
        
        y_bottom = 98
        x_kb = 0
        for i, key in enumerate(self.keyboard_bottom_row):
            if key in ['SPC', 'CAPS', 'BSP', 'CLR', 'MORE']:
                key_width = 17
            else:
                key_width = 14
            
            if key == 'CAPS' and term.caps_lock:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+14)], 
                             fill="GREEN")
                draw.text((x_kb+2, y_bottom+2), key, fill="BLACK")
            elif term.kb_row == 4 and term.kb_col == i:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+14)], 
                             fill=self.get_color("select_bg"))
                draw.text((x_kb+2, y_bottom+2), key, fill=self.get_color("select_fg"))
            else:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+14)], 
                             outline=self.get_color("fg"))
                draw.text((x_kb+2, y_bottom+2), key, fill=self.get_color("fg"))
            
            x_kb += key_width + 1
        
        caps_indicator = "[CAPS]" if term.caps_lock else f"[{term.kb_page+1}/2]"
        draw.text((2, 116), caps_indicator, fill=self.get_color("prompt"))
    
    def draw_wifi(self, draw):
        draw.rectangle([(0, 0), (127, 12)], fill=self.get_color("title_bg"))
        draw.text((45, 2), "WiFi", fill=self.get_color("title_fg"))
        
        if self.entering_wifi_password:
            self.draw_wifi_password_entry(draw)
        else:
            y = 15
            current_wlan = self.get_current_wlan()
            
            if self.wifi_menu_section == 0:
                draw.rectangle([(2, y), (125, y+10)], fill=self.get_color("select_bg"))
                draw.text((5, y+1), f"Interface: {current_wlan.upper()}", 
                         fill=self.get_color("select_fg"))
            else:
                draw.rectangle([(2, y), (125, y+10)], outline=self.get_color("fg"))
                draw.text((5, y+1), f"Interface: {current_wlan.upper()}", 
                         fill=self.get_color("fg"))
            y += 12
            
            wifi_status = "ON" if self.wlan_enabled[current_wlan] else "OFF"
            if self.wifi_menu_section == 1:
                draw.rectangle([(2, y), (125, y+10)], fill=self.get_color("select_bg"))
                draw.text((5, y+1), f"WiFi: {wifi_status}", 
                         fill=self.get_color("select_fg"))
            else:
                draw.text((5, y+1), f"WiFi: {wifi_status}", fill=self.get_color("prompt"))
            y += 12
            
            if self.wlan_enabled[current_wlan]:
                draw.text((5, y), "Connected:", fill=self.get_color("fg"))
                y += 10
                
                if self.wifi_connected[current_wlan]:
                    if self.wifi_menu_section == 2:
                        draw.rectangle([(2, y), (125, y+10)], fill=self.get_color("select_bg"))
                        draw.text((5, y+1), f"{self.wifi_connected[current_wlan][:18]}", 
                                 fill=self.get_color("select_fg"))
                    else:
                        draw.text((5, y+1), f"{self.wifi_connected[current_wlan][:18]}", fill="GREEN")
                    y += 12
                else:
                    draw.text((5, y+1), "None", fill=self.get_color("fg"))
                    y += 12
                
                draw.text((5, y), "Available:", fill=self.get_color("fg"))
                y += 10
                
                if not self.wifi_networks[current_wlan]:
                    draw.text((20, y), "Scanning...", fill=self.get_color("fg"))
                else:
                    for i, net in enumerate(self.wifi_networks[current_wlan]):
                        if y > 110:
                            break
                        
                        section_idx = 3 + i
                        if self.wifi_menu_section == section_idx:
                            draw.rectangle([(2, y), (125, y+9)], fill=self.get_color("select_bg"))
                            text_color = self.get_color("select_fg")
                        else:
                            text_color = self.get_color("fg")
                        
                        ssid = net['ssid'][:15]
                        signal = net['signal']
                        draw.text((5, y), f"{ssid} {signal}%", fill=text_color)
                        y += 10
            
            draw.text((2, 118), "K3:Select K2:Back", fill=self.get_color("prompt"))
    
    def draw_wifi_password_entry(self, draw):
        term = self.terminal
        current_wlan = self.get_current_wlan()
        
        net_idx = self.wifi_menu_section - 3
        if 0 <= net_idx < len(self.wifi_networks[current_wlan]):
            selected_net = self.wifi_networks[current_wlan][net_idx]
            draw.text((5, 14), f"Join: {selected_net['ssid'][:15]}", fill=self.get_color("fg"))
        
        draw.text((5, 26), "Password:", fill=self.get_color("prompt"))
        masked = '*' * len(self.wifi_password_input)
        draw.text((5, 38), masked[:20], fill=self.get_color("fg"))
        
        draw.line([(0, 50), (127, 50)], fill=self.get_color("prompt"))
        
        current_layout = self.keyboard_layouts[term.kb_page]
        
        y_kb = 52
        for r, row in enumerate(current_layout):
            x_kb = 2
            for c, key in enumerate(row):
                key_width = 11
                
                display_key = key
                if term.caps_lock and key.isalpha():
                    display_key = key.upper()
                
                if r == term.kb_row and c == term.kb_col:
                    draw.rectangle([(x_kb, y_kb), (x_kb+key_width, y_kb+11)], 
                                 fill=self.get_color("select_bg"))
                    draw.text((x_kb+3, y_kb+2), display_key, fill=self.get_color("select_fg"))
                else:
                    draw.rectangle([(x_kb, y_kb), (x_kb+key_width, y_kb+11)], 
                                 outline=self.get_color("fg"))
                    draw.text((x_kb+3, y_kb+2), display_key, fill=self.get_color("fg"))
                
                x_kb += key_width + 1
            y_kb += 12
        
        y_bottom = 106
        x_kb = 0
        for i, key in enumerate(self.keyboard_bottom_row):
            if key in ['SPC', 'CAPS', 'BSP', 'CLR', 'MORE']:
                key_width = 17
            else:
                key_width = 14
            
            if key == 'CAPS' and term.caps_lock:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+12)], 
                             fill="GREEN")
                draw.text((x_kb+2, y_bottom+2), key, fill="BLACK")
            elif term.kb_row == 4 and term.kb_col == i:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+12)], 
                             fill=self.get_color("select_bg"))
                draw.text((x_kb+2, y_bottom+2), key, fill=self.get_color("select_fg"))
            else:
                draw.rectangle([(x_kb, y_bottom), (x_kb+key_width, y_bottom+12)], 
                             outline=self.get_color("fg"))
                draw.text((x_kb+2, y_bottom+2), key, fill=self.get_color("fg"))
            
            x_kb += key_width + 1
    
    def draw_settings(self, draw):
        draw.rectangle([(0, 0), (127, 12)], fill=self.get_color("title_bg"))
        draw.text((40, 2), "SETTINGS", fill=self.get_color("title_fg"))
        
        if self.in_theme_select:
            y = 20
            draw.text((5, y), "Select Theme:", fill=self.get_color("fg"))
            y += 15
            
            for i, theme_name in enumerate(self.theme_options):
                if i == self.theme_select_index:
                    draw.rectangle([(10, y), (115, y+13)], fill=self.get_color("select_bg"))
                    draw.text((15, y+2), f"> {theme_name.title()}", 
                             fill=self.get_color("select_fg"))
                else:
                    draw.text((15, y+2), f"  {theme_name.title()}", 
                             fill=self.get_color("fg"))
                y += 15
            
            draw.text((5, 112), "K3:Select K2:Back", fill=self.get_color("prompt"))
        
        elif self.in_brightness_adjust:
            y = 30
            draw.text((20, y), "BRIGHTNESS", fill=self.get_color("fg"))
            y += 20
            
            bar_width = int(self.brightness * 1.0)
            draw.rectangle([(14, y), (114, y+15)], outline=self.get_color("fg"))
            if bar_width > 0:
                draw.rectangle([(15, y+1), (15+bar_width, y+14)], 
                             fill=self.get_color("select_bg"))
            
            y += 20
            draw.text((45, y), f"{self.brightness}%", fill=self.get_color("fg"))
            
            y += 25
            draw.text((20, y), "<     -  +     >", fill=self.get_color("prompt"))
            
            draw.text((25, 112), "K2: Back", fill=self.get_color("prompt"))
        
        else:
            items = [
                f"Theme: {self.theme.title()}",
                f"Brightness: {self.brightness}%"
            ]
            
            y = 25
            for i, item in enumerate(items):
                if i == self.settings_menu_index:
                    draw.rectangle([(5, y), (122, y+15)], fill=self.get_color("select_bg"))
                    draw.text((10, y+2), f"> {item}", fill=self.get_color("select_fg"))
                else:
                    draw.text((10, y+2), f"  {item}", fill=self.get_color("fg"))
                y += 18
            
            draw.text((5, 112), "K3:Change K2:Back", fill=self.get_color("prompt"))
    
    def draw_about(self, draw):
        draw.rectangle([(0, 0), (127, 12)], fill=self.get_color("title_bg"))
        draw.text((45, 2), "ABOUT", fill=self.get_color("title_fg"))
        
        if not self.system_info:
            self.get_system_info()
        
        y = 18
        draw.text((5, y), "Device:", fill=self.get_color("fg"))
        y += 10
        model = self.system_info.get('model', 'Unknown')
        if len(model) > 21:
            draw.text((5, y), model[:21], fill=self.get_color("terminal_output"))
            y += 10
            draw.text((5, y), model[21:42], fill=self.get_color("terminal_output"))
        else:
            draw.text((5, y), model, fill=self.get_color("terminal_output"))
        
        y += 12
        draw.text((5, y), self.system_info.get('temp', 'N/A'), fill=self.get_color("fg"))
        
        y += 12
        draw.text((5, y), "Firmware:", fill=self.get_color("fg"))
        y += 10
        draw.text((5, y), self.system_info.get('firmware', 'N/A')[:21], 
                 fill=self.get_color("terminal_output"))
        
        y += 12
        uptime = self.system_info.get('uptime', 'N/A')
        draw.text((5, y), uptime[:21], fill=self.get_color("fg"))
        
        draw.text((40, 115), "K2: Back", fill=self.get_color("prompt"))
    
    # ==================== INPUT HANDLING ====================
    
    def handle_input(self):
        current_time = time.time()
        
        if GPIO.input(KEY3_PIN) == GPIO.LOW:
            if self.key3_press_start == 0:
                self.key3_press_start = current_time
            elif current_time - self.key3_press_start >= self.shutdown_threshold:
                self.shutdown_pi()
                return
        else:
            if self.key3_press_start > 0:
                press_duration = current_time - self.key3_press_start
                if press_duration >= self.reboot_threshold and press_duration < self.shutdown_threshold:
                    if self.current_screen == "menu":
                        self.reboot_pi()
                self.key3_press_start = 0
        
        if self.current_screen == "menu":
            self.handle_menu_input()
        elif self.current_screen == "terminal":
            self.handle_terminal_input()
        elif self.current_screen == "wifi":
            self.handle_wifi_input()
        elif self.current_screen == "settings":
            self.handle_settings_input()
        elif self.current_screen == "about":
            if self.button_pressed(KEY2_PIN):
                self.current_screen = "menu"
                self.draw_screen()
    
    def handle_menu_input(self):
        if self.button_pressed(KEY_UP_PIN, 0.15):
            self.menu_index = (self.menu_index - 1) % 4
            self.draw_screen()
        
        elif self.button_pressed(KEY_DOWN_PIN, 0.15):
            self.menu_index = (self.menu_index + 1) % 4
            self.draw_screen()
        
        elif self.button_pressed(KEY3_PIN, 0.15):
            if self.menu_index == 0:
                self.current_screen = "terminal"
            elif self.menu_index == 1:
                self.current_screen = "wifi"
                self.wifi_menu_section = 0
                current_wlan = self.get_current_wlan()
                self.check_all_wlan_status()
                if self.wlan_enabled[current_wlan]:
                    self.scan_wifi(current_wlan)
            elif self.menu_index == 2:
                self.current_screen = "settings"
            elif self.menu_index == 3:
                self.current_screen = "about"
                self.get_system_info()
            self.draw_screen()
    
    def handle_terminal_input(self):
        term = self.terminal
        
        if term.keyboard_visible:
            self.handle_keyboard_input()
        else:
            self.handle_terminal_mode_input()
    
    def handle_keyboard_input(self):
        term = self.terminal
        
        if self.button_pressed(KEY3_PIN, 0.18):
            if term.kb_row == 4:
                key = self.keyboard_bottom_row[term.kb_col]
            else:
                current_layout = self.keyboard_layouts[term.kb_page]
                key = current_layout[term.kb_row][term.kb_col]
            
            if key == 'SPC':
                term.command_input = term.command_input[:term.cursor_pos] + ' ' + term.command_input[term.cursor_pos:]
                term.cursor_pos += 1
            elif key == 'CAPS':
                term.caps_lock = not term.caps_lock
            elif key == 'BSP':
                if term.cursor_pos > 0:
                    term.command_input = term.command_input[:term.cursor_pos-1] + term.command_input[term.cursor_pos:]
                    term.cursor_pos -= 1
            elif key == 'CLR':
                term.command_input = ""
                term.cursor_pos = 0
            elif key == '<-':
                term.cursor_pos = max(0, term.cursor_pos - 1)
            elif key == '->':
                term.cursor_pos = min(len(term.command_input), term.cursor_pos + 1)
            elif key == 'MORE':
                term.kb_page = 1 - term.kb_page
                term.kb_row = 0
                term.kb_col = 0
            else:
                # Apply caps lock to letters only
                if term.caps_lock and key.isalpha():
                    key = key.upper()
                term.command_input = term.command_input[:term.cursor_pos] + key + term.command_input[term.cursor_pos:]
                term.cursor_pos += 1
            
            self.draw_screen()
        
        elif self.button_pressed(KEY_PRESS_PIN, 0.15):
            term.keyboard_visible = False
            if term.command_input.strip():
                self.execute_command(term)
            self.draw_screen()
        
        elif self.button_pressed(KEY_UP_PIN, 0.12):
            term.kb_row = max(0, term.kb_row - 1)
            if term.kb_row < 4:
                term.kb_col = min(term.kb_col, len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1)
            else:
                term.kb_col = min(term.kb_col, len(self.keyboard_bottom_row) - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_DOWN_PIN, 0.12):
            term.kb_row = min(4, term.kb_row + 1)
            if term.kb_row < 4:
                term.kb_col = min(term.kb_col, len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1)
            else:
                term.kb_col = min(term.kb_col, len(self.keyboard_bottom_row) - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_LEFT_PIN, 0.12):
            term.kb_col = max(0, term.kb_col - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_RIGHT_PIN, 0.12):
            if term.kb_row < 4:
                term.kb_col = min(len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1, term.kb_col + 1)
            else:
                term.kb_col = min(len(self.keyboard_bottom_row) - 1, term.kb_col + 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY2_PIN, 0.15):
            term.keyboard_visible = False
            self.draw_screen()
    
    def handle_terminal_mode_input(self):
        term = self.terminal
        
        if self.button_pressed(KEY2_PIN, 0.2):
            if term.process:
                try:
                    os.killpg(os.getpgid(term.process.pid), 9)
                    term.output_lines.append("^C Stopped")
                    term.process = None
                except:
                    pass
                self.draw_screen()
            else:
                self.current_screen = "menu"
                self.draw_screen()
            return
        
        if self.button_pressed(KEY3_PIN, 0.2):
            if term.command_input.strip():
                self.execute_command(term)
                self.draw_screen()
            return
        
        if self.button_pressed(KEY_PRESS_PIN, 0.15):
            term.keyboard_visible = True
            term.kb_row = 0
            term.kb_col = 0
            term.scroll_offset = 0
            self.draw_screen()
        
        elif self.button_pressed(KEY_UP_PIN, 0.15):
            max_scroll = max(0, len(term.output_lines) - 6)
            term.scroll_offset = min(term.scroll_offset + 1, max_scroll)
            self.draw_screen()
        
        elif self.button_pressed(KEY_DOWN_PIN, 0.15):
            term.scroll_offset = max(0, term.scroll_offset - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_LEFT_PIN, 0.15):
            if term.command_history:
                if term.history_index < len(term.command_history) - 1:
                    term.history_index += 1
                elif term.history_index == -1:
                    term.history_index = 0
                
                if term.history_index >= 0:
                    term.command_input = term.command_history[-(term.history_index+1)]
                    term.cursor_pos = len(term.command_input)
                self.draw_screen()
        
        elif self.button_pressed(KEY_RIGHT_PIN, 0.15):
            if term.history_index > 0:
                term.history_index -= 1
                term.command_input = term.command_history[-(term.history_index+1)]
                term.cursor_pos = len(term.command_input)
            elif term.history_index == 0:
                term.history_index = -1
                term.command_input = ""
                term.cursor_pos = 0
            self.draw_screen()
    
    def handle_wifi_input(self):
        if self.entering_wifi_password:
            self.handle_wifi_password_input()
        else:
            current_wlan = self.get_current_wlan()
            
            if self.button_pressed(KEY_UP_PIN, 0.15):
                self.wifi_menu_section = max(0, self.wifi_menu_section - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_DOWN_PIN, 0.15):
                max_section = 2
                if self.wlan_enabled[current_wlan]:
                    max_section = 2 + len(self.wifi_networks[current_wlan])
                self.wifi_menu_section = min(max_section, self.wifi_menu_section + 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY3_PIN, 0.15):
                if self.wifi_menu_section == 0:
                    self.current_wlan_idx = (self.current_wlan_idx + 1) % len(self.available_wlans)
                    new_wlan = self.get_current_wlan()
                    if self.wlan_enabled[new_wlan]:
                        self.scan_wifi(new_wlan)
                    self.wifi_menu_section = 0
                
                elif self.wifi_menu_section == 1:
                    self.toggle_wlan(current_wlan)
                    time.sleep(0.5)
                    self.check_all_wlan_status()
                    if self.wlan_enabled[current_wlan]:
                        self.scan_wifi(current_wlan)
                
                elif self.wifi_menu_section == 2:
                    if self.wifi_connected[current_wlan]:
                        self.disconnect_wifi(current_wlan)
                        time.sleep(0.5)
                        self.check_all_wlan_status()
                
                else:
                    net_idx = self.wifi_menu_section - 3
                    if 0 <= net_idx < len(self.wifi_networks[current_wlan]):
                        self.entering_wifi_password = True
                        self.wifi_password_input = ""
                        self.terminal.kb_row = 0
                        self.terminal.kb_col = 0
                        self.terminal.kb_page = 0
                        self.terminal.caps_lock = False
                
                self.draw_screen()
            
            elif self.button_pressed(KEY2_PIN, 0.15):
                self.current_screen = "menu"
                self.draw_screen()
    
    def handle_wifi_password_input(self):
        term = self.terminal
        
        if self.button_pressed(KEY3_PIN, 0.18):
            if term.kb_row == 4:
                key = self.keyboard_bottom_row[term.kb_col]
            else:
                current_layout = self.keyboard_layouts[term.kb_page]
                key = current_layout[term.kb_row][term.kb_col]
            
            if key == 'SPC':
                self.wifi_password_input += ' '
            elif key == 'CAPS':
                term.caps_lock = not term.caps_lock
            elif key == 'BSP':
                self.wifi_password_input = self.wifi_password_input[:-1]
            elif key == 'CLR':
                self.wifi_password_input = ""
            elif key == 'MORE':
                term.kb_page = 1 - term.kb_page
                term.kb_row = 0
                term.kb_col = 0
            elif key not in ['<-', '->']:
                if term.caps_lock and key.isalpha():
                    key = key.upper()
                self.wifi_password_input += key
            
            self.draw_screen()
        
        elif self.button_pressed(KEY_PRESS_PIN, 0.15):
            current_wlan = self.get_current_wlan()
            net_idx = self.wifi_menu_section - 3
            if 0 <= net_idx < len(self.wifi_networks[current_wlan]) and self.wifi_password_input:
                selected_net = self.wifi_networks[current_wlan][net_idx]
                self.connect_wifi(current_wlan, selected_net['ssid'], self.wifi_password_input)
                time.sleep(2)
                self.check_all_wlan_status()
                self.wifi_menu_section = 2
            
            self.entering_wifi_password = False
            self.wifi_password_input = ""
            term.caps_lock = False
            self.draw_screen()
        
        elif self.button_pressed(KEY_UP_PIN, 0.12):
            term.kb_row = max(0, term.kb_row - 1)
            if term.kb_row < 4:
                term.kb_col = min(term.kb_col, len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1)
            else:
                term.kb_col = min(term.kb_col, len(self.keyboard_bottom_row) - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_DOWN_PIN, 0.12):
            term.kb_row = min(4, term.kb_row + 1)
            if term.kb_row < 4:
                term.kb_col = min(term.kb_col, len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1)
            else:
                term.kb_col = min(term.kb_col, len(self.keyboard_bottom_row) - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_LEFT_PIN, 0.12):
            term.kb_col = max(0, term.kb_col - 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY_RIGHT_PIN, 0.12):
            if term.kb_row < 4:
                term.kb_col = min(len(self.keyboard_layouts[term.kb_page][term.kb_row]) - 1, term.kb_col + 1)
            else:
                term.kb_col = min(len(self.keyboard_bottom_row) - 1, term.kb_col + 1)
            self.draw_screen()
        
        elif self.button_pressed(KEY2_PIN, 0.15):
            self.entering_wifi_password = False
            self.wifi_password_input = ""
            term.caps_lock = False
            self.draw_screen()
    
    def handle_settings_input(self):
        if self.in_theme_select:
            if self.button_pressed(KEY_UP_PIN, 0.15):
                self.theme_select_index = max(0, self.theme_select_index - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_DOWN_PIN, 0.15):
                self.theme_select_index = min(len(self.theme_options) - 1, self.theme_select_index + 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY3_PIN, 0.15):
                self.theme = self.theme_options[self.theme_select_index]
                self.in_theme_select = False
                self.draw_screen()
            
            elif self.button_pressed(KEY2_PIN, 0.15):
                self.in_theme_select = False
                self.draw_screen()
        
        elif self.in_brightness_adjust:
            if self.button_pressed(KEY_LEFT_PIN, 0.1):
                self.brightness = max(10, self.brightness - 5)
                self.pwm.ChangeDutyCycle(self.brightness)
                self.draw_screen()
            
            elif self.button_pressed(KEY_RIGHT_PIN, 0.1):
                self.brightness = min(100, self.brightness + 5)
                self.pwm.ChangeDutyCycle(self.brightness)
                self.draw_screen()
            
            elif self.button_pressed(KEY2_PIN, 0.15):
                self.in_brightness_adjust = False
                self.draw_screen()
        
        else:
            if self.button_pressed(KEY_UP_PIN, 0.15):
                self.settings_menu_index = max(0, self.settings_menu_index - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_DOWN_PIN, 0.15):
                self.settings_menu_index = min(1, self.settings_menu_index + 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY3_PIN, 0.15):
                if self.settings_menu_index == 0:
                    self.in_theme_select = True
                    self.theme_select_index = self.theme_options.index(self.theme)
                elif self.settings_menu_index == 1:
                    self.in_brightness_adjust = True
                self.draw_screen()
            
            elif self.button_pressed(KEY2_PIN, 0.15):
                self.current_screen = "menu"
                self.draw_screen()
    
    # ==================== TERMINAL EXECUTION ====================
    
    def execute_command(self, term):
        if not term.command_input.strip():
            return
        
        cmd = term.command_input.strip()
        
        term.output_lines.append(f"{self.username}$ {cmd}"[:21])
        term.command_history.append(cmd)
        term.history_index = -1
        term.scroll_offset = 0
        
        try:
            parts = cmd.split()
            if not parts:
                return
            
            if parts[0] == 'cd':
                try:
                    pi_home = pwd.getpwnam('pi').pw_dir
                    
                    if len(parts) > 1:
                        target = parts[1]
                        if target.startswith('/'):
                            new_dir = target
                        elif target.startswith('~/'):
                            new_dir = target.replace('~', pi_home)
                        elif target == '~':
                            new_dir = pi_home
                        else:
                            new_dir = os.path.join(term.working_dir, target)
                        
                        os.chdir(new_dir)
                        term.working_dir = os.getcwd()
                        term.output_lines.append(f"-> {term.working_dir[:18]}")
                    else:
                        os.chdir(pi_home)
                        term.working_dir = os.getcwd()
                        term.output_lines.append("-> ~")
                except FileNotFoundError:
                    term.output_lines.append(f"No dir: {parts[1][:12]}")
                except Exception as e:
                    term.output_lines.append(f"Err: {str(e)[:15]}")
            
            elif cmd == 'clear':
                term.output_lines = []
            
            elif cmd == 'pwd':
                term.output_lines.append(term.working_dir[:21])
            
            elif cmd == 'exit':
                self.current_screen = "menu"
            
            else:
                master, slave = pty.openpty()
                term.pty_master = master
                term.pty_slave = slave
                
                term.process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    cwd=term.working_dir,
                    preexec_fn=os.setsid,
                    close_fds=True
                )
                
                os.close(slave)
                
                flags = fcntl.fcntl(master, fcntl.F_GETFL)
                fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                term.read_thread = threading.Thread(target=self.read_pty_output, args=(term,), daemon=True)
                term.read_thread.start()
                    
        except Exception as e:
            term.output_lines.append(f"Err:{str(e)[:17]}")
        
        term.command_input = ""
        term.cursor_pos = 0
        term.keyboard_visible = False
    
    def read_pty_output(self, term):
        buffer = ""
        
        while term.process and term.process.poll() is None:
            try:
                data = os.read(term.pty_master, 1024).decode('utf-8', errors='ignore')
                buffer += data
                
                while '\n' in buffer or '\r' in buffer:
                    if '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                    else:
                        line, buffer = buffer.split('\r', 1)
                    
                    line = line.strip()
                    if line:
                        while len(line) > 21:
                            term.output_lines.append(line[:21])
                            line = line[21:]
                        if line:
                            term.output_lines.append(line)
                        
                        self.needs_redraw = True
                
                time.sleep(0.05)
            except OSError:
                time.sleep(0.05)
            except:
                break
        
        if buffer.strip():
            lines = buffer.strip().split('\n')
            for line in lines:
                if line.strip():
                    term.output_lines.append(line.strip()[:21])
        
        if term.process:
            returncode = term.process.poll()
            if returncode == 0:
                term.output_lines.append("Done!")
            elif returncode is not None:
                term.output_lines.append(f"Exit:{returncode}")
        
        try:
            os.close(term.pty_master)
        except:
            pass
        
        term.process = None
        term.pty_master = None
        self.needs_redraw = True
    
    def shutdown_pi(self):
        print("\n!!! SHUTDOWN !!!")
        image = Image.new("RGB", (128, 128), "RED")
        draw = ImageDraw.Draw(image)
        draw.text((20, 50), "SHUTTING", fill="WHITE")
        draw.text((30, 65), "DOWN...", fill="WHITE")
        self.LCD.LCD_ShowImage(image, 0, 0)
        time.sleep(2)
        
        self.pwm.stop()
        GPIO.cleanup()
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    
    def reboot_pi(self):
        print("\n!!! REBOOT !!!")
        image = Image.new("RGB", (128, 128), "BLUE")
        draw = ImageDraw.Draw(image)
        draw.text((25, 50), "REBOOTING", fill="WHITE")
        draw.text((35, 65), "NOW...", fill="WHITE")
        self.LCD.LCD_ShowImage(image, 0, 0)
        time.sleep(2)
        
        self.pwm.stop()
        GPIO.cleanup()
        subprocess.run(["sudo", "reboot"])
    
    def run(self):
        print("Pocket Terminal Starting...")
        self.draw_screen()
        
        try:
            while self.running:
                self.handle_input()
                
                if self.needs_redraw:
                    self.draw_screen()
                
                time.sleep(0.02)
        
        except KeyboardInterrupt:
            print("\nExiting...")
        
        finally:
            if self.terminal.process:
                try:
                    os.killpg(os.getpgid(self.terminal.process.pid), 9)
                except:
                    pass
            
            self.pwm.stop()
            GPIO.cleanup()
            print("Terminal stopped")

if __name__ == '__main__':
    terminal = PocketTerminal()
    terminal.run()
