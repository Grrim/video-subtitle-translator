"""
Podsumowanie funkcji AssemblyAI skonfigurowanych w systemie
Wszystkie funkcje są włączone dla najwyższej jakości transkrypcji
"""

from typing import Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AssemblyAIFeaturesSummary:
    """Klasa do wyświetlania podsumowania włączonych funkcji AssemblyAI"""
    
    @staticmethod
    def get_enabled_features() -> Dict[str, Dict[str, str]]:
        """
        Zwraca słownik wszystkich włączonych funkcji AssemblyAI
        
        Returns:
            Słownik z kategoriami i opisami funkcji
        """
        return {
            "🎯 Podstawowe funkcje wysokiej jakości": {
                "Word-level timestamps": "Precyzyjne timestampy dla każdego słowa (dokładność do milisekund)",
                "Speaker labels": "Automatyczne wykrywanie i etykietowanie mówiących (Speaker Diarization)",
                "Language detection": "Automatyczne wykrywanie języka mówionego",
                "Punctuate & format": "Automatyczna interpunkcja i formatowanie tekstu",
                "High boost": "Wysoki poziom wzmocnienia jakości rozpoznawania"
            },
            
            "🤖 Zaawansowane funkcje AI": {
                "Auto highlights": "Automatyczne wyróżnianie kluczowych fragmentów i tematów",
                "Auto chapters": "Automatyczne tworzenie rozdziałów i segmentacja treści",
                "Sentiment analysis": "Analiza sentymentu wypowiedzi (pozytywny/negatywny/neutralny)",
                "Entity detection": "Wykrywanie encji (nazwy osób, miejsc, organizacji)",
                "IAB categories": "Kategoryzacja treści według standardu IAB (Interactive Advertising Bureau)"
            },
            
            "🛡️ Bezpieczeństwo i jakość": {
                "Content safety": "Wykrywanie potencjalnie niebezpiecznych treści",
                "Audio quality optimization": "Optymalizacja dla różnych jakości audio",
                "Noise handling": "Zaawansowane radzenie sobie z szumem tła",
                "Multiple speakers": "Obsługa wielu mówiących jednocześnie"
            },
            
            "⚙️ Ustawienia precyzji": {
                "No profanity filter": "Brak filtrowania wulgaryzmów dla maksymalnej dokładności",
                "No PII redaction": "Brak ukrywania danych osobowych dla pełnej transkrypcji",
                "Single channel optimization": "Optymalizacja dla pojedynczego kanału audio",
                "High confidence threshold": "Wysoki próg pewności dla lepszej jakości"
            }
        }
    
    @staticmethod
    def print_features_summary():
        """Wyświetl podsumowanie wszystkich włączonych funkcji"""
        features = AssemblyAIFeaturesSummary.get_enabled_features()
        
        logger.info("🚀 KONFIGURACJA ASSEMBLYAI - NAJWYŻSZA JAKOŚĆ TRANSKRYPCJI")
        logger.info("=" * 70)
        
        for category, feature_list in features.items():
            logger.info(f"\n{category}")
            logger.info("-" * 50)
            
            for feature_name, description in feature_list.items():
                logger.info(f"✅ {feature_name}: {description}")
        
        logger.info("\n" + "=" * 70)
        logger.info("🎬 System gotowy do transkrypcji najwyższej jakości!")
    
    @staticmethod
    def get_quality_metrics_info() -> Dict[str, str]:
        """
        Zwraca informacje o metrykach jakości które system będzie śledzić
        
        Returns:
            Słownik z opisami metryk
        """
        return {
            "Confidence Score": "Ogólna pewność transkrypcji (0.0 - 1.0)",
            "Word-level Accuracy": "Dokładność timestampów na poziomie słów",
            "Speaker Detection Quality": "Jakość wykrywania i rozróżniania mówiących",
            "Processing Speed": "Czas przetwarzania względem długości audio",
            "Language Detection Confidence": "Pewność automatycznego wykrywania języka",
            "Segment Quality": "Jakość podziału na naturalne segmenty",
            "Entity Recognition Rate": "Skuteczność wykrywania encji",
            "Sentiment Analysis Coverage": "Pokrycie analizy sentymentu"
        }
    
    @staticmethod
    def validate_api_features(transcript_result: Dict) -> List[str]:
        """
        Waliduje czy wszystkie oczekiwane funkcje zostały zwrócone przez API
        
        Args:
            transcript_result: Wynik transkrypcji z API
            
        Returns:
            Lista ostrzeżeń o brakujących funkcjach
        """
        warnings = []
        
        # Sprawdź podstawowe funkcje
        if not transcript_result.get('words'):
            warnings.append("⚠️ Brak word-level timestamps")
        
        if not transcript_result.get('segments'):
            warnings.append("⚠️ Brak segmentów z speaker labels")
        
        # Sprawdź funkcje premium
        expected_premium_features = [
            ('highlights', 'Auto highlights'),
            ('sentiment', 'Sentiment analysis'),
            ('entities', 'Entity detection'),
            ('chapters', 'Auto chapters'),
            ('categories', 'IAB categories'),
            ('content_safety', 'Content safety')
        ]
        
        for feature_key, feature_name in expected_premium_features:
            if feature_key not in transcript_result:
                warnings.append(f"⚠️ Brak funkcji: {feature_name}")
        
        if not warnings:
            logger.info("✅ Wszystkie funkcje AssemblyAI działają prawidłowo!")
        else:
            for warning in warnings:
                logger.warning(warning)
        
        return warnings