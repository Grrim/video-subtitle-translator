"""
Serwis transkrypcji audio wykorzystujący AssemblyAI
Obsługuje rozpoznawanie mowy z plików audio
"""

import assemblyai as aai
import os
import time
from typing import Dict, Any, List, Optional
import requests

from ..utils.logger import get_logger
from ..utils.assemblyai_features_summary import AssemblyAIFeaturesSummary

logger = get_logger(__name__)

class TranscriptionService:
    """Serwis do transkrypcji audio używając AssemblyAI"""
    
    def __init__(self, api_key: str):
        """
        Inicjalizuj serwis transkrypcji
        
        Args:
            api_key: Klucz API AssemblyAI
        """
        if not api_key:
            raise ValueError("Klucz API AssemblyAI jest wymagany")
        
        self.api_key = api_key
        # Ustaw klucz API w zmiennej środowiskowej
        os.environ['ASSEMBLYAI_API_KEY'] = api_key
        aai.settings.api_key = api_key
        
        # Inicjalizuj metryki jakości
        self.processing_times = []
        self.confidence_scores = []
        
        # Wyświetl podsumowanie włączonych funkcji
        logger.info("🚀 Inicjalizacja TranscriptionService z najwyższą jakością AssemblyAI")
        AssemblyAIFeaturesSummary.print_features_summary()
        
    def transcribe_audio(self, audio_path: str, quality: str = 'premium', language: str = 'auto', enable_speaker_detection: bool = True) -> Dict[str, Any]:
        """
        Transkrybuj plik audio
        
        Args:
            audio_path: Ścieżka do pliku audio
            quality: Jakość transkrypcji ('standard' lub 'premium')
            language: Kod języka lub 'auto' dla automatycznego wykrywania
            
        Returns:
            Słownik z wynikami transkrypcji
        """
        try:
            start_time = time.time()
            logger.info(f"Rozpoczynam transkrypcję pliku: {audio_path}")
            
            # Konfiguracja transkrypcji - NAJWYŻSZA JAKOŚĆ z wszystkimi funkcjami
            config = aai.TranscriptionConfig(
                # === PODSTAWOWE USTAWIENIA WYSOKIEJ JAKOŚCI ===
                language_code=language if language != 'auto' else None,
                language_detection=language == 'auto',  # Automatyczne wykrywanie języka
                punctuate=True,                         # Interpunkcja i formatowanie tekstu
                format_text=True,                       # Formatowanie tekstu (wielkie litery, etc.)
                
                # === SPEAKER LABELS (Wykrywanie mówiących) ===
                speaker_labels=enable_speaker_detection,  # Etykiety mówiących
                speakers_expected=None,                    # Automatyczne wykrywanie liczby mówiących
                
                # === WORD-LEVEL TIMESTAMPS (Maksymalna precyzja) ===
                # Word-level timestamps są automatycznie włączone w AssemblyAI
                dual_channel=False,                       # Dla lepszej precyzji timestampów
                
                # === BOOST DLA NAJWYŻSZEJ JAKOŚCI ===
                word_boost=[],                           # Lista słów do wzmocnienia (można dodać specjalne terminy)
                boost_param='high',                      # Wysoki poziom wzmocnienia jakości
                
                # === DODATKOWE FUNKCJE AI (Premium) ===
                auto_highlights=True,                    # Automatyczne wyróżnienia kluczowych fragmentów
                auto_chapters=True,                      # Automatyczne rozdziały/segmentacja
                sentiment_analysis=True,                 # Analiza sentymentu wypowiedzi
                entity_detection=True,                   # Wykrywanie encji (nazwy, miejsca, organizacje)
                iab_categories=True,                     # Kategoryzacja treści IAB
                content_safety=True,                     # Wykrywanie niebezpiecznych treści
                
                # === USTAWIENIA PRYWATNOŚCI I FILTROWANIA ===
                filter_profanity=False,                 # Nie filtruj wulgaryzmów (dla dokładności)
                redact_pii=False,                        # Nie ukrywaj danych osobowych
                redact_pii_audio=False,                  # Nie ukrywaj w audio
                redact_pii_policies=None,                # Brak polityk ukrywania
                redact_pii_sub='***',                    # Zastępowanie (jeśli włączone)
                
                # === USTAWIENIA AUDIO ===
                audio_start_from=None,                   # Start od początku
                audio_end_at=None,                       # Do końca pliku
                
                # === WEBHOOK (opcjonalne) ===
                webhook_url=None,
                webhook_auth_header_name=None,
                webhook_auth_header_value=None,
                
                # === DODATKOWE USTAWIENIA JAKOŚCI ===
                speech_threshold=None,                   # Automatyczny próg wykrywania mowy
                disfluencies=False,                      # Nie uwzględniaj zacinania się
                # multichannel nie istnieje - używamy dual_channel powyżej
            )
            
            # Utwórz transkryptor
            transcriber = aai.Transcriber(config=config)
            
            # Rozpocznij transkrypcję
            transcript = transcriber.transcribe(audio_path)
            
            # Sprawdź status
            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Błąd transkrypcji: {transcript.error}")
            
            # Oblicz czas przetwarzania
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Przygotuj wynik z rozszerzonymi metrykami
            confidence = getattr(transcript, 'confidence', 0.0)
            self.confidence_scores.append(confidence)
            
            result = {
                'id': getattr(transcript, 'id', 'unknown'),
                'text': transcript.text or '',
                'confidence': confidence,
                'language_code': getattr(transcript, 'language_code', 'unknown'),
                'audio_duration': getattr(transcript, 'audio_duration', 0),
                'segments': self._extract_segments(transcript, enable_speaker_detection),
                'words': self._extract_words_with_precision(transcript),
                'status': getattr(transcript.status, 'value', 'completed') if hasattr(transcript, 'status') else 'completed',
                'processing_time': processing_time,
                'quality_metrics': {
                    'confidence_score': confidence,
                    'processing_time': processing_time,
                    'word_count': len(transcript.text.split()) if transcript.text else 0,
                    'segment_count': len(self._extract_segments(transcript, enable_speaker_detection)),
                    'language_detected': getattr(transcript, 'language_code', 'unknown'),
                    'audio_duration_seconds': getattr(transcript, 'audio_duration', 0) / 1000.0 if getattr(transcript, 'audio_duration', 0) else 0
                }
            }
            
            # === DODATKOWE INFORMACJE PREMIUM (Wszystkie funkcje AI) ===
            # Auto Highlights - kluczowe fragmenty
            if hasattr(transcript, 'auto_highlights') and transcript.auto_highlights:
                result['highlights'] = [
                    {
                        'text': highlight.text,
                        'count': highlight.count,
                        'rank': highlight.rank,
                        'timestamps': getattr(highlight, 'timestamps', [])
                    }
                    for highlight in transcript.auto_highlights.results
                ]
                logger.info(f"✨ Wykryto {len(result['highlights'])} kluczowych fragmentów")
            
            # Sentiment Analysis - analiza sentymentu
            if hasattr(transcript, 'sentiment_analysis') and transcript.sentiment_analysis:
                result['sentiment'] = [
                    {
                        'text': sentiment.text,
                        'sentiment': sentiment.sentiment.value,
                        'confidence': sentiment.confidence,
                        'start': sentiment.start / 1000.0,
                        'end': sentiment.end / 1000.0
                    }
                    for sentiment in transcript.sentiment_analysis
                ]
                logger.info(f"😊 Przeanalizowano sentyment dla {len(result['sentiment'])} fragmentów")
            
            # Entity Detection - wykrywanie encji
            if hasattr(transcript, 'entities') and transcript.entities:
                result['entities'] = [
                    {
                        'text': entity.text,
                        'entity_type': entity.entity_type.value,
                        'start': entity.start / 1000.0,
                        'end': entity.end / 1000.0
                    }
                    for entity in transcript.entities
                ]
                logger.info(f"🏷️ Wykryto {len(result['entities'])} encji (nazwy, miejsca, organizacje)")
            
            # Auto Chapters - automatyczne rozdziały
            if hasattr(transcript, 'chapters') and transcript.chapters:
                result['chapters'] = [
                    {
                        'summary': chapter.summary,
                        'headline': chapter.headline,
                        'gist': chapter.gist,
                        'start': chapter.start / 1000.0,
                        'end': chapter.end / 1000.0
                    }
                    for chapter in transcript.chapters
                ]
                logger.info(f"📚 Utworzono {len(result['chapters'])} automatycznych rozdziałów")
            
            # IAB Categories - kategoryzacja treści
            if hasattr(transcript, 'iab_categories') and transcript.iab_categories:
                result['categories'] = {
                    'summary': getattr(transcript.iab_categories, 'summary', {}),
                    'results': [
                        {
                            'text': cat.text,
                            'labels': [
                                {
                                    'relevance': label.relevance,
                                    'label': label.label
                                }
                                for label in cat.labels
                            ],
                            'timestamp': {
                                'start': cat.timestamp.start / 1000.0,
                                'end': cat.timestamp.end / 1000.0
                            }
                        }
                        for cat in transcript.iab_categories.results
                    ]
                }
                logger.info(f"📂 Skategoryzowano treść według standardu IAB")
            
            # Content Safety - bezpieczeństwo treści
            if hasattr(transcript, 'content_safety_labels') and transcript.content_safety_labels:
                result['content_safety'] = {
                    'summary': getattr(transcript.content_safety_labels, 'summary', {}),
                    'results': [
                        {
                            'text': safety.text,
                            'labels': [
                                {
                                    'confidence': label.confidence,
                                    'severity': label.severity,
                                    'label': label.label
                                }
                                for label in safety.labels
                            ],
                            'timestamp': {
                                'start': safety.timestamp.start / 1000.0,
                                'end': safety.timestamp.end / 1000.0
                            }
                        }
                        for safety in transcript.content_safety_labels.results
                    ]
                }
                logger.info(f"🛡️ Przeanalizowano bezpieczeństwo treści")
            
            # Waliduj czy wszystkie funkcje zostały zwrócone
            warnings = AssemblyAIFeaturesSummary.validate_api_features(result)
            
            logger.info(f"✅ Transkrypcja zakończona pomyślnie!")
            logger.info(f"📊 Statystyki: {len(result['text'])} znaków, {len(result.get('words', []))} słów, {len(result.get('segments', []))} segmentów")
            logger.info(f"🎯 Pewność: {result['confidence']:.1%}, Czas: {result['processing_time']:.1f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Błąd podczas transkrypcji: {e}")
            # Rzuć wyjątek zamiast zwracać błędny wynik
            # To pozwoli aplikacji obsłużyć błąd odpowiednio
            raise Exception(f"Transkrypcja nie powiodła się: {str(e)}")
    
    def _extract_segments(self, transcript, enable_speaker_detection: bool = True) -> List[Dict[str, Any]]:
        """
        Wyciągnij segmenty z transkrypcji
        
        Args:
            transcript: Obiekt transkrypcji AssemblyAI
            
        Returns:
            Lista segmentów z czasami
        """
        segments = []
        
        if hasattr(transcript, 'utterances') and transcript.utterances and enable_speaker_detection:
            # Jeśli mamy utterances (segmenty mówców)
            for i, utterance in enumerate(transcript.utterances):
                segments.append({
                    'text': utterance.text,
                    'start': utterance.start / 1000.0,  # Konwersja z ms na sekundy
                    'end': utterance.end / 1000.0,
                    'confidence': utterance.confidence,
                    'speaker': getattr(utterance, 'speaker', f'Speaker_{chr(65+i%26)}'),  # A, B, C, etc.
                    'speaker_confidence': getattr(utterance, 'confidence', 0.8),
                    'segment_id': i,
                    'word_count': len(utterance.text.split()) if utterance.text else 0
                })
        elif hasattr(transcript, 'words') and transcript.words:
            # Jeśli mamy tylko słowa, grupuj je w segmenty
            current_segment = []
            segment_start = None
            segment_end = None
            
            for word in transcript.words:
                if segment_start is None:
                    segment_start = word.start / 1000.0
                
                current_segment.append(word.text)
                segment_end = word.end / 1000.0
                
                # Utwórz nowy segment co ~3-4 sekundy lub po 6-8 słów dla lepszej czytelności
                if (segment_end - segment_start > 3.5) or (len(current_segment) >= 7):
                    segments.append({
                        'text': ' '.join(current_segment),
                        'start': segment_start,
                        'end': segment_end,
                        'confidence': word.confidence,
                        'speaker': 'A'
                    })
                    
                    current_segment = []
                    segment_start = None
            
            # Dodaj ostatni segment jeśli istnieje
            if current_segment:
                segments.append({
                    'text': ' '.join(current_segment),
                    'start': segment_start,
                    'end': segment_end,
                    'confidence': 0.9,  # Domyślna pewność
                    'speaker': 'A'
                })
        else:
            # Fallback - jeden segment z całym tekstem
            audio_duration = getattr(transcript, 'audio_duration', 0)
            segments.append({
                'text': transcript.text or '',
                'start': 0.0,
                'end': audio_duration / 1000.0 if audio_duration else 10.0,
                'confidence': getattr(transcript, 'confidence', 0.9),
                'speaker': 'A'
            })
        
        return segments
    
    def _extract_words_with_precision(self, transcript) -> List[Dict[str, Any]]:
        """
        Wyciągnij słowa z MAKSYMALNĄ PRECYZJĄ word-level timestamps
        
        Args:
            transcript: Obiekt transkrypcji AssemblyAI
            
        Returns:
            Lista słów z precyzyjnymi timestampami
        """
        words = []
        
        if hasattr(transcript, 'words') and transcript.words:
            logger.info(f"Wykryto {len(transcript.words)} słów z word-level timestamps")
            
            for i, word in enumerate(transcript.words):
                # Konwertuj z milisekund na sekundy z wysoką precyzją
                start_seconds = word.start / 1000.0
                end_seconds = word.end / 1000.0
                
                # Waliduj timestampy
                if end_seconds <= start_seconds:
                    # Napraw nieprawidłowe timestampy
                    end_seconds = start_seconds + 0.1  # Minimalna długość 100ms
                
                word_data = {
                    'text': word.text,
                    'start': round(start_seconds, 3),  # Precyzja do milisekund
                    'end': round(end_seconds, 3),
                    'confidence': getattr(word, 'confidence', 0.9),
                    'word_index': i,  # Indeks słowa
                    'duration': round(end_seconds - start_seconds, 3),
                    'speaker': getattr(word, 'speaker', 'A'),  # Mówiący (jeśli dostępne)
                    'is_punctuated': any(p in word.text for p in '.,!?;:'),  # Czy ma interpunkcję
                }
                
                words.append(word_data)
            
            # Sprawdź jakość word-level timestamps
            self._validate_word_timestamps(words)
            
        else:
            logger.warning("Brak word-level timestamps - używam fallback z segmentów")
            words = self._fallback_words_from_segments(transcript)
        
        return words
    
    def _validate_word_timestamps(self, words: List[Dict[str, Any]]):
        """
        Waliduj jakość word-level timestamps
        
        Args:
            words: Lista słów z timestampami
        """
        if not words:
            return
        
        issues = []
        
        # Sprawdź nakładanie się słów
        for i in range(len(words) - 1):
            current_end = words[i]['end']
            next_start = words[i + 1]['start']
            
            if current_end > next_start:
                issues.append(f"Nakładanie słów {i}-{i+1}")
        
        # Sprawdź bardzo krótkie słowa
        short_words = [w for w in words if w['duration'] < 0.05]  # < 50ms
        if short_words:
            issues.append(f"{len(short_words)} bardzo krótkich słów")
        
        # Sprawdź bardzo długie słowa
        long_words = [w for w in words if w['duration'] > 3.0]  # > 3s
        if long_words:
            issues.append(f"{len(long_words)} bardzo długich słów")
        
        if issues:
            logger.warning(f"Problemy z word-level timestamps: {', '.join(issues)}")
        else:
            logger.info("✅ Word-level timestamps są wysokiej jakości")
    
    def _fallback_words_from_segments(self, transcript) -> List[Dict[str, Any]]:
        """
        Fallback: stwórz słowa z segmentów gdy brak word-level timestamps
        
        Args:
            transcript: Obiekt transkrypcji
            
        Returns:
            Lista oszacowanych słów
        """
        words = []
        
        if hasattr(transcript, 'utterances') and transcript.utterances:
            segments = transcript.utterances
        else:
            # Użyj podstawowych segmentów
            segments = getattr(transcript, 'segments', [])
        
        word_index = 0
        
        for segment in segments:
            segment_text = getattr(segment, 'text', '')
            segment_start = getattr(segment, 'start', 0) / 1000.0
            segment_end = getattr(segment, 'end', 0) / 1000.0
            segment_confidence = getattr(segment, 'confidence', 0.8)
            
            # Podziel segment na słowa
            segment_words = segment_text.split()
            
            if not segment_words:
                continue
            
            # Rozłóż czas równomiernie między słowa
            segment_duration = segment_end - segment_start
            time_per_word = segment_duration / len(segment_words)
            
            for i, word_text in enumerate(segment_words):
                word_start = segment_start + (i * time_per_word)
                word_end = word_start + time_per_word
                
                word_data = {
                    'text': word_text,
                    'start': round(word_start, 3),
                    'end': round(word_end, 3),
                    'confidence': segment_confidence,
                    'word_index': word_index,
                    'duration': round(time_per_word, 3),
                    'speaker': getattr(segment, 'speaker', 'A'),
                    'is_punctuated': any(p in word_text for p in '.,!?;:'),
                    'estimated': True  # Oznacz jako oszacowane
                }
                
                words.append(word_data)
                word_index += 1
        
        logger.info(f"Utworzono {len(words)} oszacowanych słów z segmentów")
        return words
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Pobierz listę obsługiwanych języków
        
        Returns:
            Słownik z kodami i nazwami języków
        """
        return {
            'auto': 'Automatyczne wykrywanie',
            'en': 'Angielski',
            'es': 'Hiszpański',
            'fr': 'Francuski',
            'de': 'Niemiecki',
            'it': 'Włoski',
            'pt': 'Portugalski',
            'nl': 'Holenderski',
            'hi': 'Hindi',
            'ja': 'Japoński',
            'zh': 'Chiński',
            'ko': 'Koreański',
            'ru': 'Rosyjski',
            'ar': 'Arabski',
            'tr': 'Turecki',
            'pl': 'Polski',
            'uk': 'Ukraiński',
            'vi': 'Wietnamski',
            'th': 'Tajski'
        }
    
    def check_api_status(self) -> bool:
        """
        Sprawdź status API AssemblyAI
        
        Returns:
            True jeśli API jest dostępne, False w przeciwnym razie
        """
        try:
            # Sprawdź dostępność API przez prosty request
            headers = {'authorization': self.api_key}
            response = requests.get('https://api.assemblyai.com/v2/transcript', headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania statusu API: {e}")
            return False