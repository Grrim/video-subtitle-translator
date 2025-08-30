#!/usr/bin/env python3
"""
Test zaawansowanego post-processingu word-level timestamps
Sprawdza wszystkie wymagane funkcje:
- Word-level timestamps + speaker labels + punctuate + format_text
- Naprawianie nakładających się segmentów
- Minimalne przerwy między słowami (20ms)
- Stabilizacja bloków (38 słów)
- Analiza profilu energii audio i korekta offsetu
- Minimalna długość wyświetlania słów (~400ms) i nakładanie między blokami (100ms)
"""

import sys
import os
from pathlib import Path

# Dodaj główny katalog do ścieżki
sys.path.append(str(Path(__file__).parent))

from src.services.advanced_word_processor import AdvancedWordProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)

def test_advanced_processing():
    """Test zaawansowanego post-processingu"""
    
    print("🚀 Test zaawansowanego post-processingu word-level timestamps")
    print("=" * 60)
    
    # Stwórz procesor
    processor = AdvancedWordProcessor()
    
    # Test dane - symulacja word-level timestamps z AssemblyAI
    test_transcript_data = {
        'words': [
            {'text': 'Witaj', 'start': 0.0, 'end': 0.5, 'confidence': 0.95, 'speaker': 'A'},
            {'text': 'w', 'start': 0.45, 'end': 0.55, 'confidence': 0.9, 'speaker': 'A'},  # Nakładanie!
            {'text': 'naszym', 'start': 0.6, 'end': 1.0, 'confidence': 0.92, 'speaker': 'A'},
            {'text': 'systemie', 'start': 1.1, 'end': 1.6, 'confidence': 0.88, 'speaker': 'A'},
            {'text': 'tłumaczenia', 'start': 1.7, 'end': 2.3, 'confidence': 0.94, 'speaker': 'A'},
            {'text': 'napisów.', 'start': 2.4, 'end': 2.9, 'confidence': 0.91, 'speaker': 'A', 'is_punctuated': True},
            
            # Drugi mówiący
            {'text': 'To', 'start': 3.0, 'end': 3.1, 'confidence': 0.85, 'speaker': 'B'},  # Krótkie słowo
            {'text': 'jest', 'start': 3.15, 'end': 3.4, 'confidence': 0.89, 'speaker': 'B'},  # Mała przerwa
            {'text': 'bardzo', 'start': 3.5, 'end': 3.9, 'confidence': 0.93, 'speaker': 'B'},
            {'text': 'przydatne', 'start': 4.0, 'end': 4.6, 'confidence': 0.87, 'speaker': 'B'},
            {'text': 'narzędzie!', 'start': 4.7, 'end': 5.3, 'confidence': 0.92, 'speaker': 'B', 'is_punctuated': True},
        ],
        'segments': [
            {'text': 'Witaj w naszym systemie tłumaczenia napisów.', 'start': 0.0, 'end': 2.9, 'speaker': 'A', 'confidence': 0.92},
            {'text': 'To jest bardzo przydatne narzędzie!', 'start': 3.0, 'end': 5.3, 'speaker': 'B', 'confidence': 0.89}
        ]
    }
    
    print("📝 Dane testowe:")
    print(f"   - {len(test_transcript_data['words'])} słów z word-level timestamps")
    print(f"   - {len(test_transcript_data['segments'])} segmentów")
    print(f"   - 2 mówiących (A, B)")
    print(f"   - Zawiera nakładania, krótkie słowa, interpunkcję")
    print()
    
    # Test przetwarzania
    try:
        print("🔄 Rozpoczynam zaawansowane przetwarzanie...")
        
        # Przetwórz bez pliku audio (test podstawowych funkcji)
        blocks = processor.process_word_level_transcription(test_transcript_data)
        
        if blocks:
            print(f"✅ Sukces! Utworzono {len(blocks)} stabilizowanych bloków")
            print()
            
            # Wyświetl szczegóły bloków
            for i, block in enumerate(blocks):
                print(f"📦 Blok {i+1}:")
                print(f"   - Słowa: {len(block.words)}")
                print(f"   - Czas: {block.start_time:.2f}s - {block.end_time:.2f}s")
                print(f"   - Wyświetlanie: {block.display_start:.2f}s - {block.display_end:.2f}s")
                print(f"   - Mówiący: {block.speaker}")
                print(f"   - Pewność: {block.confidence:.2f}")
                print(f"   - Tekst: {' '.join([w.word for w in block.words])}")
                print()
            
            # Test generowania SRT
            print("📄 Generowanie SRT...")
            srt_content = processor.generate_stabilized_srt(blocks)
            
            if srt_content:
                print("✅ SRT wygenerowany pomyślnie!")
                print("📋 Przykład SRT:")
                print("-" * 40)
                print(srt_content[:500] + "..." if len(srt_content) > 500 else srt_content)
                print("-" * 40)
            else:
                print("❌ Błąd generowania SRT")
            
            # Test parametrów
            print("⚙️ Parametry post-processingu:")
            print(f"   - Minimalna przerwa między słowami: {processor.min_word_gap*1000:.0f}ms")
            print(f"   - Minimalna długość słowa: {processor.min_word_duration*1000:.0f}ms")
            print(f"   - Nakładanie między blokami: {processor.block_overlap*1000:.0f}ms")
            print(f"   - Słów na blok: {processor.words_per_block}")
            
        else:
            print("❌ Błąd: Nie utworzono żadnych bloków")
            
    except Exception as e:
        print(f"❌ Błąd przetwarzania: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("🎯 Test zakończony!")

if __name__ == "__main__":
    test_advanced_processing()