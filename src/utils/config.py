"""
Konfiguracja aplikacji - zarządzanie kluczami API i ustawieniami
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

class Config:
    """Klasa zarządzająca konfiguracją aplikacji"""
    
    def __init__(self):
        # Załaduj zmienne środowiskowe z pliku .env
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        # Klucze API
        self.assemblyai_api_key = os.getenv('ASSEMBLYAI_API_KEY')
        self.deepl_api_key = os.getenv('DEEPL_API_KEY')
        
        # Ustawienia aplikacji
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        self.max_file_size_mb = int(os.getenv('MAX_FILE_SIZE_MB', '500'))
        self.supported_video_formats = [
            'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 
            'm4v', '3gp', 'ogv', 'ts', 'mts', 'm2ts'
        ]
        
        # Ustawienia AssemblyAI - NAJWYŻSZA JAKOŚĆ
        self.assemblyai_config = {
            # Podstawowe ustawienia wysokiej jakości
            'language_detection': True,          # Automatyczne wykrywanie języka
            'punctuate': True,                   # Interpunkcja i formatowanie
            'format_text': True,                 # Formatowanie tekstu
            'speaker_labels': True,              # Etykiety mówiących (speaker diarization)
            
            # Word-level timestamps dla maksymalnej precyzji
            'word_timestamps': True,             # Włącz word-level timestamps
            'dual_channel': False,               # Dla lepszej precyzji timestampów
            
            # Dodatkowe funkcje poprawiające jakość
            'auto_chapters': True,               # Automatyczne rozdziały
            'entity_detection': True,            # Wykrywanie encji (nazwy, miejsca)
            'sentiment_analysis': True,          # Analiza sentymentu
            'auto_highlights': True,             # Automatyczne wyróżnienia
            'content_safety': True,              # Filtrowanie treści
            
            # Ustawienia jakości audio
            'filter_profanity': False,           # Nie filtruj wulgaryzmów (dla dokładności)
            'redact_pii': False,                 # Nie ukrywaj danych osobowych
            'redact_pii_audio': False,           # Nie ukrywaj w audio
            
            # Boost dla lepszej jakości
            'word_boost': [],                    # Lista słów do wzmocnienia
            'boost_param': 'high',               # Wysoki poziom wzmocnienia
            
            # Ustawienia modelu
            'speech_model': 'best',              # Najlepszy dostępny model
            'language_confidence_threshold': 0.7, # Próg pewności języka
            'audio_start_from': 0,               # Start od początku
            'audio_end_at': None,                # Do końca pliku
        }
        
        # Ustawienia DeepL
        self.deepl_config = {
            'preserve_formatting': True,
            'split_sentences': 'nonewlines',
            'outline_detection': False,
            'non_splitting_tags': ['code', 'pre'],
            'splitting_tags': ['p', 'br', 'div']
        }
        
        # Mapowanie języków DeepL
        self.deepl_language_map = {
            'PL': 'PL',
            'EN': 'EN-US',
            'DE': 'DE',
            'FR': 'FR',
            'ES': 'ES',
            'IT': 'IT',
            'PT': 'PT-PT',
            'RU': 'RU',
            'JA': 'JA',
            'ZH': 'ZH',
            'NL': 'NL',
            'SV': 'SV',
            'DA': 'DA',
            'FI': 'FI',
            'NO': 'NB',
            'CS': 'CS',
            'SK': 'SK',
            'SL': 'SL',
            'ET': 'ET',
            'LV': 'LV',
            'LT': 'LT',
            'BG': 'BG',
            'HU': 'HU',
            'RO': 'RO',
            'EL': 'EL',
            'TR': 'TR',
            'UK': 'UK',
            'ID': 'ID',
            'KO': 'KO',
            'AR': 'AR'
        }
        
        # Nazwy języków dla interfejsu
        self.language_names = {
            'PL': 'Polski',
            'EN': 'English',
            'DE': 'Deutsch',
            'FR': 'Français',
            'ES': 'Español',
            'IT': 'Italiano',
            'PT': 'Português',
            'RU': 'Русский',
            'JA': '日本語',
            'ZH': '中文',
            'NL': 'Nederlands',
            'SV': 'Svenska',
            'DA': 'Dansk',
            'FI': 'Suomi',
            'NO': 'Norsk',
            'CS': 'Čeština',
            'SK': 'Slovenčina',
            'SL': 'Slovenščina',
            'ET': 'Eesti',
            'LV': 'Latviešu',
            'LT': 'Lietuvių',
            'BG': 'Български',
            'HU': 'Magyar',
            'RO': 'Română',
            'EL': 'Ελληνικά',
            'TR': 'Türkçe',
            'UK': 'Українська',
            'ID': 'Bahasa Indonesia',
            'KO': '한국어',
            'AR': 'العربية'
        }
    
    def is_configured(self) -> bool:
        """Sprawdź czy aplikacja jest skonfigurowana"""
        return bool(self.assemblyai_api_key and self.deepl_api_key)
    
    def get_missing_config(self) -> list:
        """Pobierz listę brakujących konfiguracji"""
        missing = []
        if not self.assemblyai_api_key:
            missing.append('ASSEMBLYAI_API_KEY')
        if not self.deepl_api_key:
            missing.append('DEEPL_API_KEY')
        return missing
    
    def get_deepl_language_code(self, language_code: str) -> str:
        """Pobierz kod języka dla DeepL API"""
        return self.deepl_language_map.get(language_code, language_code)
    
    def get_language_name(self, language_code: str) -> str:
        """Pobierz nazwę języka"""
        return self.language_names.get(language_code, language_code)