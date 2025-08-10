"""
Komponent do odtwarzania wideo w interfejsie
"""

import streamlit as st
import base64
from pathlib import Path

class VideoPlayer:
    """Komponent do odtwarzania wideo"""
    
    @staticmethod
    def render_video_player(video_path: str, width: int = 640):
        """
        Renderuj odtwarzacz wideo
        
        Args:
            video_path: Ścieżka do pliku wideo
            width: Szerokość odtwarzacza
        """
        try:
            # Sprawdź czy plik istnieje
            if not Path(video_path).exists():
                st.error("❌ Plik wideo nie został znaleziony")
                return
            
            # Odczytaj plik wideo
            with open(video_path, 'rb') as video_file:
                video_bytes = video_file.read()
            
            # Wyświetl wideo
            st.video(video_bytes)
            
        except Exception as e:
            st.error(f"❌ Błąd podczas ładowania wideo: {str(e)}")
    
    @staticmethod
    def render_video_with_download(video_path: str, filename: str = "video.mp4"):
        """
        Renderuj odtwarzacz wideo z opcją pobierania
        
        Args:
            video_path: Ścieżka do pliku wideo
            filename: Nazwa pliku do pobrania
        """
        try:
            # Wyświetl wideo
            VideoPlayer.render_video_player(video_path)
            
            # Przycisk pobierania
            with open(video_path, 'rb') as video_file:
                video_bytes = video_file.read()
            
            st.download_button(
                label="📥 Pobierz wideo",
                data=video_bytes,
                file_name=filename,
                mime="video/mp4",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Błąd podczas przygotowywania wideo: {str(e)}")
    
    @staticmethod
    def get_video_thumbnail(video_path: str) -> str:
        """
        Pobierz miniaturę wideo (placeholder - wymaga implementacji z FFmpeg)
        
        Args:
            video_path: Ścieżka do pliku wideo
            
        Returns:
            Base64 encoded thumbnail lub placeholder
        """
        # TODO: Implementacja generowania miniatur z FFmpeg
        # Na razie zwracamy placeholder
        return "data:image/svg+xml;base64," + base64.b64encode(
            b'<svg width="320" height="240" xmlns="http://www.w3.org/2000/svg">'
            b'<rect width="100%" height="100%" fill="#f0f0f0"/>'
            b'<text x="50%" y="50%" text-anchor="middle" dy=".3em" font-family="Arial" font-size="16">Video Thumbnail</text>'
            b'</svg>'
        ).decode()