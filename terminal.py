import LCD_1in44
import time
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
import subprocess
import shlex
import os
import getpass
import sys
import pwd

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
    def __init__(self, terminal_id):
        self.terminal_id = terminal_id
        self.command_input = ""
        self.cursor_pos = 0
        self.output_lines = []
        self.command_history = []
        self.history_index = -1
        self.keyboard_visible = False
        self.kb_row = 0
        self.kb_col = 0
        self.scroll_offset = 0
        self.running_process = None
        self.process_start_time = 0
        try:
            pi_home = pwd.getpwnam('pi').pw_dir
            self.working_dir = pi_home
        except:
            self.working_dir = "/home/pi"

class VirtualTerminal:
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
        GPIO.output(BACKLIGHT_PIN, GPIO.HIGH)
        
        self.username = 'pi'
        try:
            pi_home = pwd.getpwnam('pi').pw_dir
            os.chdir(pi_home)
        except:
            os.chdir("/home/pi")
        
        self.terminals = [Terminal(1), Terminal(2)]
        self.active_terminal = 0
        
        self.keyboard_layout = [
            ['a','b','c','d','e','f','g','h','i','j','k','l','m'],
            ['n','o','p','q','r','s','t','u','v','w','x','y','z'],
            ['0','1','2','3','4','5','6','7','8','9','.','-','_'],
            ['/','~','&','|','>','<','<-','->','SPC','BSP','CLR']
        ]
        
        self.button_prev = {}
        self.button_time = {}
        for pin in input_pins:
            self.button_prev[pin] = GPIO.HIGH
            self.button_time[pin] = 0
        
        self.key1_long_start = 0
        self.shutdown_threshold = 5.0
        
        self.screen_on = True
        self.running = True
        self.last_draw_time = 0
    
    def get_current_terminal(self):
        return self.terminals[self.active_terminal]
    
    def get_prompt(self):
        return f"{self.username} $"
    
    def get_full_path_display(self):
        term = self.terminals[self.active_terminal]
        cwd = term.working_dir
        try:
            pi_home = pwd.getpwnam('pi').pw_dir
        except:
            pi_home = "/home/pi"
        
        if cwd == pi_home:
            return "~"
        elif cwd.startswith(pi_home + "/"):
            return "~/" + cwd[len(pi_home)+1:]
        return cwd
    
    def draw_screen(self):
        if not self.screen_on:
            image = Image.new("RGB", (self.LCD.width, self.LCD.height), "BLACK")
            self.LCD.LCD_ShowImage(image, 0, 0)
            return
            
        image = Image.new("RGB", (self.LCD.width, self.LCD.height), "BLACK")
        draw = ImageDraw.Draw(image)
        
        term = self.get_current_terminal()
        
        term_text = f"Terminal {self.active_terminal + 1}"
        if term.running_process and term.running_process.poll() is None:
            draw.rectangle([(0, 0), (127, 11)], fill="ORANGE")
            draw.text((2, 1), term_text + " [RUN]", fill="WHITE")
        else:
            draw.rectangle([(0, 0), (127, 11)], fill="BLUE")
            draw.text((2, 1), term_text, fill="WHITE")
        
        if term.keyboard_visible:
            self.draw_terminal_with_keyboard(draw, term)
        else:
            self.draw_terminal_only(draw, term)
        
        self.LCD.LCD_ShowImage(image, 0, 0)
        self.last_draw_time = time.time()
    
    def draw_terminal_only(self, draw, term):
        max_lines = 6
        total_lines = len(term.output_lines)
        start_idx = max(0, total_lines - max_lines - term.scroll_offset)
        end_idx = total_lines - term.scroll_offset
        visible_lines = term.output_lines[start_idx:end_idx]
        
        y_pos = 14
        for line in visible_lines:
            display_line = line[:21] if len(line) > 21 else line
            draw.text((2, y_pos), display_line, fill="GREEN")
            y_pos += 15
        
        input_y = 104
        draw.rectangle([(0, input_y-2), (127, 127)], fill="NAVY")
        
        prompt = self.get_prompt()
        draw.text((2, input_y), prompt, fill="CYAN")
        
        prompt_width = len(prompt) * 6
        available_width = 127 - prompt_width - 2
        max_chars = available_width // 6
        
        if len(term.command_input) > max_chars:
            visible_start = max(0, term.cursor_pos - max_chars + 3)
            visible_text = term.command_input[visible_start:visible_start + max_chars]
            cursor_offset = min(term.cursor_pos - visible_start, max_chars)
        else:
            visible_text = term.command_input
            cursor_offset = term.cursor_pos
        
        display_text = visible_text.replace(' ', '_')
        draw.text((prompt_width + 2, input_y), display_text, fill="WHITE")
        
        if int(time.time() * 2) % 2 == 0:
            cursor_x = prompt_width + 2 + cursor_offset * 6
            draw.rectangle([(cursor_x, input_y), (cursor_x+5, input_y+11)], fill="YELLOW")
            if cursor_offset < len(display_text):
                draw.text((cursor_x, input_y), display_text[cursor_offset], fill="BLACK")
    
    def draw_terminal_with_keyboard(self, draw, term):
        y_pos = 14
        display_lines = term.output_lines[-1:]
        for line in display_lines:
            draw.text((2, y_pos), line[:21], fill="GREEN")
        
        prompt = self.get_prompt()
        draw.text((2, 29), prompt, fill="CYAN")
        
        prompt_width = len(prompt) * 6
        
        display_text = term.command_input[:18].replace(' ', '_')
        draw.text((prompt_width + 2, 29), display_text, fill="WHITE")
        
        cursor_x = prompt_width + 2 + (term.cursor_pos * 6)
        draw.line([(cursor_x, 29), (cursor_x, 39)], fill="YELLOW", width=2)
        
        draw.line([(0, 40), (127, 40)], fill="CYAN", width=1)
        
        y_kb = 42
        for r, row in enumerate(self.keyboard_layout):
            x_kb = 0
            
            for c, key in enumerate(row):
                if r < 3:
                    width = 9
                else:
                    if key in ['/','~','&','|','>','<']:
                        width = 9
                    elif key in ['<-', '->']:
                        width = 11
                    elif key == 'SPC':
                        width = 17
                    elif key in ['BSP', 'CLR']:
                        width = 17
                    else:
                        width = 9
                
                if x_kb + width > 128:
                    break
                
                if r == term.kb_row and c == term.kb_col:
                    draw.rectangle([(x_kb, y_kb), (x_kb+width, y_kb+20)], fill="YELLOW", outline="YELLOW")
                    draw.rectangle([(x_kb+1, y_kb+1), (x_kb+width-1, y_kb+19)], fill="BLACK")
                    text_color = "YELLOW"
                else:
                    draw.rectangle([(x_kb, y_kb), (x_kb+width, y_kb+20)], fill="DARKGRAY", outline="WHITE")
                    text_color = "WHITE"
                
                if len(key) == 1:
                    text_x = x_kb + (width // 2) - 2
                elif key in ['<-', '->']:
                    text_x = x_kb + 2
                elif key in ['SPC', 'BSP', 'CLR']:
                    text_x = x_kb + 2
                else:
                    text_x = x_kb + 3
                
                draw.text((text_x, y_kb+6), key, fill=text_color)
                
                x_kb += width
            
            y_kb += 21
    
    def button_pressed(self, pin, debounce=0.15):
        """Check if button just pressed with debounce"""
        current = GPIO.input(pin)
        if current == GPIO.LOW and self.button_prev[pin] == GPIO.HIGH:
            if time.time() - self.button_time[pin] >= debounce:
                self.button_prev[pin] = current
                self.button_time[pin] = time.time()
                return True
        self.button_prev[pin] = current
        return False
    
    def check_running_processes(self):
        """Check all terminals for running processes and update output"""
        needs_redraw = False
        
        for term in self.terminals:
            if term.running_process:
                returncode = term.running_process.poll()
                
                if returncode is not None:
                    try:
                        stdout, stderr = term.running_process.communicate(timeout=0.1)
                        
                        if term.output_lines and term.output_lines[-1] == "Running...":
                            term.output_lines.pop()
                        
                        if stdout:
                            lines = stdout.decode('utf-8', errors='ignore').split('\n')
                            for line in lines[-8:]:
                                if line.strip():
                                    term.output_lines.append(line[:21])
                        
                        if stderr:
                            lines = stderr.decode('utf-8', errors='ignore').split('\n')
                            for line in lines[:3]:
                                if line.strip():
                                    term.output_lines.append(f"E:{line[:19]}")
                        
                        if returncode == 0:
                            term.output_lines.append("Done!")
                        else:
                            term.output_lines.append(f"Exit:{returncode}")
                    except:
                        term.output_lines.append("Finished")
                    
                    term.running_process = None
                    needs_redraw = True
        
        return needs_redraw
    
    def handle_input(self):
        current_time = time.time()
        term = self.get_current_terminal()
        
        if GPIO.input(KEY1_PIN) == GPIO.LOW:
            if self.key1_long_start == 0:
                self.key1_long_start = current_time
            elif current_time - self.key1_long_start >= self.shutdown_threshold:
                self.shutdown_pi()
                return
        else:
            self.key1_long_start = 0
        
        if self.button_pressed(KEY2_PIN, 0.2):
            self.active_terminal = 1 - self.active_terminal
            self.draw_screen()
            return
        
        if term.keyboard_visible:
            # === KEYBOARD MODE ===
            
            if self.button_pressed(KEY3_PIN, 0.18):
                key = self.keyboard_layout[term.kb_row][term.kb_col]
                
                if key == 'SPC':
                    term.command_input = term.command_input[:term.cursor_pos] + ' ' + term.command_input[term.cursor_pos:]
                    term.cursor_pos += 1
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
                else:
                    term.command_input = term.command_input[:term.cursor_pos] + key + term.command_input[term.cursor_pos:]
                    term.cursor_pos += 1
                
                self.draw_screen()
            
            elif self.button_pressed(KEY_PRESS_PIN, 0.15):
                term.keyboard_visible = False
                self.draw_screen()
            
            elif self.button_pressed(KEY_UP_PIN, 0.12):
                term.kb_row = max(0, term.kb_row - 1)
                term.kb_col = min(term.kb_col, len(self.keyboard_layout[term.kb_row]) - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_DOWN_PIN, 0.12):
                term.kb_row = min(len(self.keyboard_layout) - 1, term.kb_row + 1)
                term.kb_col = min(term.kb_col, len(self.keyboard_layout[term.kb_row]) - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_LEFT_PIN, 0.12):
                term.kb_col = max(0, term.kb_col - 1)
                self.draw_screen()
            
            elif self.button_pressed(KEY_RIGHT_PIN, 0.12):
                term.kb_col = min(len(self.keyboard_layout[term.kb_row]) - 1, term.kb_col + 1)
                self.draw_screen()
        
        else:
            # === TERMINAL MODE ===
            
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
                    elif term.history_index == -1 and len(term.command_history) > 0:
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
            
            elif self.button_pressed(KEY3_PIN, 0.2):
                if term.running_process and term.running_process.poll() is None:
                    try:
                        term.running_process.terminate()
                        term.output_lines.append("^C Stopped")
                        
                        try:
                            stdout, stderr = term.running_process.communicate(timeout=1)
                            if stdout:
                                lines = stdout.decode('utf-8', errors='ignore').split('\n')
                                for line in lines[-5:]:
                                    if line.strip():
                                        term.output_lines.append(line[:21])
                        except:
                            pass
                        
                        term.running_process = None
                    except:
                        pass
                    self.draw_screen()
                elif term.command_input.strip():
                    self.execute_command(term)
                    self.draw_screen()
    
    def execute_command(self, term):
        if not term.command_input.strip():
            return
        
        cmd = term.command_input.strip()
        path_display = self.get_full_path_display()
        
        term.output_lines.append(f"{self.username}:{path_display}"[:21])
        term.output_lines.append(f"$ {cmd}"[:21])
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
                        term.output_lines.append(f"-> {self.get_full_path_display()}")
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
                self.running = False
            
            else:
                term.output_lines.append("Running...")
                
                term.running_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=term.working_dir
                )
                term.process_start_time = time.time()
                    
        except Exception as e:
            term.output_lines.append(f"Err:{str(e)[:17]}")
        
        term.command_input = ""
        term.cursor_pos = 0
    
    def shutdown_pi(self):
        print("\n!!! SHUTDOWN INITIATED !!!")
        image = Image.new("RGB", (self.LCD.width, self.LCD.height), "RED")
        draw = ImageDraw.Draw(image)
        draw.text((20, 50), "SHUTTING", fill="WHITE")
        draw.text((30, 65), "DOWN...", fill="WHITE")
        self.LCD.LCD_ShowImage(image, 0, 0)
        time.sleep(2)
        
        GPIO.cleanup()
        subprocess.run(["sudo", "shutdown", "-h", "now"])
    
    def run(self):
        print("Dual Terminal Starting...")
        print(f"Directory: {os.getcwd()}")
        self.draw_screen()
        
        try:
            while self.running:
                if self.check_running_processes():
                    self.draw_screen()
                
                self.handle_input()
                
                current_time = time.time()
                term = self.get_current_terminal()
                if term.running_process and term.running_process.poll() is None:
                    if current_time - self.last_draw_time > 2:
                        self.draw_screen()
                
                time.sleep(0.02)
        
        except KeyboardInterrupt:
            print("\nExiting...")
        
        finally:
            for term in self.terminals:
                if term.running_process:
                    try:
                        term.running_process.terminate()
                    except:
                        pass
            
            GPIO.output(BACKLIGHT_PIN, GPIO.HIGH)
            self.LCD.LCD_Clear()
            GPIO.cleanup()
            print("Terminal stopped")

if __name__ == '__main__':
    terminal = VirtualTerminal()
    terminal.run()
