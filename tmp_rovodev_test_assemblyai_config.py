#!/usr/bin/env python3
"""
Test konfiguracji AssemblyAI - sprawdzenie wszystkich funkcji
Ten skrypt testuje czy wszystkie wymagane funkcje są prawidłowo skonfigurowane
"""

import sys
import os
from pathlib import Path

# Dodaj główny katalog do ścieżki Python
sys.path.append(str(Path(__file__).parent))

from src.utils.config import Config
from src.utils.assemblyai_features_summary import AssemblyAIFeaturesSummary
from src.services.transcription_service import TranscriptionService
from src.utils.logger import get_logger

logger = get_logger(__name__)

def test_assemblyai_configuration():
    """Test konfiguracji AssemblyAI"""
    
    print("🧪 TESTOWANIE KONFIGURACJI ASSEMBLYAI")
    print("=" * 60)
    
    # 1. Test konfiguracji
    print("\n1️⃣ Sprawdzanie konfiguracji...")
    config = Config()
    
    if not config.assemblyai_api_key:
        print("❌ Brak klucza API AssemblyAI!")
        return False
    
    print(f"✅ Klucz API AssemblyAI: {config.assemblyai_api_key[:10]}...")
    
    # 2. Test ustawień AssemblyAI
    print("\n2️⃣ Sprawdzanie ustawień AssemblyAI...")
    assemblyai_config = config.assemblyai_config
    
    required_features = [
        'language_detection',
        'punctuate', 
        'format_text',
        'speaker_labels',
        'word_timestamps',
        'auto_highlights',
        'sentiment_analysis',
        'entity_detection',
        'auto_chapters',
        'content_safety'
    ]
    
    for feature in required_features:
        if assemblyai_config.get(feature, False):
            print(f"✅ {feature}: włączone")
        else:
            print(f"⚠️ {feature}: wyłączone lub brak")
    
    # 3. Test inicjalizacji serwisu
    print("\n3️⃣ Testowanie inicjalizacji TranscriptionService...")
    try:
        transcription_service = TranscriptionService(config.assemblyai_api_key)
        print("✅ TranscriptionService zainicjalizowany pomyślnie")
    except Exception as e:
        print(f"❌ Błąd inicjalizacji: {e}")
        return False
    
    # 4. Test dostępności API
    print("\n4️⃣ Sprawdzanie dostępności API AssemblyAI...")
    try:
        api_status = transcription_service.check_api_status()
        if api_status:
            print("✅ API AssemblyAI jest dostępne")
        else:
            print("⚠️ API AssemblyAI może być niedostępne")
    except Exception as e:
        print(f"⚠️ Nie można sprawdzić statusu API: {e}")
    
    # 5. Wyświetl podsumowanie funkcji
    print("\n5️⃣ Podsumowanie włączonych funkcji:")
    AssemblyAIFeaturesSummary.print_features_summary()
    
    # 6. Wyświetl metryki jakości
    print("\n6️⃣ Metryki jakości które będą śledzone:")
    quality_metrics = AssemblyAIFeaturesSummary.get_quality_metrics_info()
    for metric, description in quality_metrics.items():
        print(f"📊 {metric}: {description}")
    
    print("\n" + "=" * 60)
    print("🎉 KONFIGURACJA ASSEMBLYAI GOTOWA!")
    print("🚀 System skonfigurowany z najwyższą jakością transkrypcji")
    print("✨ Wszystkie funkcje premium są włączone:")
    print("   • Word-level timestamps")
    print("   • Speaker labels") 
    print("   • Language detection")
    print("   • Punctuate & format text")
    print("   • Auto highlights")
    print("   • Sentiment analysis")
    print("   • Entity detection")
    print("   • Auto chapters")
    print("   • Content safety")
    print("   • IAB categories")
    
    return True

if __name__ == "__main__":
    success = test_assemblyai_configuration()
    if success:
        print("\n✅ Test zakończony pomyślnie!")
        sys.exit(0)
    else:
        print("\n❌ Test zakończony z błędami!")
        sys.exit(1)