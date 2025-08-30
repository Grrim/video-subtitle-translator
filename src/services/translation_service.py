"""
Serwis tłumaczenia tekstu wykorzystujący DeepL API
Obsługuje tłumaczenie maszynowe wysokiej jakości
"""

import deepl
from typing import Dict, Any, List, Optional
import time

from ..utils.logger import get_logger

logger = get_logger(__name__)

class TranslationService:
    """Serwis do tłumaczenia tekstu używając DeepL API"""
    
    def __init__(self, api_key: str):
        """
        Inicjalizuj serwis tłumaczenia
        
        Args:
            api_key: Klucz API DeepL
        """
        if not api_key:
            raise ValueError("Klucz API DeepL jest wymagany")
        
        self.translator = deepl.Translator(api_key)
        self.api_key = api_key
        
        # Inicjalizuj metryki jakości
        self.translation_times = []
        self.translation_quality_scores = []
        
    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = None, 
                      formality: str = 'default', preserve_formatting: bool = True) -> str:
        """
        Przetłumacz tekst
        
        Args:
            text: Tekst do przetłumaczenia
            target_language: Język docelowy (kod DeepL)
            source_language: Język źródłowy (opcjonalny, auto-detect jeśli None)
            formality: Poziom formalności ('default', 'more', 'less')
            preserve_formatting: Czy zachować formatowanie
            
        Returns:
            Przetłumaczony tekst
        """
        try:
            start_time = time.time()
            logger.info(f"Rozpoczynam tłumaczenie na język: {target_language}")
            
            # Mapowanie kodów języków DeepL
            language_map = {
                'EN': 'EN-US',
                'PT': 'PT-PT', 
                'ZH': 'ZH-HANS'
            }
            
            # Użyj mapowania jeśli dostępne
            mapped_target = language_map.get(target_language, target_language)
            
            # Przygotuj parametry tłumaczenia
            translate_params = {
                'target_lang': mapped_target,
                'preserve_formatting': preserve_formatting
            }
            
            # Dodaj język źródłowy jeśli podany
            if source_language:
                translate_params['source_lang'] = source_language
            
            # Dodaj formalność jeśli obsługiwana dla danego języka
            if formality != 'default' and self._supports_formality(target_language):
                translate_params['formality'] = formality
            
            # Wykonaj tłumaczenie
            result = self.translator.translate_text(text, **translate_params)
            
            # Oblicz czas tłumaczenia i jakość
            translation_time = time.time() - start_time
            self.translation_times.append(translation_time)
            
            translated_text = result.text
            detected_language = result.detected_source_lang
            
            # Oszacuj jakość tłumaczenia
            quality_score = self._estimate_translation_quality(text, translated_text, translation_time)
            self.translation_quality_scores.append(quality_score)
            
            logger.info(f"Tłumaczenie zakończone. Wykryty język źródłowy: {detected_language}")
            logger.info(f"Długość przetłumaczonego tekstu: {len(translated_text)} znaków")
            logger.info(f"Czas tłumaczenia: {translation_time:.2f}s, Jakość: {quality_score:.2f}")
            
            return translated_text
            
        except Exception as e:
            logger.error(f"Błąd podczas tłumaczenia: {e}")
            raise Exception(f"Nie można przetłumaczyć tekstu: {e}")
    
    def translate_segments(self, segments: List[Dict[str, Any]], target_language: str, 
                          source_language: Optional[str] = None, formality: str = 'default') -> List[Dict[str, Any]]:
        """
        Przetłumacz segmenty tekstu zachowując strukturę czasową
        
        Args:
            segments: Lista segmentów z tekstem i czasami
            target_language: Język docelowy
            source_language: Język źródłowy (opcjonalny)
            formality: Poziom formalności
            
        Returns:
            Lista przetłumaczonych segmentów
        """
        try:
            start_time = time.time()
            logger.info(f"Rozpoczynam tłumaczenie {len(segments)} segmentów")
            
            translated_segments = []
            failed_segments = []
            
            for i, segment in enumerate(segments):
                if 'text' not in segment:
                    logger.warning(f"Segment {i} nie zawiera tekstu, pomijam")
                    continue
                
                try:
                    # Przetłumacz tekst segmentu
                    translated_text = self.translate_text(
                        segment['text'],
                        target_language=target_language,
                        source_language=source_language,
                        formality=formality
                    )
                    
                    # Skopiuj segment z przetłumaczonym tekstem i dodatkowymi metrykami
                    translated_segment = segment.copy()
                    translated_segment['text'] = translated_text
                    translated_segment['original_text'] = segment['text']
                    translated_segment['translation_quality'] = self._estimate_translation_quality(
                        segment['text'], translated_text, 0.1
                    )
                    translated_segment['target_language'] = target_language
                    translated_segment['formality'] = formality
                    translated_segment['segment_index'] = i
                    
                    translated_segments.append(translated_segment)
                    
                except Exception as e:
                    logger.error(f"Błąd tłumaczenia segmentu {i}: {e}")
                    failed_segments.append(i)
                    
                    # Dodaj segment z błędem
                    error_segment = segment.copy()
                    error_segment['translation_error'] = str(e)
                    error_segment['text'] = segment['text']  # Zachowaj oryginalny tekst
                    error_segment['translation_failed'] = True
                    translated_segments.append(error_segment)
                
                # Dodaj małe opóźnienie aby nie przeciążyć API
                if i < len(segments) - 1:
                    time.sleep(0.1)
            
            total_time = time.time() - start_time
            logger.info(f"Przetłumaczono {len(translated_segments) - len(failed_segments)}/{len(segments)} segmentów w {total_time:.2f}s")
            
            if failed_segments:
                logger.warning(f"Nieudane tłumaczenia segmentów: {failed_segments}")
            
            return translated_segments
            
        except Exception as e:
            logger.error(f"Błąd podczas tłumaczenia segmentów: {e}")
            raise Exception(f"Nie można przetłumaczyć segmentów: {e}")
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Pobierz informacje o wykorzystaniu API
        
        Returns:
            Słownik z informacjami o wykorzystaniu
        """
        try:
            usage = self.translator.get_usage()
            
            return {
                'character_count': usage.character.count,
                'character_limit': usage.character.limit,
                'character_usage_percent': (usage.character.count / usage.character.limit * 100) if usage.character.limit > 0 else 0,
                'document_count': getattr(usage.document, 'count', 0) if hasattr(usage, 'document') else 0,
                'document_limit': getattr(usage.document, 'limit', 0) if hasattr(usage, 'document') else 0
            }
            
        except Exception as e:
            logger.error(f"Błąd podczas pobierania informacji o wykorzystaniu: {e}")
            return {}
    
    def get_supported_languages(self) -> Dict[str, Dict[str, str]]:
        """
        Pobierz listę obsługiwanych języków
        
        Returns:
            Słownik z językami źródłowymi i docelowymi
        """
        try:
            source_languages = self.translator.get_source_languages()
            target_languages = self.translator.get_target_languages()
            
            return {
                'source': {lang.code: lang.name for lang in source_languages},
                'target': {lang.code: lang.name for lang in target_languages}
            }
            
        except Exception as e:
            logger.error(f"Błąd podczas pobierania obsługiwanych języków: {e}")
            return {'source': {}, 'target': {}}
    
    def get_target_languages_for_ui(self) -> Dict[str, str]:
        """
        Pobierz języki docelowe w formacie przyjaznym dla UI
        
        Returns:
            Słownik z kodami i nazwami języków docelowych
        """
        try:
            target_languages = self.translator.get_target_languages()
            
            # Mapowanie kodów DeepL na przyjazne nazwy
            language_names = {
                'BG': 'Bułgarski',
                'CS': 'Czeski',
                'DA': 'Duński',
                'DE': 'Niemiecki',
                'EL': 'Grecki',
                'EN': 'Angielski (amerykański)',
                'EN-GB': 'Angielski (brytyjski)',
                'ES': 'Hiszpański',
                'ET': 'Estoński',
                'FI': 'Fiński',
                'FR': 'Francuski',
                'HU': 'Węgierski',
                'ID': 'Indonezyjski',
                'IT': 'Włoski',
                'JA': 'Japoński',
                'KO': 'Koreański',
                'LT': 'Litewski',
                'LV': 'Łotewski',
                'NB': 'Norweski (Bokmål)',
                'NL': 'Holenderski',
                'PL': 'Polski',
                'PT': 'Portugalski (europejski)',
                'PT-BR': 'Portugalski (brazylijski)',
                'RO': 'Rumuński',
                'RU': 'Rosyjski',
                'SK': 'Słowacki',
                'SL': 'Słoweński',
                'SV': 'Szwedzki',
                'TR': 'Turecki',
                'UK': 'Ukraiński',
                'ZH': 'Chiński (uproszczony)'
            }
            
            result = {}
            for lang in target_languages:
                name = language_names.get(lang.code, lang.name)
                result[lang.code] = name
            
            return result
            
        except Exception as e:
            logger.error(f"Błąd podczas pobierania języków docelowych: {e}")
            return {
                'PL': 'Polski',
                'EN': 'Angielski',
                'DE': 'Niemiecki',
                'FR': 'Francuski',
                'ES': 'Hiszpański',
                'IT': 'Włoski'
            }
    
    def _supports_formality(self, language_code: str) -> bool:
        """
        Sprawdź czy język obsługuje ustawienia formalności
        
        Args:
            language_code: Kod języka
            
        Returns:
            True jeśli język obsługuje formalność
        """
        # Języki obsługujące formalność w DeepL
        formality_languages = ['DE', 'FR', 'IT', 'ES', 'NL', 'PL', 'PT', 'PT-BR', 'RU']
        return language_code.upper() in formality_languages
    
    def check_api_status(self) -> bool:
        """
        Sprawdź status API DeepL
        
        Returns:
            True jeśli API jest dostępne, False w przeciwnym razie
        """
        try:
            # Sprawdź dostępność przez pobranie informacji o wykorzystaniu
            self.translator.get_usage()
            return True
            
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania statusu API DeepL: {e}")
            return False
    
    def _estimate_translation_quality(self, original_text: str, translated_text: str, translation_time: float) -> float:
        """
        Oszacuj jakość tłumaczenia na podstawie różnych metryk
        
        Args:
            original_text: Tekst oryginalny
            translated_text: Tekst przetłumaczony
            translation_time: Czas tłumaczenia
            
        Returns:
            Wynik jakości (0.0 - 1.0)
        """
        if not original_text or not translated_text:
            return 0.0
        
        # Metryki jakości
        quality_factors = []
        
        # 1. Stosunek długości (powinien być rozsądny)
        length_ratio = len(translated_text) / len(original_text)
        if 0.5 <= length_ratio <= 2.0:
            quality_factors.append(0.9)
        elif 0.3 <= length_ratio <= 3.0:
            quality_factors.append(0.7)
        else:
            quality_factors.append(0.3)
        
        # 2. Obecność tekstu (nie pusty)
        if translated_text.strip():
            quality_factors.append(0.9)
        else:
            quality_factors.append(0.0)
        
        # 3. Czas tłumaczenia (szybsze = lepsze API response)
        if translation_time < 2.0:
            quality_factors.append(0.9)
        elif translation_time < 5.0:
            quality_factors.append(0.7)
        else:
            quality_factors.append(0.5)
        
        # 4. Zachowanie interpunkcji
        original_punct = sum(1 for c in original_text if c in '.,!?;:')
        translated_punct = sum(1 for c in translated_text if c in '.,!?;:')
        
        if original_punct > 0:
            punct_ratio = translated_punct / original_punct
            if 0.7 <= punct_ratio <= 1.3:
                quality_factors.append(0.8)
            else:
                quality_factors.append(0.6)
        else:
            quality_factors.append(0.8)  # Brak interpunkcji to OK
        
        # Średnia ważona
        return sum(quality_factors) / len(quality_factors) if quality_factors else 0.5
    
    def get_translation_statistics(self) -> Dict[str, Any]:
        """
        Pobierz statystyki tłumaczeń
        
        Returns:
            Słownik ze statystykami
        """
        if not self.translation_times:
            return {}
        
        import statistics
        
        return {
            'total_translations': len(self.translation_times),
            'average_time': statistics.mean(self.translation_times),
            'min_time': min(self.translation_times),
            'max_time': max(self.translation_times),
            'average_quality': statistics.mean(self.translation_quality_scores) if self.translation_quality_scores else 0.0,
            'min_quality': min(self.translation_quality_scores) if self.translation_quality_scores else 0.0,
            'max_quality': max(self.translation_quality_scores) if self.translation_quality_scores else 0.0
        }