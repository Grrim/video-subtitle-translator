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
            
            translated_text = result.text
            detected_language = result.detected_source_lang
            
            logger.info(f"Tłumaczenie zakończone. Wykryty język źródłowy: {detected_language}")
            logger.info(f"Długość przetłumaczonego tekstu: {len(translated_text)} znaków")
            
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
            logger.info(f"Rozpoczynam tłumaczenie {len(segments)} segmentów")
            
            translated_segments = []
            
            for i, segment in enumerate(segments):
                if 'text' not in segment:
                    logger.warning(f"Segment {i} nie zawiera tekstu, pomijam")
                    continue
                
                # Przetłumacz tekst segmentu
                translated_text = self.translate_text(
                    segment['text'],
                    target_language=target_language,
                    source_language=source_language,
                    formality=formality
                )
                
                # Skopiuj segment z przetłumaczonym tekstem
                translated_segment = segment.copy()
                translated_segment['text'] = translated_text
                translated_segment['original_text'] = segment['text']
                
                translated_segments.append(translated_segment)
                
                # Dodaj małe opóźnienie aby nie przeciążyć API
                if i < len(segments) - 1:
                    time.sleep(0.1)
            
            logger.info(f"Przetłumaczono {len(translated_segments)} segmentów")
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