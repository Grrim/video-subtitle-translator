"""
Zaawansowany procesor słów z funkcjami post-processingu
Implementuje wszystkie wymagane funkcje:
- Word-level timestamps + speaker labels + punctuate + format_text
- Naprawianie nakładających się segmentów
- Minimalne przerwy między słowami (20ms)
- Stabilizacja bloków (38 słów)
- Analiza profilu energii audio i korekta offsetu (cross-correlation)
- Minimalna długość wyświetlania słów (~400ms) i nakładanie między blokami (100ms)
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import re
from scipy import signal
from scipy.signal import correlate
import logging

from ..utils.logger import get_logger
from .word_level_sync import WordTiming, WordLevelSegment

logger = get_logger(__name__)

@dataclass
class AudioEnergyProfile:
    """Profil energii audio dla korekty offsetu"""
    timestamps: np.ndarray
    energy_values: np.ndarray
    sample_rate: float
    window_size: float = 0.025  # 25ms okno
    
@dataclass
class StabilizedBlock:
    """Stabilizowany blok 38 słów"""
    block_id: int
    words: List[WordTiming]
    start_time: float
    end_time: float
    display_start: float  # Z nakładaniem
    display_end: float    # Z nakładaniem
    speaker: str
    confidence: float
    word_count: int = field(init=False)
    
    def __post_init__(self):
        self.word_count = len(self.words)

class AdvancedWordProcessor:
    """Zaawansowany procesor słów z pełnym post-processingiem"""
    
    def __init__(self):
        # Podstawowe parametry
        self.min_word_gap = 0.020  # 20ms minimalna przerwa między słowami
        self.min_word_duration = 0.400  # 400ms minimalna długość wyświetlania słowa
        self.block_overlap = 0.100  # 100ms nakładanie między blokami
        self.words_per_block = 38  # Stabilizacja bloków na 38 słów
        
        # Parametry korekty offsetu
        self.cross_correlation_window = 1.0  # 1s okno dla cross-correlation
        self.energy_threshold = 0.1  # Próg energii dla wykrywania mowy
        self.max_offset_correction = 0.200  # Maksymalna korekta offsetu (200ms)
        
        # Cache dla profili energii
        self._energy_profiles: Dict[str, AudioEnergyProfile] = {}
        
    def process_word_level_transcription(self, 
                                       transcript_data: Dict[str, Any],
                                       audio_file_path: Optional[str] = None) -> List[StabilizedBlock]:
        """
        Główna funkcja przetwarzania transkrypcji z pełnym post-processingiem
        
        Args:
            transcript_data: Dane transkrypcji z AssemblyAI (z word-level timestamps)
            audio_file_path: Ścieżka do pliku audio (opcjonalnie dla analizy energii)
            
        Returns:
            Lista stabilizowanych bloków z przetworzonym timingiem
        """
        logger.info("🚀 Rozpoczynam zaawansowane przetwarzanie word-level timestamps...")
        
        # 1. Wyciągnij słowa z precyzyjnymi timestampami
        words = self._extract_precise_word_timings(transcript_data)
        if not words:
            logger.error("❌ Brak word-level timestamps do przetworzenia")
            return []
        
        logger.info(f"📝 Wyciągnięto {len(words)} słów z word-level timestamps")
        
        # 2. Napraw nakładające się segmenty
        words = self._fix_overlapping_segments(words)
        logger.info("✅ Naprawiono nakładające się segmenty")
        
        # 3. Dodaj minimalne przerwy między słowami (20ms)
        words = self._add_minimum_word_gaps(words)
        logger.info("✅ Dodano minimalne przerwy między słowami (20ms)")
        
        # 4. Analiza profilu energii audio i korekta offsetu (jeśli dostępny plik audio)
        if audio_file_path:
            words = self._apply_energy_based_offset_correction(words, audio_file_path)
            logger.info("✅ Zastosowano korektę offsetu na podstawie profilu energii")
        
        # 5. Zastosuj minimalną długość wyświetlania słów (~400ms)
        words = self._apply_minimum_display_duration(words)
        logger.info("✅ Zastosowano minimalną długość wyświetlania słów (400ms)")
        
        # 6. Stabilizuj bloki (38 słów) z nakładaniem (100ms)
        blocks = self._stabilize_blocks_with_overlap(words)
        logger.info(f"✅ Utworzono {len(blocks)} stabilizowanych bloków (38 słów każdy)")
        
        # 7. Finalna optymalizacja i walidacja
        blocks = self._final_optimization_and_validation(blocks)
        logger.info("✅ Zakończono finalną optymalizację")
        
        logger.info(f"🎯 Przetwarzanie zakończone: {len(blocks)} bloków gotowych")
        return blocks
    
    def _extract_precise_word_timings(self, transcript_data: Dict[str, Any]) -> List[WordTiming]:
        """
        Wyciągnij precyzyjne word-level timestamps z AssemblyAI
        Priorytet: word-level timestamps > segmenty > fallback
        """
        words = []
        
        # PRIORYTET 1: Word-level timestamps z AssemblyAI
        if 'words' in transcript_data and transcript_data['words']:
            logger.info(f"🎯 Używam {len(transcript_data['words'])} precyzyjnych word-level timestamps")
            
            for i, word_data in enumerate(transcript_data['words']):
                word = WordTiming(
                    word=word_data.get('text', '').strip(),
                    start=float(word_data.get('start', 0.0)),
                    end=float(word_data.get('end', 0.0)),
                    confidence=float(word_data.get('confidence', 0.8)),
                    speaker=word_data.get('speaker', 'A'),
                    word_index=i,
                    duration=float(word_data.get('end', 0.0) - word_data.get('start', 0.0)),
                    is_punctuated=any(p in word_data.get('text', '') for p in '.,!?;:'),
                    is_estimated=word_data.get('estimated', False)
                )
                
                if word.word and word.start >= 0 and word.end > word.start:
                    words.append(word)
            
            return words
        
        # PRIORYTET 2: Segmenty z speaker labels
        elif 'segments' in transcript_data and transcript_data['segments']:
            logger.warning("⚠️ Brak word-level timestamps, tworzę z segmentów")
            return self._estimate_words_from_segments(transcript_data['segments'])
        
        else:
            logger.error("❌ Brak danych word-level i segmentów")
            return []
    
    def _fix_overlapping_segments(self, words: List[WordTiming]) -> List[WordTiming]:
        """
        Napraw nakładające się segmenty słów
        Algorytm: wykryj nakładania i dostosuj timing zachowując naturalny przepływ
        """
        if len(words) <= 1:
            return words
        
        fixed_words = []
        overlaps_fixed = 0
        
        for i, word in enumerate(words):
            current_word = WordTiming(
                word=word.word,
                start=word.start,
                end=word.end,
                confidence=word.confidence,
                speaker=word.speaker,
                word_index=word.word_index,
                duration=word.duration,
                is_punctuated=word.is_punctuated,
                is_estimated=word.is_estimated
            )
            
            # Sprawdź nakładanie z poprzednim słowem
            if i > 0:
                prev_word = fixed_words[-1]
                
                if current_word.start < prev_word.end:
                    # NAKŁADANIE WYKRYTE
                    overlap_duration = prev_word.end - current_word.start
                    
                    # Strategia naprawy zależna od wielkości nakładania
                    if overlap_duration <= 0.050:  # Małe nakładanie (≤50ms)
                        # Przesuń start aktualnego słowa
                        current_word.start = prev_word.end + self.min_word_gap
                        current_word.duration = current_word.end - current_word.start
                        
                    elif overlap_duration <= 0.200:  # Średnie nakładanie (≤200ms)
                        # Podziel nakładanie między słowa
                        overlap_split = overlap_duration / 2
                        prev_word.end -= overlap_split
                        current_word.start = prev_word.end + self.min_word_gap
                        
                        # Aktualizuj poprzednie słowo w liście
                        fixed_words[-1] = prev_word
                        current_word.duration = current_word.end - current_word.start
                        
                    else:  # Duże nakładanie (>200ms)
                        # Radykalna korekta - zachowaj proporcje
                        total_duration = current_word.end - prev_word.start
                        prev_duration_ratio = (prev_word.end - prev_word.start) / (overlap_duration + (prev_word.end - prev_word.start) + (current_word.end - current_word.start))
                        
                        prev_word.end = prev_word.start + (total_duration * prev_duration_ratio)
                        current_word.start = prev_word.end + self.min_word_gap
                        
                        # Aktualizuj poprzednie słowo
                        fixed_words[-1] = prev_word
                        current_word.duration = current_word.end - current_word.start
                    
                    overlaps_fixed += 1
            
            fixed_words.append(current_word)
        
        logger.info(f"🔧 Naprawiono {overlaps_fixed} nakładających się segmentów")
        return fixed_words
    
    def _add_minimum_word_gaps(self, words: List[WordTiming]) -> List[WordTiming]:
        """
        Dodaj minimalne przerwy między słowami (20ms)
        Zachowaj naturalny rytm mowy
        """
        if len(words) <= 1:
            return words
        
        gapped_words = []
        gaps_added = 0
        
        for i, word in enumerate(words):
            current_word = WordTiming(
                word=word.word,
                start=word.start,
                end=word.end,
                confidence=word.confidence,
                speaker=word.speaker,
                word_index=word.word_index,
                duration=word.duration,
                is_punctuated=word.is_punctuated,
                is_estimated=word.is_estimated
            )
            
            # Sprawdź przerwę z poprzednim słowem
            if i > 0:
                prev_word = gapped_words[-1]
                current_gap = current_word.start - prev_word.end
                
                if current_gap < self.min_word_gap:
                    # Za mała przerwa - dostosuj
                    if current_gap < 0:
                        # Nakładanie - przesuń start
                        current_word.start = prev_word.end + self.min_word_gap
                    else:
                        # Mała przerwa - zwiększ do minimum
                        current_word.start = prev_word.end + self.min_word_gap
                    
                    # Zachowaj oryginalną długość słowa jeśli możliwe
                    original_duration = word.end - word.start
                    current_word.end = current_word.start + original_duration
                    current_word.duration = original_duration
                    
                    gaps_added += 1
            
            gapped_words.append(current_word)
        
        logger.info(f"📏 Dodano/poprawiono {gaps_added} przerw między słowami")
        return gapped_words
    
    def _apply_energy_based_offset_correction(self, words: List[WordTiming], audio_file_path: str) -> List[WordTiming]:
        """
        Analiza profilu energii audio i korekta offsetu używając cross-correlation
        """
        try:
            # Załaduj profil energii audio
            energy_profile = self._load_audio_energy_profile(audio_file_path)
            
            # Oblicz cross-correlation między timestampami a energią
            offset_correction = self._calculate_cross_correlation_offset(words, energy_profile)
            
            if abs(offset_correction) > 0.001:  # Jeśli korekta > 1ms
                # Zastosuj korektę do wszystkich słów
                corrected_words = []
                for word in words:
                    corrected_word = WordTiming(
                        word=word.word,
                        start=word.start + offset_correction,
                        end=word.end + offset_correction,
                        confidence=word.confidence,
                        speaker=word.speaker,
                        word_index=word.word_index,
                        duration=word.duration,
                        is_punctuated=word.is_punctuated,
                        is_estimated=word.is_estimated
                    )
                    corrected_words.append(corrected_word)
                
                logger.info(f"🎯 Zastosowano korektę offsetu: {offset_correction*1000:.1f}ms")
                return corrected_words
            
            else:
                logger.info("✅ Brak potrzeby korekty offsetu (timestamps precyzyjne)")
                return words
                
        except Exception as e:
            logger.warning(f"⚠️ Nie udało się zastosować korekty energii: {e}")
            return words
    
    def _load_audio_energy_profile(self, audio_file_path: str) -> AudioEnergyProfile:
        """
        Załaduj i oblicz profil energii audio
        """
        # Sprawdź cache
        if audio_file_path in self._energy_profiles:
            return self._energy_profiles[audio_file_path]
        
        try:
            import librosa
            
            # Załaduj audio
            y, sr = librosa.load(audio_file_path, sr=None)
            
            # Oblicz energię w oknach
            hop_length = int(sr * self.cross_correlation_window / 100)  # 10ms hop
            frame_length = int(sr * 0.025)  # 25ms okno
            
            # RMS energy
            rms_energy = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Timestamps dla każdej ramki
            timestamps = librosa.frames_to_time(range(len(rms_energy)), sr=sr, hop_length=hop_length)
            
            profile = AudioEnergyProfile(
                timestamps=timestamps,
                energy_values=rms_energy,
                sample_rate=sr,
                window_size=0.025
            )
            
            # Cache profil
            self._energy_profiles[audio_file_path] = profile
            
            logger.info(f"📊 Załadowano profil energii: {len(timestamps)} ramek, {timestamps[-1]:.1f}s")
            return profile
            
        except ImportError:
            logger.warning("⚠️ Brak librosa - nie można analizować energii audio")
            raise
        except Exception as e:
            logger.error(f"❌ Błąd ładowania profilu energii: {e}")
            raise
    
    def _calculate_cross_correlation_offset(self, words: List[WordTiming], energy_profile: AudioEnergyProfile) -> float:
        """
        Oblicz optymalny offset używając cross-correlation między timestampami a energią
        """
        if not words or len(energy_profile.timestamps) < 10:
            return 0.0
        
        # Stwórz sygnał aktywności mowy z timestampów słów
        max_time = max(words[-1].end, energy_profile.timestamps[-1])
        time_resolution = 0.010  # 10ms rozdzielczość
        time_grid = np.arange(0, max_time, time_resolution)
        
        # Sygnał aktywności z timestampów
        speech_activity = np.zeros_like(time_grid)
        for word in words:
            start_idx = int(word.start / time_resolution)
            end_idx = int(word.end / time_resolution)
            if start_idx < len(speech_activity) and end_idx < len(speech_activity):
                speech_activity[start_idx:end_idx] = 1.0
        
        # Interpoluj energię na tę samą siatkę czasową
        energy_interpolated = np.interp(time_grid, energy_profile.timestamps, energy_profile.energy_values)
        
        # Normalizuj sygnały
        energy_interpolated = (energy_interpolated - np.mean(energy_interpolated)) / np.std(energy_interpolated)
        speech_activity = (speech_activity - np.mean(speech_activity)) / np.std(speech_activity)
        
        # Cross-correlation
        correlation = correlate(energy_interpolated, speech_activity, mode='full')
        
        # Znajdź maksimum korelacji
        max_corr_idx = np.argmax(correlation)
        offset_samples = max_corr_idx - (len(speech_activity) - 1)
        offset_seconds = offset_samples * time_resolution
        
        # Ogranicz korektę do rozsądnych wartości
        offset_seconds = np.clip(offset_seconds, -self.max_offset_correction, self.max_offset_correction)
        
        correlation_strength = np.max(correlation) / len(speech_activity)
        logger.info(f"🔍 Cross-correlation: offset={offset_seconds*1000:.1f}ms, siła={correlation_strength:.3f}")
        
        return offset_seconds
    
    def _apply_minimum_display_duration(self, words: List[WordTiming]) -> List[WordTiming]:
        """
        Zastosuj minimalną długość wyświetlania słów (~400ms)
        Szczególnie dla krótkich słów i nagłych pauz
        """
        extended_words = []
        extensions_applied = 0
        
        for word in words:
            current_duration = word.end - word.start
            
            # Sprawdź czy słowo potrzebuje wydłużenia
            needs_extension = (
                current_duration < self.min_word_duration or  # Za krótkie
                len(word.word) <= 2 or  # Bardzo krótkie słowo (1-2 znaki)
                word.is_punctuated  # Słowo z interpunkcją (pauza)
            )
            
            if needs_extension:
                # Oblicz nową długość
                if len(word.word) <= 2:
                    # Bardzo krótkie słowa - minimum 400ms
                    new_duration = self.min_word_duration
                elif word.is_punctuated:
                    # Słowa z interpunkcją - dodatkowy czas na pauzę
                    new_duration = max(self.min_word_duration, current_duration * 1.5)
                else:
                    # Standardowe wydłużenie
                    new_duration = self.min_word_duration
                
                extended_word = WordTiming(
                    word=word.word,
                    start=word.start,
                    end=word.start + new_duration,
                    confidence=word.confidence,
                    speaker=word.speaker,
                    word_index=word.word_index,
                    duration=new_duration,
                    is_punctuated=word.is_punctuated,
                    is_estimated=word.is_estimated
                )
                
                extended_words.append(extended_word)
                extensions_applied += 1
            else:
                extended_words.append(word)
        
        logger.info(f"⏱️ Wydłużono {extensions_applied} słów do minimalnej długości wyświetlania")
        return extended_words
    
    def _stabilize_blocks_with_overlap(self, words: List[WordTiming]) -> List[StabilizedBlock]:
        """
        Stabilizuj bloki (38 słów) z nakładaniem między blokami (100ms)
        """
        if not words:
            return []
        
        blocks = []
        block_id = 0
        
        # Podziel słowa na bloki po 38 słów
        for i in range(0, len(words), self.words_per_block):
            block_words = words[i:i + self.words_per_block]
            
            if not block_words:
                continue
            
            # Podstawowy timing bloku
            block_start = block_words[0].start
            block_end = block_words[-1].end
            
            # Oblicz timing wyświetlania z nakładaniem
            display_start = block_start
            display_end = block_end
            
            # Nakładanie z poprzednim blokiem
            if blocks:
                prev_block = blocks[-1]
                overlap_start = max(block_start - self.block_overlap, prev_block.display_start)
                display_start = overlap_start
                
                # Aktualizuj poprzedni blok żeby nakładał się z tym
                prev_block.display_end = min(prev_block.display_end + self.block_overlap, block_start + self.block_overlap)
            
            # Nakładanie z następnym blokiem (będzie zaktualizowane później)
            if i + self.words_per_block < len(words):
                display_end += self.block_overlap
            
            # Oblicz średnią pewność i dominującego mówiącego
            confidences = [w.confidence for w in block_words]
            speakers = [w.speaker for w in block_words]
            avg_confidence = np.mean(confidences)
            dominant_speaker = max(set(speakers), key=speakers.count)
            
            block = StabilizedBlock(
                block_id=block_id,
                words=block_words,
                start_time=block_start,
                end_time=block_end,
                display_start=display_start,
                display_end=display_end,
                speaker=dominant_speaker,
                confidence=avg_confidence
            )
            
            blocks.append(block)
            block_id += 1
        
        logger.info(f"📦 Utworzono {len(blocks)} stabilizowanych bloków z nakładaniem {self.block_overlap*1000:.0f}ms")
        return blocks
    
    def _final_optimization_and_validation(self, blocks: List[StabilizedBlock]) -> List[StabilizedBlock]:
        """
        Finalna optymalizacja i walidacja bloków
        """
        optimized_blocks = []
        
        for block in blocks:
            # Walidacja timingu
            if block.display_start >= 0 and block.display_end > block.display_start:
                # Sprawdź czy wszystkie słowa mają rozsądny timing
                valid_words = []
                for word in block.words:
                    if word.start >= 0 and word.end > word.start and word.word.strip():
                        valid_words.append(word)
                
                if valid_words:
                    # Aktualizuj blok z walidowanymi słowami
                    optimized_block = StabilizedBlock(
                        block_id=block.block_id,
                        words=valid_words,
                        start_time=valid_words[0].start,
                        end_time=valid_words[-1].end,
                        display_start=block.display_start,
                        display_end=block.display_end,
                        speaker=block.speaker,
                        confidence=block.confidence
                    )
                    optimized_blocks.append(optimized_block)
        
        # Finalna walidacja nakładań między blokami
        for i in range(len(optimized_blocks) - 1):
            current_block = optimized_blocks[i]
            next_block = optimized_blocks[i + 1]
            
            # Upewnij się, że nakładanie nie jest za duże
            if current_block.display_end > next_block.display_start + self.block_overlap:
                current_block.display_end = next_block.display_start + self.block_overlap
        
        logger.info(f"✅ Finalna walidacja: {len(optimized_blocks)} bloków gotowych")
        return optimized_blocks
    
    def _estimate_words_from_segments(self, segments: List[Dict[str, Any]]) -> List[WordTiming]:
        """
        Fallback: oszacuj słowa z segmentów gdy brak word-level timestamps
        """
        words = []
        word_index = 0
        
        for segment in segments:
            text = segment.get('text', '').strip()
            start_time = float(segment.get('start', 0.0))
            end_time = float(segment.get('end', 0.0))
            confidence = float(segment.get('confidence', 0.8))
            speaker = segment.get('speaker', 'A')
            
            # Podziel tekst na słowa
            segment_words = re.findall(r'\b\w+\b', text)
            
            if not segment_words:
                continue
            
            # Rozłóż czas równomiernie
            segment_duration = end_time - start_time
            time_per_word = segment_duration / len(segment_words)
            
            for i, word_text in enumerate(segment_words):
                word_start = start_time + (i * time_per_word)
                word_end = word_start + time_per_word
                
                word = WordTiming(
                    word=word_text,
                    start=word_start,
                    end=word_end,
                    confidence=confidence,
                    speaker=speaker,
                    word_index=word_index,
                    duration=time_per_word,
                    is_punctuated=any(p in word_text for p in '.,!?;:'),
                    is_estimated=True
                )
                
                words.append(word)
                word_index += 1
        
        logger.info(f"📝 Oszacowano {len(words)} słów z {len(segments)} segmentów")
        return words
    
    def generate_stabilized_srt(self, blocks: List[StabilizedBlock]) -> str:
        """
        Generuj SRT z stabilizowanych bloków
        """
        srt_content = []
        subtitle_index = 1
        
        for block in blocks:
            # Każdy blok jako jeden napis
            srt_content.append(str(subtitle_index))
            
            start_time = self._format_srt_timestamp(block.display_start)
            end_time = self._format_srt_timestamp(block.display_end)
            
            srt_content.append(f"{start_time} --> {end_time}")
            
            # Tekst bloku z informacją o mówiącym
            words_text = " ".join([w.word for w in block.words])
            if len(set([w.speaker for w in block.words])) > 1:
                # Wiele mówiących w bloku - dodaj oznaczenia
                speaker_text = f"[{block.speaker}] {words_text}"
            else:
                speaker_text = words_text
            
            srt_content.append(speaker_text)
            srt_content.append("")  # Pusta linia
            
            subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def _format_srt_timestamp(self, seconds: float) -> str:
        """Formatuj timestamp dla SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"