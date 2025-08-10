"""
Serwis do przetwarzania plików wideo
Obsługuje ekstrakcję audio, dodawanie napisów, i podstawowe operacje na wideo
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import ffmpeg

from ..utils.logger import get_logger

logger = get_logger(__name__)

class VideoProcessor:
    """Klasa do przetwarzania plików wideo"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Pobierz informacje o pliku wideo
        
        Args:
            video_path: Ścieżka do pliku wideo
            
        Returns:
            Słownik z informacjami o wideo
        """
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if not video_stream:
                return {}
            
            duration = float(probe['format']['duration'])
            duration_str = f"{int(duration // 3600):02d}:{int((duration % 3600) // 60):02d}:{int(duration % 60):02d}"
            
            return {
                'duration': duration_str,
                'duration_seconds': duration,
                'resolution': f"{video_stream['width']}x{video_stream['height']}",
                'fps': eval(video_stream['r_frame_rate']),
                'codec': video_stream['codec_name'],
                'bitrate': probe['format'].get('bit_rate', 'N/A')
            }
            
        except Exception as e:
            logger.error(f"Błąd podczas pobierania informacji o wideo: {e}")
            return {}
    
    def extract_audio(self, video_path: str, output_format: str = 'wav') -> str:
        """
        Ekstraktuj audio z pliku wideo
        
        Args:
            video_path: Ścieżka do pliku wideo
            output_format: Format wyjściowy audio (wav, mp3, etc.)
            
        Returns:
            Ścieżka do wyekstraktowanego pliku audio
        """
        try:
            # Stwórz unikalną nazwę pliku audio
            audio_filename = f"audio_{os.path.basename(video_path).rsplit('.', 1)[0]}.{output_format}"
            audio_path = os.path.join(self.temp_dir, audio_filename)
            
            # Usuń plik jeśli już istnieje
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            # Ekstraktuj audio używając ffmpeg
            (
                ffmpeg
                .input(video_path)
                .output(
                    audio_path,
                    acodec='pcm_s16le',  # WAV format
                    ac=1,  # Mono
                    ar=16000  # 16kHz sample rate (optymalne dla ASR)
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"Audio wyekstraktowane do: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Błąd podczas ekstrakcji audio: {e}")
            raise Exception(f"Nie można wyekstraktować audio z wideo: {e}")
    
    def add_subtitles_to_video(self, video_path: str, subtitle_content: str, subtitle_format: str = 'SRT') -> str:
        """
        Dodaj napisy do wideo
        
        Args:
            video_path: Ścieżka do pliku wideo
            subtitle_content: Zawartość napisów
            subtitle_format: Format napisów (SRT, VTT, ASS)
            
        Returns:
            Ścieżka do wideo z napisami
        """
        try:
            # Stwórz plik z napisami
            subtitle_ext = subtitle_format.lower()
            subtitle_filename = f"subtitles_{os.path.basename(video_path).rsplit('.', 1)[0]}.{subtitle_ext}"
            subtitle_path = os.path.join(self.temp_dir, subtitle_filename)
            
            with open(subtitle_path, 'w', encoding='utf-8') as f:
                f.write(subtitle_content)
            
            # Stwórz nazwę pliku wyjściowego
            output_filename = f"output_with_subs_{os.path.basename(video_path)}"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            # Usuń plik wyjściowy jeśli już istnieje
            if os.path.exists(output_path):
                os.remove(output_path)
            
            # Dodaj napisy do wideo
            if subtitle_format.upper() == 'SRT':
                # Dla SRT używamy filtru subtitles z escapowaniem ścieżki
                subtitle_path_escaped = subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
                (
                    ffmpeg
                    .input(video_path)
                    .output(
                        output_path,
                        vf=f"subtitles='{subtitle_path_escaped}':force_style='FontSize=16,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=1'",
                        vcodec='libx264',
                        acodec='copy',
                        preset='fast'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # Dla innych formatów
                subtitle_path_escaped = subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
                (
                    ffmpeg
                    .input(video_path)
                    .output(
                        output_path,
                        vf=f"subtitles='{subtitle_path_escaped}'",
                        vcodec='libx264',
                        acodec='copy',
                        preset='fast'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            
            logger.info(f"Wideo z napisami utworzone: {output_path}")
            
            # Wyczyść plik napisów
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)
            
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"Błąd FFmpeg podczas dodawania napisów: {e}")
            logger.error(f"FFmpeg stderr: {e.stderr.decode() if e.stderr else 'Brak stderr'}")
            raise Exception(f"Błąd FFmpeg: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            logger.error(f"Błąd podczas dodawania napisów do wideo: {e}")
            raise Exception(f"Nie można dodać napisów do wideo: {e}")
    
    def validate_video_file(self, video_path: str) -> bool:
        """
        Sprawdź czy plik wideo jest prawidłowy
        
        Args:
            video_path: Ścieżka do pliku wideo
            
        Returns:
            True jeśli plik jest prawidłowy, False w przeciwnym razie
        """
        try:
            probe = ffmpeg.probe(video_path)
            video_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'video']
            return len(video_streams) > 0
            
        except Exception as e:
            logger.error(f"Błąd podczas walidacji pliku wideo: {e}")
            return False
    
    def get_supported_formats(self) -> list:
        """
        Pobierz listę obsługiwanych formatów wideo
        
        Returns:
            Lista obsługiwanych rozszerzeń plików
        """
        return [
            'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 
            'm4v', '3gp', 'ogv', 'ts', 'mts', 'm2ts'
        ]