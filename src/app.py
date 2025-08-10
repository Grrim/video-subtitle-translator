"""
Główna aplikacja Streamlit dla systemu tłumaczenia napisów wideo
"""

import streamlit as st
import os
from pathlib import Path
import tempfile
import time
from typing import Optional, Dict, Any

from .services.video_processor import VideoProcessor
from .services.transcription_service import TranscriptionService
from .services.translation_service import TranslationService
from .services.subtitle_generator import SubtitleGenerator
from .utils.config import Config
from .utils.logger import get_logger
from .components.file_uploader import FileUploader
from .components.language_selector import LanguageSelector
from .components.progress_tracker import ProgressTracker
from .components.video_player import VideoPlayer

logger = get_logger(__name__)

class VideoSubtitleApp:
    """Główna klasa aplikacji do tłumaczenia napisów wideo"""
    
    def __init__(self):
        self.config = Config()
        self.video_processor = VideoProcessor()
        self.transcription_service = TranscriptionService(self.config.assemblyai_api_key)
        self.translation_service = TranslationService(self.config.deepl_api_key)
        self.subtitle_generator = SubtitleGenerator()
        
    def run(self):
        """Uruchom główną aplikację"""
        self._setup_page()
        self._render_sidebar()
        self._render_main_content()
    
    def _setup_page(self):
        """Konfiguracja strony Streamlit"""
        st.title("🎬 System Tłumaczenia Napisów Wideo")
        st.markdown("""
        **Profesjonalny system tłumaczenia mowy w treściach wideo**
        
        Wykorzystuje:
        - 🎤 **AssemblyAI** do rozpoznawania mowy (ASR)
        - 🌍 **DeepL** do tłumaczenia maszynowego (MT)
        - 🎥 **FFmpeg** do przetwarzania wideo
        """)
        
        # Sprawdź konfigurację API
        if not self._check_api_configuration():
            st.stop()
    
    def _check_api_configuration(self) -> bool:
        """Sprawdź czy klucze API są skonfigurowane"""
        missing_keys = []
        
        if not self.config.assemblyai_api_key:
            missing_keys.append("AssemblyAI API Key")
        
        if not self.config.deepl_api_key:
            missing_keys.append("DeepL API Key")
        
        if missing_keys:
            st.error(f"❌ Brakuje kluczy API: {', '.join(missing_keys)}")
            st.info("""
            **Jak skonfigurować klucze API:**
            
            1. Stwórz plik `.env` w głównym katalogu projektu
            2. Dodaj następujące linie:
            ```
            ASSEMBLYAI_API_KEY=twój_klucz_assemblyai
            DEEPL_API_KEY=twój_klucz_deepl
            ```
            
            **Gdzie uzyskać klucze:**
            - AssemblyAI: https://www.assemblyai.com/
            - DeepL: https://www.deepl.com/pro-api
            """)
            return False
        
        return True
    
    def _render_sidebar(self):
        """Renderuj panel boczny z ustawieniami"""
        with st.sidebar:
            st.header("⚙️ Ustawienia")
            
            # Wybór języka docelowego
            target_language = LanguageSelector.render_target_language_selector()
            st.session_state.target_language = target_language
            
            # Ustawienia jakości
            st.subheader("🎯 Jakość przetwarzania")
            
            transcription_quality = st.selectbox(
                "Jakość transkrypcji",
                ["standard", "premium"],
                help="Premium oferuje lepszą jakość ale jest droższy"
            )
            
            translation_formality = st.selectbox(
                "Formalność tłumaczenia",
                ["default", "more", "less"],
                help="Poziom formalności w tłumaczeniu"
            )
            
            # Ustawienia napisów
            st.subheader("📝 Ustawienia napisów")
            
            subtitle_format = st.selectbox(
                "Format napisów",
                ["SRT", "VTT", "ASS"],
                help="Format pliku z napisami"
            )
            
            max_chars_per_line = st.slider(
                "Maksymalna długość linii",
                20, 80, 42,
                help="Maksymalna liczba znaków w linii napisu"
            )
            
            # Zapisz ustawienia w session_state
            st.session_state.update({
                'transcription_quality': transcription_quality,
                'translation_formality': translation_formality,
                'subtitle_format': subtitle_format,
                'max_chars_per_line': max_chars_per_line
            })
    
    def _render_main_content(self):
        """Renderuj główną zawartość aplikacji"""
        # Upload pliku wideo
        uploaded_file = FileUploader.render_video_uploader()
        
        if uploaded_file is not None:
            self._process_video_workflow(uploaded_file)
    
    def _process_video_workflow(self, uploaded_file):
        """Główny workflow przetwarzania wideo"""
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📹 Podgląd wideo")
            
            # Zapisz przesłany plik tymczasowo
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(uploaded_file.read())
                video_path = tmp_file.name
            
            # Wyświetl odtwarzacz wideo
            VideoPlayer.render_video_player(video_path)
            
            # Przycisk do rozpoczęcia przetwarzania
            if st.button("🚀 Rozpocznij przetwarzanie", type="primary", use_container_width=True):
                self._start_processing(video_path, uploaded_file.name)
        
        with col2:
            st.subheader("ℹ️ Informacje o pliku")
            
            # Informacje o pliku
            file_info = self.video_processor.get_video_info(video_path)
            if file_info:
                st.write(f"**Nazwa:** {uploaded_file.name}")
                st.write(f"**Rozmiar:** {uploaded_file.size / (1024*1024):.1f} MB")
                st.write(f"**Czas trwania:** {file_info.get('duration', 'N/A')}")
                st.write(f"**Rozdzielczość:** {file_info.get('resolution', 'N/A')}")
                st.write(f"**FPS:** {file_info.get('fps', 'N/A')}")
    
    def _start_processing(self, video_path: str, original_filename: str):
        """Rozpocznij przetwarzanie wideo"""
        progress_tracker = ProgressTracker()
        
        try:
            # Krok 1: Ekstrakcja audio
            progress_tracker.update_progress(0.1, "🎵 Ekstraktowanie audio z wideo...")
            audio_path = self.video_processor.extract_audio(video_path)
            
            # Krok 2: Transkrypcja
            progress_tracker.update_progress(0.3, "🎤 Transkrypcja audio (AssemblyAI)...")
            transcript = self.transcription_service.transcribe_audio(
                audio_path,
                quality=st.session_state.get('transcription_quality', 'standard')
            )
            
            # Krok 3: Tłumaczenie
            progress_tracker.update_progress(0.6, "🌍 Tłumaczenie tekstu (DeepL)...")
            translated_text = self.translation_service.translate_text(
                transcript['text'],
                target_language=st.session_state.get('target_language', 'PL'),
                formality=st.session_state.get('translation_formality', 'default')
            )
            
            # Krok 4: Generowanie napisów
            progress_tracker.update_progress(0.8, "📝 Generowanie napisów...")
            subtitle_content = self.subtitle_generator.generate_subtitles(
                transcript['segments'],
                translated_text,
                format=st.session_state.get('subtitle_format', 'SRT'),
                max_chars_per_line=st.session_state.get('max_chars_per_line', 42)
            )
            
            # Krok 5: Tworzenie wideo z napisami
            progress_tracker.update_progress(0.9, "🎬 Tworzenie wideo z napisami...")
            output_video_path = self.video_processor.add_subtitles_to_video(
                video_path,
                subtitle_content,
                st.session_state.get('subtitle_format', 'SRT')
            )
            
            # Krok 6: Zakończenie
            progress_tracker.update_progress(1.0, "✅ Przetwarzanie zakończone!")
            
            # Wyświetl rezultaty
            self._display_results(output_video_path, subtitle_content, original_filename)
            
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania: {str(e)}")
            st.error(f"❌ Wystąpił błąd: {str(e)}")
        
        finally:
            # Wyczyść pliki tymczasowe
            self._cleanup_temp_files([video_path, audio_path if 'audio_path' in locals() else None])
    
    def _display_results(self, output_video_path: str, subtitle_content: str, original_filename: str):
        """Wyświetl rezultaty przetwarzania"""
        st.success("🎉 Przetwarzanie zakończone pomyślnie!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎬 Wideo z napisami")
            VideoPlayer.render_video_player(output_video_path)
            
            # Przycisk pobierania wideo
            with open(output_video_path, 'rb') as f:
                st.download_button(
                    label="📥 Pobierz wideo z napisami",
                    data=f.read(),
                    file_name=f"translated_{original_filename}",
                    mime="video/mp4"
                )
        
        with col2:
            st.subheader("📝 Napisy")
            st.text_area(
                "Wygenerowane napisy:",
                subtitle_content,
                height=300,
                help="Możesz skopiować napisy lub pobrać jako plik"
            )
            
            # Przycisk pobierania napisów
            subtitle_filename = f"subtitles_{original_filename.rsplit('.', 1)[0]}.{st.session_state.get('subtitle_format', 'srt').lower()}"
            st.download_button(
                label="📥 Pobierz napisy",
                data=subtitle_content,
                file_name=subtitle_filename,
                mime="text/plain"
            )
    
    def _cleanup_temp_files(self, file_paths: list):
        """Wyczyść pliki tymczasowe"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Nie można usunąć pliku tymczasowego {file_path}: {e}")

def run_app():
    """Funkcja uruchamiająca aplikację"""
    app = VideoSubtitleApp()
    app.run()