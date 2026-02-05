import subprocess
import sys
import os
import json
import psutil
from pathlib import Path

class BotManager:
    def __init__(self, bot_dir):
        self.bot_dir = Path(bot_dir)
        self.script_path = self.bot_dir / 'wb_telegram_bot.py'
        self.config_file = self.bot_dir / 'bot_config.json'
        self.chat_ids_file = self.bot_dir / 'user_chat_ids.json'
        self.pid_file = self.bot_dir / 'bot.pid'

    def is_running(self):
        """Check if bot is running using PID file"""
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text())
            if psutil.pid_exists(pid):
                # Check if it's actually our python process
                process = psutil.Process(pid)
                # Simple check: command line contains the script name
                cmdline = process.cmdline()
                return any('wb_telegram_bot.py' in arg for arg in cmdline)
            else:
                return False
        except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def start(self):
        """Start the bot process"""
        if self.is_running():
            return True, "Bot is already running"

        try:
            # Use pythonw for no console window on Windows, or python
            python_exe = sys.executable.replace('python.exe', 'pythonw.exe')
            if not os.path.exists(python_exe):
                python_exe = sys.executable

            # Start process detached
            process = subprocess.Popen(
                [python_exe, str(self.script_path)],
                cwd=str(self.bot_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Save PID
            self.pid_file.write_text(str(process.pid))
            return True, "Bot started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        """Stop the bot process"""
        if not self.pid_file.exists():
            return True, "Bot is not running"

        try:
            pid = int(self.pid_file.read_text())
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
            
            if self.pid_file.exists():
                self.pid_file.unlink()
            return True, "Bot stopped"
        except Exception as e:
            return False, str(e)

    def get_config(self):
        """Read config"""
        config = {}
        if self.config_file.exists():
            try:
                config = json.loads(self.config_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        
        # Also read chat IDs to know who is authorized
        chat_ids = {}
        if self.chat_ids_file.exists():
            try:
                chat_ids = json.loads(self.chat_ids_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        
        config['skip_autostart'] = config.get('skip_autostart', False)
        config['user_chat_ids'] = chat_ids
        
        # Read bot state (auth status)
        bot_state_file = self.bot_dir / 'bot_state.json'
        is_authorized = False
        if bot_state_file.exists():
            try:
                state = json.loads(bot_state_file.read_text(encoding='utf-8'))
                # Consider authorized if updated recently (e.g. last 10 mins)
                # But actually the file is only written when checking, so just trust the flag
                is_authorized = state.get('is_authorized', False)
            except Exception:
                pass
        config['is_authorized'] = is_authorized
        
        return config

    def save_config(self, new_config):
        """Save config"""
        # Preserve existing config if partial update
        current = self.get_config()
        
        # Remove read-only fields
        for field in ['user_chat_ids', 'is_authorized']:
            if field in current:
                del current[field]
            if field in new_config:
                del new_config[field]
            
        current.update(new_config)
        
        self.config_file.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), 
            encoding='utf-8'
        )
        return True

    def clear_photos(self):
        """Clear photos folder"""
        config = self.get_config()
        photo_dir_name = config.get('photo_save_path', 'photos')
        photo_dir = self.bot_dir / photo_dir_name
        
        if not photo_dir.exists():
            return 0
            
        count = 0
        for f in photo_dir.glob('*'):
            if f.is_file():
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        return count
