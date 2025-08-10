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
        
    def transcribe_audio(self, audio_path: str, quality: str = 'standard', language: str = 'auto') -> Dict[str, Any]:
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
            logger.info(f"Rozpoczynam transkrypcję pliku: {audio_path}")
            
            # Konfiguracja transkrypcji
            config = aai.TranscriptionConfig(
                language_code=language if language != 'auto' else None,
                language_detection=language == 'auto',
                punctuate=True,
                format_text=True,
                speaker_labels=False,  # Można włączyć dla rozpoznawania mówców
                auto_highlights=quality == 'premium',
                sentiment_analysis=quality == 'premium',
                entity_detection=quality == 'premium',
                word_boost=[],  # Można dodać słowa do wzmocnienia
                boost_param='default'
            )
            
            # Utwórz transkryptor
            transcriber = aai.Transcriber(config=config)
            
            # Rozpocznij transkrypcję
            transcript = transcriber.transcribe(audio_path)
            
            # Sprawdź status
            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Błąd transkrypcji: {transcript.error}")
            
            # Przygotuj wynik
            result = {
                'id': getattr(transcript, 'id', 'unknown'),
                'text': transcript.text or '',
                'confidence': getattr(transcript, 'confidence', 0.0),
                'language_code': getattr(transcript, 'language_code', 'unknown'),
                'audio_duration': getattr(transcript, 'audio_duration', 0),
                'segments': self._extract_segments(transcript),
                'words': self._extract_words(transcript) if hasattr(transcript, 'words') else [],
                'status': getattr(transcript.status, 'value', 'completed') if hasattr(transcript, 'status') else 'completed'
            }
            
            # Dodaj dodatkowe informacje dla premium
            if quality == 'premium':
                if hasattr(transcript, 'auto_highlights') and transcript.auto_highlights:
                    result['highlights'] = [
                        {
                            'text': highlight.text,
                            'count': highlight.count,
                            'rank': highlight.rank
                        }
                        for highlight in transcript.auto_highlights.results
                    ]
                
                if hasattr(transcript, 'sentiment_analysis') and transcript.sentiment_analysis:
                    result['sentiment'] = [
                        {
                            'text': sentiment.text,
                            'sentiment': sentiment.sentiment.value,
                            'confidence': sentiment.confidence,
                            'start': sentiment.start,
                            'end': sentiment.end
                        }
                        for sentiment in transcript.sentiment_analysis
                    ]
            
            logger.info(f"Transkrypcja zakończona pomyślnie. Długość tekstu: {len(result['text'])} znaków")
            return result
            
        except Exception as e:
            logger.error(f"Błąd podczas transkrypcji: {e}")
            # Zwróć podstawowy wynik w przypadku błędu
            return {
                'id': 'error',
                'text': 'Błąd podczas transkrypcji',
                'confidence': 0.0,
                'language_code': 'unknown',
                'audio_duration': 0,
                'segments': [{
                    'text': 'Błąd podczas transkrypcji',
                    'start': 0.0,
                    'end': 10.0,
                    'confidence': 0.0,
                    'speaker': 'A'
                }],
                'words': [],
                'status': 'error',
                'error': str(e)
            }
    
    def _extract_segments(self, transcript) -> List[Dict[str, Any]]:
        """
        Wyciągnij segmenty z transkrypcji
        
        Args:
            transcript: Obiekt transkrypcji AssemblyAI
            
        Returns:
            Lista segmentów z czasami
        """
        segments = []
        
        if hasattr(transcript, 'utterances') and transcript.utterances:
            # Jeśli mamy utterances (segmenty mówców)
            for utterance in transcript.utterances:
                segments.append({
                    'text': utterance.text,
                    'start': utterance.start / 1000.0,  # Konwersja z ms na sekundy
                    'end': utterance.end / 1000.0,
                    'confidence': utterance.confidence,
                    'speaker': getattr(utterance, 'speaker', 'A')
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
                
                # Utwórz nowy segment co ~5 sekund lub po 10 słowach
                if (segment_end - segment_start > 5.0) or (len(current_segment) >= 10):
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
    
    def _extract_words(self, transcript) -> List[Dict[str, Any]]:
        """
        Wyciągnij słowa z transkrypcji
        
        Args:
            transcript: Obiekt transkrypcji AssemblyAI
            
        Returns:
            Lista słów z czasami
        """
        words = []
        
        if hasattr(transcript, 'words') and transcript.words:
            for word in transcript.words:
                words.append({
                    'text': word.text,
                    'start': word.start / 1000.0,  # Konwersja z ms na sekundy
                    'end': word.end / 1000.0,
                    'confidence': word.confidence
                })
        
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