"""
Główna aplikacja Streamlit dla systemu tłumaczenia napisów wideo
"""

import streamlit as st
import os
from pathlib import Path
import tempfile
import time
from typing import Optional, Dict, Any, List, Callable, Tuple

from .services.video_processor import VideoProcessor
from .services.transcription_service import TranscriptionService
from .services.translation_service import TranslationService
from .services.subtitle_generator import SubtitleGenerator
from .services.quality_control import QualityController, QualityFlag
from .services.retry_manager import RetryManager, RetryConfig, SegmentReprocessor
from .services.audio_sync_manager import AudioSyncManager
from .services.word_level_sync import WordLevelSynchronizer
from .services.advanced_word_processor import AdvancedWordProcessor
from .services.smooth_subtitle_renderer import SmoothSubtitleRenderer, SmoothSubtitleConfig
from .services.utterance_segmentation import UtteranceSegmentator
from .services.timestamp_debugger import TimestampDebugger
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
        
        # Nowe komponenty kontroli jakości
        self.quality_controller = QualityController()
        self.retry_manager = RetryManager(RetryConfig(max_retries=3, confidence_threshold=0.7))
        self.segment_reprocessor = SegmentReprocessor(self.retry_manager)
        self.audio_sync_manager = AudioSyncManager()
        self.word_level_sync = WordLevelSynchronizer()
        self.advanced_word_processor = AdvancedWordProcessor()
        self.smooth_renderer = SmoothSubtitleRenderer()
        self.utterance_segmentator = UtteranceSegmentator()
        self.timestamp_debugger = TimestampDebugger()
        
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
            
            # Nowe ustawienia kontroli jakości
            st.subheader("🔍 Kontrola jakości")
            
            enable_quality_control = st.checkbox(
                "Włącz kontrolę jakości",
                value=True,
                help="Automatyczna walidacja i kontrola jakości na każdym etapie"
            )
            
            enable_speaker_detection = st.checkbox(
                "Wykrywanie mówiących",
                value=True,
                help="Identyfikacja różnych mówiących w nagraniu"
            )
            
            enable_auto_retry = st.checkbox(
                "Automatyczne ponowne próby",
                value=True,
                help="Automatyczne ponowne przetwarzanie w przypadku błędów"
            )
            
            enable_audio_sync = st.checkbox(
                "Precyzyjna synchronizacja audio",
                value=True,
                help="Automatyczna korekta synchronizacji między dźwiękiem a napisami"
            )
            
            enable_word_level = st.checkbox(
                "Napisy na poziomie słów",
                value=True,
                help="Wyświetlaj słowa stopniowo, jak dochodzą do zdania"
            )
            
            enable_advanced_processing = st.checkbox(
                "🚀 Zaawansowany post-processing",
                value=True,
                help="Napraw nakładania, minimalne przerwy (20ms), stabilizacja bloków (38 słów), korekta offsetu"
            )
            
            enable_utterance_segmentation = st.checkbox(
                "Segmentacja na utterances (wypowiedzi)",
                value=True,
                help="Automatyczny podział na naturalne wypowiedzi na podstawie pauz w mowie"
            )
            
            word_display_mode = st.selectbox(
                "Tryb wyświetlania słów",
                ["smooth_progressive", "stable_blocks", "fade_transitions", "youtube_style", "individual"],
                help="Smooth progressive: płynne bez migotania, Stable blocks: stabilne bloki, Fade transitions: z efektami"
            )
            
            max_words_on_screen = st.slider(
                "Maksymalna liczba słów na ekranie",
                3, 15, 8,
                help="Ile słów może być jednocześnie widocznych (jak na YouTube)"
            )
            
            # Ustawienia jakości napisów
            st.subheader("✨ Jakość napisów")
            
            enable_anti_flicker = st.checkbox(
                "Eliminacja migotania",
                value=True,
                help="Usuwa migotanie i poprawia płynność napisów"
            )
            
            subtitle_quality = st.selectbox(
                "Jakość napisów",
                ["standard", "high", "premium"],
                index=1,
                help="Standard: podstawowe SRT, High: SRT z stylizacją, Premium: ASS z efektami"
            )
            
            min_display_duration = st.slider(
                "Minimalna długość wyświetlania (s)",
                0.2, 1.0, 0.4, 0.1,
                help="Minimalna długość wyświetlania każdego napisu"
            )
            
            confidence_threshold = st.slider(
                "Próg pewności",
                0.5, 1.0, 0.7, 0.05,
                help="Minimalny poziom pewności dla akceptacji wyników"
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
                'max_chars_per_line': max_chars_per_line,
                'enable_quality_control': enable_quality_control,
                'enable_speaker_detection': enable_speaker_detection,
                'enable_auto_retry': enable_auto_retry,
                'enable_audio_sync': enable_audio_sync,
                'enable_word_level': enable_word_level,
                'enable_advanced_processing': enable_advanced_processing,
                'enable_utterance_segmentation': enable_utterance_segmentation,
                'word_display_mode': word_display_mode,
                'max_words_on_screen': max_words_on_screen,
                'enable_anti_flicker': enable_anti_flicker,
                'subtitle_quality': subtitle_quality,
                'min_display_duration': min_display_duration,
                'confidence_threshold': confidence_threshold
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
            
            # Krok 4: Precyzyjna synchronizacja audio-napisy
            if st.session_state.get('enable_audio_sync', True):
                progress_tracker.update_progress(0.65, "🎵 Analiza cech audio...")
                
                # Analizuj cechy audio
                audio_features = self.audio_sync_manager.analyze_audio_features(audio_path)
                
                progress_tracker.update_progress(0.7, "🔄 Obliczanie korekty synchronizacji...")
                
                # Przygotuj segmenty z tłumaczeniem dla synchronizacji
                segments_for_sync = []
                for i, segment in enumerate(transcript['segments']):
                    sync_segment = segment.copy()
                    # Użyj prostego podziału tłumaczenia na segmenty
                    words = translated_text.split()
                    words_per_segment = len(words) // len(transcript['segments'])
                    start_word = i * words_per_segment
                    end_word = (i + 1) * words_per_segment if i < len(transcript['segments']) - 1 else len(words)
                    sync_segment['text'] = ' '.join(words[start_word:end_word])
                    segments_for_sync.append(sync_segment)
                
                # Oblicz korekcję synchronizacji
                sync_correction = self.audio_sync_manager.calculate_sync_offset(
                    audio_features, segments_for_sync
                )
                
                if sync_correction.confidence > 0.3:  # Obniżony próg
                    if sync_correction.confidence > 0.6:
                        st.success(f"🎯 Wykryto precyzyjne przesunięcie: {sync_correction.offset_seconds:.2f}s "
                                 f"(pewność: {sync_correction.confidence:.1%}, metoda: {sync_correction.method})")
                    else:
                        st.info(f"🎯 Wykryto przybliżone przesunięcie: {sync_correction.offset_seconds:.2f}s "
                               f"(pewność: {sync_correction.confidence:.1%}, metoda: {sync_correction.method})")
                    
                    # Zastosuj korekcję synchronizacji
                    corrected_segments = self.audio_sync_manager.apply_sync_correction(
                        segments_for_sync, sync_correction
                    )
                    
                    # Precyzyjne dostrojenie timingu
                    corrected_segments = self.audio_sync_manager.fine_tune_segment_timing(
                        corrected_segments, audio_features
                    )
                    
                    # Waliduj jakość synchronizacji
                    sync_quality = self.audio_sync_manager.validate_sync_quality(
                        corrected_segments, audio_features
                    )
                    
                    if sync_quality['sync_quality'] in ['excellent', 'good']:
                        st.success(f"✅ Synchronizacja: {sync_quality['sync_quality']} "
                                  f"(pokrycie: {sync_quality['coverage']:.1%})")
                    else:
                        st.warning(f"⚠️ Synchronizacja: {sync_quality['sync_quality']} "
                                  f"(pokrycie: {sync_quality['coverage']:.1%})")
                    
                    # Użyj skorygowanych segmentów
                    transcript['segments'] = corrected_segments
                else:
                    st.warning(f"⚠️ Bardzo niska pewność synchronizacji ({sync_correction.confidence:.1%})")
                    st.info("💡 Używam oryginalnych czasów segmentów - synchronizacja może być mniej precyzyjna")
                    # Nie stosuj korekty, ale kontynuuj z oryginalnymi segmentami
            
            # Krok 5: Segmentacja na utterances (jeśli włączona)
            if st.session_state.get('enable_utterance_segmentation', True):
                progress_tracker.update_progress(0.75, "🗣️ Segmentacja na naturalne wypowiedzi...")
                
                # Segmentuj na utterances
                utterance_segments = self.utterance_segmentator.segment_by_utterances(transcript)
                
                # Pobierz statystyki pauz
                pause_stats = self.utterance_segmentator.get_pause_statistics(utterance_segments)
                
                if pause_stats:
                    st.info(f"🎯 Wykryto {pause_stats['total_pauses']} naturalnych pauz "
                           f"(średnia: {pause_stats['average_pause']:.2f}s, "
                           f"maksymalna: {pause_stats['max_pause']:.2f}s)")
                else:
                    st.info("🎯 Segmentacja na utterances zakończona")
                
                # Konwertuj utterances z powrotem do formatu transcript
                transcript['segments'] = self._convert_utterances_to_segments(utterance_segments)
                transcript['utterances'] = utterance_segments
                
                # Zapisz informacje o utterances
                st.session_state['utterance_segments'] = utterance_segments
                st.session_state['pause_statistics'] = pause_stats
            
            # Krok 6: Generowanie napisów (na poziomie słów lub tradycyjnie)
            if st.session_state.get('enable_word_level', True):
                progress_tracker.update_progress(0.8, "📝 Generowanie napisów na poziomie słów...")
                
                # Ustaw parametry wyświetlania
                self.word_level_sync.max_words_on_screen = st.session_state.get('max_words_on_screen', 8)
                
                # Konfiguruj renderer płynnych napisów
                smooth_config = SmoothSubtitleConfig(
                    min_display_duration=st.session_state.get('min_display_duration', 0.4),
                    max_words_per_line=st.session_state.get('max_words_on_screen', 8),
                    font_size=18 if st.session_state.get('subtitle_quality', 'high') == 'standard' else 20
                )
                self.smooth_renderer.config = smooth_config
                
                # NOWY: Zaawansowany post-processing jeśli włączony
                if st.session_state.get('enable_advanced_processing', True):
                    st.info("🚀 Stosowanie zaawansowanego post-processingu...")
                    
                    # Użyj zaawansowanego procesora słów
                    stabilized_blocks = self.advanced_word_processor.process_word_level_transcription(
                        transcript, audio_file_path if 'audio_file_path' in locals() else None
                    )
                    
                    if stabilized_blocks:
                        st.success(f"✅ Utworzono {len(stabilized_blocks)} stabilizowanych bloków (38 słów każdy)")
                        
                        # Konwertuj stabilizowane bloki do formatu word_segments dla kompatybilności
                        word_segments = self._convert_stabilized_blocks_to_segments(stabilized_blocks)
                        
                        # Wyświetl informacje o post-processingu
                        with st.expander("📊 Szczegóły zaawansowanego post-processingu"):
                            st.write(f"**Liczba bloków:** {len(stabilized_blocks)}")
                            st.write(f"**Średnia liczba słów na blok:** {sum(len(block.words) for block in stabilized_blocks) / len(stabilized_blocks):.1f}")
                            st.write(f"**Nakładanie między blokami:** {self.advanced_word_processor.block_overlap*1000:.0f}ms")
                            st.write(f"**Minimalna przerwa między słowami:** {self.advanced_word_processor.min_word_gap*1000:.0f}ms")
                            st.write(f"**Minimalna długość wyświetlania słowa:** {self.advanced_word_processor.min_word_duration*1000:.0f}ms")
                    else:
                        st.warning("⚠️ Zaawansowany post-processing nieudany, używam standardowego przetwarzania")
                        # Fallback do standardowego przetwarzania
                        word_segments = self.word_level_sync.create_word_level_subtitles(
                            transcript, translated_text
                        )
                else:
                    # Standardowe przetwarzanie word-level
                    word_segments = self.word_level_sync.create_word_level_subtitles(
                        transcript, translated_text
                    )
                
                # Konwertuj do formatu kompatybilnego z smooth renderer
                smooth_segments = self._convert_to_smooth_format(word_segments)
                
                # Wybierz tryb wyświetlania
                display_mode = st.session_state.get('word_display_mode', 'smooth_progressive')
                quality = st.session_state.get('subtitle_quality', 'high')
                
                if display_mode in ['smooth_progressive', 'stable_blocks', 'fade_transitions']:
                    # Sprawdź jakość word-level timestamps
                    word_count = sum(len(seg.get('words', [])) for seg in smooth_segments)
                    estimated_count = sum(
                        sum(1 for w in seg.get('words', []) if w.get('estimated', False)) 
                        for seg in smooth_segments
                    )
                    
                    if word_count > 0:
                        word_level_quality = 1.0 - (estimated_count / word_count)
                        
                        if word_level_quality > 0.8:
                            quality_msg = f"🎯 Używam precyzyjnych word-level timestamps z AssemblyAI ({word_level_quality:.1%} jakości)"
                        else:
                            quality_msg = f"⚠️ Mieszane timestampy: {word_count-estimated_count} precyzyjnych, {estimated_count} oszacowanych"
                    else:
                        quality_msg = "📝 Używam oszacowanych timestampów z segmentów"
                    
                    if st.session_state.get('enable_anti_flicker', True):
                        if quality == 'premium':
                            subtitle_content = self.smooth_renderer.generate_high_quality_ass(smooth_segments)
                            st.success(f"✨ Napisy Premium ASS z word-level precision + eliminacja migotania")
                            st.info(quality_msg)
                        else:
                            subtitle_content = self.smooth_renderer.generate_smooth_srt(smooth_segments, display_mode)
                            st.success(f"✨ Płynne napisy bez migotania - tryb: {display_mode}")
                            st.info(quality_msg)
                    else:
                        subtitle_content = self.smooth_renderer.generate_smooth_srt(smooth_segments, display_mode)
                        st.info(f"🎯 Tryb: {display_mode}")
                        st.info(quality_msg)
                elif display_mode == 'youtube_style':
                    subtitle_content = self.word_level_sync.generate_progressive_srt(word_segments)
                    max_words = st.session_state.get('max_words_on_screen', 8)
                    st.info(f"🎯 Używam stylu YouTube - słowa dochodzą do wypowiedzi (max {max_words} słów na ekranie)")
                else:
                    subtitle_content = self.word_level_sync.generate_word_level_srt(word_segments)
                    st.info("🎯 Używam indywidualnego wyświetlania - tylko jedno słowo na raz")
                
                # Zapisz informacje o segmentach słów dla dalszego przetwarzania
                st.session_state['word_segments'] = word_segments
                
            else:
                progress_tracker.update_progress(0.8, "📝 Generowanie tradycyjnych napisów...")
                subtitle_content = self.subtitle_generator.generate_subtitles(
                    transcript['segments'],
                    translated_text,
                    format=st.session_state.get('subtitle_format', 'SRT'),
                    max_chars_per_line=st.session_state.get('max_chars_per_line', 42)
                )
            
            # Krok 7: Tworzenie wideo z napisami
            progress_tracker.update_progress(0.9, "🎬 Tworzenie wideo z napisami...")
            output_video_path = self.video_processor.add_subtitles_to_video(
                video_path,
                subtitle_content,
                st.session_state.get('subtitle_format', 'SRT')
            )
            
            # Krok 8: Zakończenie
            progress_tracker.update_progress(1.0, "✅ Przetwarzanie zakończone!")
            
            # Wyświetl rezultaty
            self._display_results(output_video_path, subtitle_content, original_filename)
            
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania: {str(e)}")
            st.error(f"❌ Wystąpił błąd: {str(e)}")
        
        finally:
            # Wyczyść pliki tymczasowe
            self._cleanup_temp_files([video_path, audio_path if 'audio_path' in locals() else None])
    
    def _execute_with_retry_sync(self, operation: Callable, operation_name: str, *args, **kwargs) -> Tuple[Any, int]:
        """
        Synchroniczna wersja execute_with_retry dla kompatybilności ze Streamlit
        
        Args:
            operation: Funkcja do wykonania
            operation_name: Nazwa operacji
            *args, **kwargs: Argumenty dla operacji
            
        Returns:
            Tuple (result, retry_count)
        """
        retry_count = 0
        last_exception = None
        
        for attempt in range(self.retry_manager.config.max_retries + 1):
            try:
                start_time = time.time()
                result = operation(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Sprawdź jakość wyniku
                if self.retry_manager._validate_result_quality(result, operation_name):
                    logger.info(f"{operation_name} zakończona pomyślnie po {attempt + 1} próbach")
                    self.retry_manager._record_successful_attempt(operation_name, execution_time, retry_count)
                    return result, retry_count
                else:
                    raise Exception(f"Wynik operacji {operation_name} nie spełnia kryteriów jakości")
                    
            except Exception as e:
                last_exception = e
                retry_count += 1
                
                logger.warning(f"{operation_name} - próba {attempt + 1} nieudana: {str(e)}")
                
                if attempt < self.retry_manager.config.max_retries:
                    delay = self.retry_manager._calculate_retry_delay(attempt)
                    logger.info(f"Ponowna próba za {delay:.1f} sekund...")
                    
                    self.retry_manager._record_failed_attempt(operation_name, str(e), attempt + 1)
                    time.sleep(delay)
                else:
                    logger.error(f"{operation_name} - wszystkie próby wyczerpane")
        
        # Wszystkie próby nieudane
        self.retry_manager._record_final_failure(operation_name, str(last_exception), retry_count)
        raise Exception(f"Operacja {operation_name} nieudana po {retry_count} próbach: {last_exception}")
    
    def _reprocess_segments_sync(self, segments: List[Dict], confidence_threshold: float = 0.6) -> List[Dict]:
        """
        Synchroniczne ponowne przetwarzanie segmentów o niskiej pewności
        
        Args:
            segments: Lista segmentów
            confidence_threshold: Próg pewności
            
        Returns:
            Lista przetworzonych segmentów
        """
        reprocessed_segments = []
        
        for i, segment in enumerate(segments):
            confidence = segment.get('confidence', 1.0)
            
            if confidence < confidence_threshold:
                logger.info(f"Ponowne przetwarzanie segmentu {i} (pewność: {confidence:.2f})")
                
                try:
                    # Ponowne tłumaczenie
                    original_text = segment.get('original_text', segment.get('text', ''))
                    if original_text:
                        retranslated, _ = self._execute_with_retry_sync(
                            self.translation_service.translate_text,
                            "segment_retranslation",
                            original_text,
                            target_language=segment.get('target_language', 'PL')
                        )
                        
                        segment['text'] = retranslated
                        segment['reprocessed'] = True
                        segment['original_confidence'] = confidence
                        segment['confidence'] = min(confidence + 0.2, 1.0)  # Zwiększ pewność
                
                except Exception as e:
                    logger.error(f"Błąd podczas ponownego przetwarzania segmentu {i}: {e}")
                    segment['reprocessing_failed'] = True
            
            reprocessed_segments.append(segment)
        
        return reprocessed_segments
    
    def _convert_to_smooth_format(self, word_segments):
        """
        Konwertuj segmenty słów do formatu kompatybilnego z smooth renderer
        
        Args:
            word_segments: Segmenty z WordLevelSynchronizer
            
        Returns:
            Segmenty w formacie dla SmoothSubtitleRenderer
        """
        smooth_segments = []
        
        for segment in word_segments:
            if hasattr(segment, 'words'):
                # WordLevelSegment object
                words_list = []
                for word in segment.words:
                    word_dict = {
                        'word': word.word,
                        'start': word.start,
                        'end': word.end,
                        'confidence': word.confidence,
                        'speaker': word.speaker
                    }
                    words_list.append(word_dict)
                
                smooth_segment = {
                    'words': words_list,
                    'sentence_id': segment.sentence_id,
                    'complete_text': segment.complete_text
                }
                smooth_segments.append(smooth_segment)
            else:
                # Already in dict format
                smooth_segments.append(segment)
        
        return smooth_segments
    
    def _convert_utterances_to_segments(self, utterances):
        """
        Konwertuj utterances z powrotem do formatu segmentów
        
        Args:
            utterances: Lista UtteranceSegment
            
        Returns:
            Lista segmentów w standardowym formacie
        """
        segments = []
        
        for utterance in utterances:
            segment = {
                'text': utterance.text,
                'start': utterance.start,
                'end': utterance.end,
                'confidence': utterance.confidence,
                'speaker': utterance.speaker,
                'words': utterance.words,
                'pause_before': utterance.pause_before,
                'pause_after': utterance.pause_after,
                'is_natural_break': utterance.is_natural_break,
                'segment_id': utterance.segment_id
            }
            segments.append(segment)
        
        return segments
    
    def _auto_fix_timestamp_issues(self, transcript: Dict, issues: List) -> Dict:
        """
        Automatycznie napraw podstawowe problemy z timestampami
        
        Args:
            transcript: Dane transkrypcji
            issues: Lista problemów
            
        Returns:
            Naprawione dane transkrypcji
        """
        fixed_transcript = transcript.copy()
        segments = fixed_transcript.get('segments', [])
        
        if not segments:
            return fixed_transcript
        
        logger.info("🔧 Automatyczne naprawy timestampów...")
        
        # 1. Napraw nakładające się segmenty
        for i in range(len(segments) - 1):
            current_segment = segments[i]
            next_segment = segments[i + 1]
            
            current_end = current_segment.get('end', 0)
            next_start = next_segment.get('start', 0)
            
            if current_end > next_start:
                # Napraw nakładanie
                gap = 0.1  # 100ms przerwy
                middle_point = (current_end + next_start) / 2
                
                segments[i]['end'] = middle_point - gap/2
                segments[i + 1]['start'] = middle_point + gap/2
                
                logger.debug(f"Naprawiono nakładanie segmentów {i}-{i+1}")
        
        # 2. Napraw bardzo krótkie segmenty
        for i, segment in enumerate(segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            duration = end - start
            
            if duration < 0.1:
                # Wydłuż segment do minimum 300ms
                min_duration = 0.3
                segments[i]['end'] = start + min_duration
                
                # Sprawdź czy nie koliduje z następnym
                if i < len(segments) - 1:
                    next_start = segments[i + 1].get('start', 0)
                    if segments[i]['end'] > next_start:
                        segments[i]['end'] = next_start - 0.05
                
                logger.debug(f"Wydłużono krótki segment {i}")
        
        # 3. Napraw nieprawidłowe zakresy (end <= start)
        for i, segment in enumerate(segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            if end <= start:
                # Ustaw minimalną długość
                segments[i]['end'] = start + 0.5
                logger.debug(f"Naprawiono nieprawidłowy zakres segmentu {i}")
        
        # 4. Napraw word-level timestamps jeśli dostępne
        words = fixed_transcript.get('words', [])
        if words:
            fixed_words = self._fix_word_timestamps(words)
            fixed_transcript['words'] = fixed_words
        
        # 5. Dodaj offset jeśli wszystkie timestampy zaczynają się za wcześnie
        first_segment_start = segments[0].get('start', 0) if segments else 0
        if first_segment_start < 0.1:  # Zaczyna się bardzo wcześnie
            offset = 0.3  # Dodaj 300ms offset
            
            for segment in segments:
                segment['start'] = segment.get('start', 0) + offset
                segment['end'] = segment.get('end', 0) + offset
            
            for word in words:
                word['start'] = word.get('start', 0) + offset
                word['end'] = word.get('end', 0) + offset
            
            logger.info(f"Dodano offset {offset}s do wszystkich timestampów")
        
        fixed_transcript['segments'] = segments
        logger.info("✅ Automatyczne naprawy timestampów zakończone")
        
        return fixed_transcript
    
    def _fix_word_timestamps(self, words: List[Dict]) -> List[Dict]:
        """
        Napraw word-level timestamps
        
        Args:
            words: Lista słów
            
        Returns:
            Naprawione słowa
        """
        if not words:
            return words
        
        fixed_words = []
        
        for i, word in enumerate(words):
            fixed_word = word.copy()
            
            start = word.get('start', 0)
            end = word.get('end', 0)
            duration = end - start
            
            # Napraw bardzo krótkie słowa
            if duration < 0.05:  # < 50ms
                min_duration = max(0.08, len(word.get('text', '')) * 0.06)  # ~60ms na znak
                fixed_word['end'] = start + min_duration
            
            # Napraw bardzo długie słowa
            elif duration > 2.0:  # > 2s
                max_duration = min(2.0, len(word.get('text', '')) * 0.15)  # ~150ms na znak
                fixed_word['end'] = start + max_duration
            
            # Napraw nakładanie z następnym słowem
            if i < len(words) - 1:
                next_start = words[i + 1].get('start', 0)
                if fixed_word['end'] > next_start:
                    gap = 0.02  # 20ms przerwy
                    fixed_word['end'] = next_start - gap
                    
                    # Upewnij się że słowo ma minimalną długość
                    if fixed_word['end'] - fixed_word['start'] < 0.05:
                        fixed_word['end'] = fixed_word['start'] + 0.05
            
            fixed_words.append(fixed_word)
        
        return fixed_words
    
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
    
    def _display_results_with_quality_report(self, 
                                           output_video_path: str, 
                                           subtitle_content: str, 
                                           original_filename: str,
                                           quality_report=None,
                                           transcript=None,
                                           translated_segments=None):
        """Wyświetl rezultaty przetwarzania z raportem jakości"""
        st.success("🎉 Przetwarzanie zakończone pomyślnie!")
        
        # Główne rezultaty
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
        
        # Raport jakości
        if quality_report:
            st.subheader("📊 Raport jakości")
            self._display_quality_metrics(quality_report)
        
        # Informacje o mówiących
        if transcript and transcript.get('segments'):
            st.subheader("👥 Analiza mówiących")
            self._display_speaker_analysis(transcript)
        
        # Statystyki przetwarzania
        st.subheader("📈 Statystyki przetwarzania")
        self._display_processing_statistics()
        
        # Informacje o napisach na poziomie słów
        if 'word_segments' in st.session_state:
            st.subheader("🔤 Analiza napisów na poziomie słów")
            self._display_word_level_analysis()
        
        # Informacje o segmentacji utterances
        if 'utterance_segments' in st.session_state:
            st.subheader("🗣️ Analiza segmentacji utterances")
            self._display_utterance_analysis()
    
    def _display_quality_metrics(self, quality_report):
        """Wyświetl metryki jakości"""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Ogólna jakość",
                quality_report.overall_quality.value.title(),
                delta=None
            )
            
            confidence = quality_report.confidence_metrics.overall_confidence
            st.metric(
                "Pewność ogólna",
                f"{confidence:.1%}",
                delta=f"{(confidence - 0.7):.1%}" if confidence != 0.7 else None
            )
        
        with col2:
            st.metric(
                "Pewność transkrypcji",
                f"{quality_report.confidence_metrics.transcription_confidence:.1%}"
            )
            
            st.metric(
                "Pewność tłumaczenia",
                f"{quality_report.confidence_metrics.translation_confidence:.1%}"
            )
        
        with col3:
            st.metric(
                "Czas przetwarzania",
                f"{quality_report.processing_time:.1f}s"
            )
            
            st.metric(
                "Liczba ponownych prób",
                quality_report.retry_count
            )
        
        # Problemy i rekomendacje
        if quality_report.timing_issues or quality_report.translation_issues:
            st.subheader("⚠️ Wykryte problemy")
            
            if quality_report.timing_issues:
                st.warning("**Problemy z timingiem:**")
                for issue in quality_report.timing_issues:
                    st.write(f"• {issue}")
            
            if quality_report.translation_issues:
                st.warning("**Problemy z tłumaczeniem:**")
                for issue in quality_report.translation_issues:
                    st.write(f"• {issue}")
        
        if quality_report.recommendations:
            st.subheader("💡 Rekomendacje")
            for rec in quality_report.recommendations:
                st.info(f"• {rec}")
    
    def _display_speaker_analysis(self, transcript):
        """Wyświetl analizę mówiących"""
        speaker_analysis = self.quality_controller.analyze_speakers(transcript)
        
        if len(speaker_analysis) > 1:
            st.write(f"**Wykryto {len(speaker_analysis)} mówiących:**")
            
            for speaker in speaker_analysis:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**{speaker.speaker_id}**")
                
                with col2:
                    st.write(f"Segmentów: {speaker.segments_count}")
                
                with col3:
                    st.write(f"Czas: {speaker.total_duration:.1f}s")
                    st.write(f"Pewność: {speaker.confidence:.1%}")
        else:
            st.write("**Wykryto jednego mówiącego**")
    
    def _display_processing_statistics(self):
        """Wyświetl statystyki przetwarzania"""
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎤 Transkrypcja")
            if hasattr(self.transcription_service, 'processing_times') and self.transcription_service.processing_times:
                avg_time = sum(self.transcription_service.processing_times) / len(self.transcription_service.processing_times)
                st.metric("Średni czas", f"{avg_time:.1f}s")
                
                if self.transcription_service.confidence_scores:
                    avg_confidence = sum(self.transcription_service.confidence_scores) / len(self.transcription_service.confidence_scores)
                    st.metric("Średnia pewność", f"{avg_confidence:.1%}")
        
        with col2:
            st.subheader("🌍 Tłumaczenie")
            if hasattr(self.translation_service, 'translation_times') and self.translation_service.translation_times:
                stats = self.translation_service.get_translation_statistics()
                if stats:
                    st.metric("Średni czas", f"{stats['average_time']:.1f}s")
                    st.metric("Średnia jakość", f"{stats['average_quality']:.1%}")
        
        # Statystyki ponownych prób
        retry_stats = self.retry_manager.get_retry_statistics()
        if retry_stats:
            st.subheader("🔄 Ponowne próby")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Sukces", f"{retry_stats['success_rate']:.1f}%")
            
            with col2:
                st.metric("Średnie próby", f"{retry_stats['average_retry_count']:.1f}")
            
            with col3:
                st.metric("Operacje", retry_stats['total_operations'])
    
    def _display_error_statistics(self):
        """Wyświetl statystyki błędów"""
        st.subheader("📊 Statystyki sesji")
        
        retry_stats = self.retry_manager.get_retry_statistics()
        if retry_stats:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Udane operacje", retry_stats['successful_operations'])
                st.metric("Nieudane operacje", retry_stats['failed_operations'])
            
            with col2:
                st.metric("Wskaźnik sukcesu", f"{retry_stats['success_rate']:.1f}%")
                st.metric("Średni czas", f"{retry_stats['average_execution_time']:.1f}s")
    
    def _convert_stabilized_blocks_to_segments(self, stabilized_blocks):
        """
        Konwertuj stabilizowane bloki do formatu word_segments dla kompatybilności
        """
        from .services.word_level_sync import WordLevelSegment
        
        word_segments = []
        for block in stabilized_blocks:
            segment = WordLevelSegment(
                sentence_id=block.block_id,
                words=block.words,
                sentence_start=block.start_time,
                sentence_end=block.end_time,
                complete_text=' '.join([w.word for w in block.words])
            )
            word_segments.append(segment)
        
        return word_segments
    
    def _display_word_level_analysis(self):
        """Wyświetl analizę napisów na poziomie słów"""
        word_segments = st.session_state.get('word_segments', [])
        
        if not word_segments:
            return
        
        # Oblicz statystyki
        total_words = sum(len(segment.words) for segment in word_segments)
        total_sentences = len(word_segments)
        
        # Średnia długość słowa
        word_durations = []
        for segment in word_segments:
            for word in segment.words:
                duration = word.end - word.start
                word_durations.append(duration)
        
        avg_word_duration = np.mean(word_durations) if word_durations else 0
        
        # Średnia pewność słów
        word_confidences = []
        for segment in word_segments:
            for word in segment.words:
                word_confidences.append(word.confidence)
        
        avg_word_confidence = np.mean(word_confidences) if word_confidences else 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Całkowita liczba słów", total_words)
            st.metric("Liczba zdań", total_sentences)
        
        with col2:
            st.metric("Średnia długość słowa", f"{avg_word_duration:.2f}s")
            st.metric("Słów na zdanie", f"{total_words/total_sentences:.1f}" if total_sentences > 0 else "0")
        
        with col3:
            st.metric("Średnia pewność słów", f"{avg_word_confidence:.1%}")
            
            # Tryb wyświetlania
            display_mode = st.session_state.get('word_display_mode', 'progressive')
            mode_text = "Progresywny" if display_mode == 'progressive' else "Indywidualny"
            st.metric("Tryb wyświetlania", mode_text)
        
        # Szczegółowa analiza pierwszych kilku zdań
        st.subheader("🔍 Podgląd pierwszych zdań")
        
        for i, segment in enumerate(word_segments[:3]):  # Pokaż pierwsze 3 zdania
            with st.expander(f"Zdanie {i+1}: '{segment.complete_text}'"):
                st.write(f"**Czas trwania:** {segment.sentence_end - segment.sentence_start:.2f}s")
                st.write(f"**Liczba słów:** {len(segment.words)}")
                
                # Tabela słów
                word_data = []
                for j, word in enumerate(segment.words):
                    word_data.append({
                        "Nr": j+1,
                        "Słowo": word.word,
                        "Start": f"{word.start:.2f}s",
                        "Koniec": f"{word.end:.2f}s",
                        "Długość": f"{word.end - word.start:.2f}s",
                        "Pewność": f"{word.confidence:.1%}"
                    })
                
                st.table(word_data)
        
        # Informacje o korzyściach
        st.info("""
        **Korzyści z napisów na poziomie słów:**
        
        🎯 **Lepsza synchronizacja** - każde słowo ma precyzyjny timing
        
        📺 **Naturalne czytanie** - słowa pojawiają się jak w naturalnej mowie
        
        🎬 **Profesjonalny wygląd** - jak w filmach i programach TV
        
        ♿ **Dostępność** - łatwiejsze dla osób z problemami słuchu
        
        🧠 **Lepsze zrozumienie** - mózg łatwiej przetwarza stopniowo pojawiające się słowa
        """)
        
        # Porównanie z tradycyjnymi napisami
        st.subheader("📊 Porównanie z tradycyjnymi napisami")
        
        comparison_data = {
            "Aspekt": [
                "Synchronizacja",
                "Naturalność",
                "Czytelność",
                "Precyzja timingu",
                "Doświadczenie użytkownika"
            ],
            "Tradycyjne napisy": [
                "Segmenty (2-5s)",
                "Sztuczne bloki tekstu",
                "Dobra",
                "Przybliżona",
                "Standardowa"
            ],
            "Napisy na poziomie słów": [
                "Każde słowo osobno",
                "Jak naturalna mowa",
                "Doskonała",
                "Precyzyjna",
                "Premium"
            ]
        }
        
        st.table(comparison_data)
    
    def _display_utterance_analysis(self):
        """Wyświetl analizę segmentacji utterances"""
        utterance_segments = st.session_state.get('utterance_segments', [])
        pause_stats = st.session_state.get('pause_statistics', {})
        
        if not utterance_segments:
            return
        
        # Podstawowe statystyki
        total_utterances = len(utterance_segments)
        natural_breaks = sum(1 for u in utterance_segments if u.is_natural_break)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Liczba utterances", total_utterances)
            st.metric("Naturalne przerwy", f"{natural_breaks}/{total_utterances}")
        
        with col2:
            if pause_stats:
                st.metric("Średnia pauza", f"{pause_stats.get('average_pause', 0):.2f}s")
                st.metric("Maksymalna pauza", f"{pause_stats.get('max_pause', 0):.2f}s")
        
        with col3:
            if pause_stats:
                st.metric("Całkowity czas pauz", f"{pause_stats.get('total_pause_time', 0):.1f}s")
                st.metric("Pauzy > 1s", pause_stats.get('pauses_over_1s', 0))
        
        # Szczegółowa analiza pierwszych utterances
        st.subheader("🔍 Podgląd pierwszych utterances")
        
        for i, utterance in enumerate(utterance_segments[:3]):
            with st.expander(f"Utterance {i+1}: '{utterance.text[:50]}...'"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Czas:** {utterance.start:.2f}s - {utterance.end:.2f}s")
                    st.write(f"**Długość:** {utterance.end - utterance.start:.2f}s")
                    st.write(f"**Mówiący:** {utterance.speaker}")
                    st.write(f"**Pewność:** {utterance.confidence:.1%}")
                
                with col2:
                    st.write(f"**Pauza przed:** {utterance.pause_before:.2f}s")
                    st.write(f"**Pauza po:** {utterance.pause_after:.2f}s")
                    st.write(f"**Naturalna przerwa:** {'✅' if utterance.is_natural_break else '❌'}")
                    st.write(f"**Liczba słów:** {len(utterance.words)}")
                
                st.write(f"**Pełny tekst:** {utterance.text}")
        
        # Informacje o korzyściach
        st.info("""
        **Korzyści z segmentacji utterances:**
        
        🎯 **Naturalne przerwy** - podział tam gdzie rzeczywiście są pauzy w mowie
        
        📊 **Automatyczne wykrywanie** - AssemblyAI automatycznie znajduje ciszę
        
        🗣️ **Lepsze grupowanie** - wypowiedzi grupowane logicznie
        
        ⏱️ **Precyzyjne pauzy** - dokładne informacje o długości przerw
        
        🎬 **Profesjonalne napisy** - jak w filmach i programach TV
        """)
        
        # Wykres rozkładu długości utterances
        if len(utterance_segments) > 1:
            st.subheader("📊 Rozkład długości utterances")
            
            durations = [u.end - u.start for u in utterance_segments]
            
            import matplotlib.pyplot as plt
            import numpy as np
            
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.hist(durations, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax.set_xlabel('Długość utterance (sekundy)')
            ax.set_ylabel('Liczba utterances')
            ax.set_title('Rozkład długości utterances')
            ax.grid(True, alpha=0.3)
            
            st.pyplot(fig)
            plt.close()
    
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