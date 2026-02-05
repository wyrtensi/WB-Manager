import os
import asyncio
import logging
import subprocess
import shutil
import edge_tts
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class TTSManager:
    def __init__(self):
        self.ffmpeg_path = self.find_ffmpeg()

    def find_ffmpeg(self):
        """Finds FFmpeg executable."""
        ffmpeg_paths = [
            "ffmpeg",
            r"C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
        ]
        for path in ffmpeg_paths:
            try:
                result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return path
            except Exception:
                continue
        return None

    async def _generate_audio(self, text, voice, rate, pitch, output_path, volume_db=0):
        if not text.strip():
            text = " "
        
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        
        if volume_db != 0:
            temp_path = str(output_path) + ".temp.mp3"
            await communicate.save(temp_path)
            self.adjust_volume(temp_path, output_path, volume_db)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            await communicate.save(str(output_path))
            
        self.trim_silence(output_path)

    def generate_tts(self, text, output_path, voice="ru-RU-DmitryNeural", rate="+5%", pitch="-10Hz", volume_db=5):
        """Synchronous wrapper for TTS generation."""
        try:
            asyncio.run(self._generate_audio(text, voice, rate, pitch, output_path, volume_db))
            return True, None
        except Exception as e:
            logger.error(f"TTS Generation error: {e}")
            return False, str(e)

    def adjust_volume(self, input_path, output_path, volume_db):
        try:
            if self.ffmpeg_path:
                cmd = [
                    self.ffmpeg_path, "-y", "-i", str(input_path),
                    "-af", f"volume={volume_db}dB",
                    "-c:a", "mp3", str(output_path)
                ]
                subprocess.run(cmd, check=True, capture_output=True)
            else:
                audio = AudioSegment.from_mp3(str(input_path))
                adjusted = audio + volume_db
                adjusted.export(str(output_path), format="mp3")
        except Exception as e:
            logger.error(f"Volume adjustment error: {e}")
            # Fallback copy if failed
            if str(input_path) != str(output_path):
                shutil.copy2(input_path, output_path)

    def trim_silence(self, file_path):
        if not self.ffmpeg_path:
            return
        try:
            temp_path = str(file_path) + ".trim.mp3"
            cmd = [
                self.ffmpeg_path, "-y", "-i", str(file_path),
                "-af", "silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-50dB",
                temp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            if os.path.exists(temp_path):
                shutil.move(temp_path, file_path)
        except Exception as e:
            logger.error(f"Trim silence error: {e}")
