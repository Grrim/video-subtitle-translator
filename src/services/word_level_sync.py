"""
Synchronizacja na poziomie słów
Wyświetla słowa stopniowo, jak dochodzą do zdania, zamiast całych segmentów
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import re

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class WordTiming:
    """Timing pojedynczego słowa z word-level precision"""
    word: str
    start: float
    end: float
    confidence: float
    speaker: str = "A"
    
    # Dodatkowe pola dla word-level timestamps
    word_index: int = 0
    duration: float = 0.0
    is_punctuated: bool = False
    is_estimated: bool = False  # Czy timestamp jest oszacowany czy prawdziwy

@dataclass
class WordLevelSegment:
    """Segment z podziałem na słowa"""
    sentence_id: int
    words: List[WordTiming]
    sentence_start: float
    sentence_end: float
    complete_text: str

class WordLevelSynchronizer:
    """Synchronizator na poziomie słów"""
    
    def __init__(self):
        self.min_word_duration = 0.1  # Minimalna długość słowa (100ms)
        self.max_word_duration = 2.0  # Maksymalna długość słowa (2s)
        self.word_gap = 0.05  # Przerwa między słowami (50ms)
        self.max_words_on_screen = 8  # Maksymalna liczba słów na ekranie
        self.max_chars_per_line = 50  # Maksymalna liczba znaków w linii
        
    def create_word_level_subtitles(self, 
                                  transcript_data: Dict[str, Any],
                                  translated_text: str) -> List[WordLevelSegment]:
        """
        Stwórz napisy na poziomie słów
        
        Args:
            transcript_data: Dane transkrypcji z AssemblyAI
            translated_text: Przetłumaczony tekst
            
        Returns:
            Lista segmentów z podziałem na słowa
        """
        try:
            logger.info("Tworzenie napisów na poziomie słów...")
            
            # Pobierz słowa z transkrypcji
            word_timings = self._extract_word_timings(transcript_data)
            
            if not word_timings:
                logger.warning("Brak danych o słowach, używam segmentów")
                return self._fallback_to_segments(transcript_data, translated_text)
            
            # Podziel przetłumaczony tekst na zdania
            translated_sentences = self._split_into_sentences(translated_text)
            
            # Dopasuj słowa do przetłumaczonych zdań
            word_segments = self._align_words_with_translation(
                word_timings, translated_sentences
            )
            
            # Optymalizuj timing słów
            optimized_segments = self._optimize_word_timing(word_segments)
            
            logger.info(f"Utworzono {len(optimized_segments)} segmentów na poziomie słów")
            return optimized_segments
            
        except Exception as e:
            logger.error(f"Błąd tworzenia napisów na poziomie słów: {e}")
            return self._fallback_to_segments(transcript_data, translated_text)
    
    def _extract_word_timings(self, transcript_data: Dict[str, Any]) -> List[WordTiming]:
        """
        Wyciągnij PRECYZYJNE word-level timestamps z AssemblyAI
        
        Args:
            transcript_data: Dane transkrypcji z word-level timestamps
            
        Returns:
            Lista precyzyjnych timingów słów
        """
        word_timings = []
        
        # PRIORYTET: Użyj word-level timestamps z AssemblyAI
        if 'words' in transcript_data and transcript_data['words']:
            logger.info(f"🎯 Używam {len(transcript_data['words'])} precyzyjnych word-level timestamps z AssemblyAI")
            
            for word_data in transcript_data['words']:
                # Sprawdź czy to prawdziwe word-level timestamps czy oszacowane
                is_estimated = word_data.get('estimated', False)
                
                word_timing = WordTiming(
                    word=word_data.get('text', ''),
                    start=word_data.get('start', 0.0),
                    end=word_data.get('end', 0.0),
                    confidence=word_data.get('confidence', 0.8),
                    speaker=word_data.get('speaker', 'A')
                )
                
                # Dodaj dodatkowe informacje z word-level
                word_timing.word_index = word_data.get('word_index', 0)
                word_timing.duration = word_data.get('duration', 0.1)
                word_timing.is_punctuated = word_data.get('is_punctuated', False)
                word_timing.is_estimated = is_estimated
                
                word_timings.append(word_timing)
            
            # Waliduj i popraw word-level timestamps
            word_timings = self._optimize_word_level_timestamps(word_timings)
            
            # Sprawdź jakość
            quality_score = self._assess_word_timing_quality(word_timings)
            logger.info(f"✅ Jakość word-level timestamps: {quality_score:.1%}")
            
        # FALLBACK: Jeśli nie ma word-level, stwórz z segmentów
        elif 'segments' in transcript_data and transcript_data['segments']:
            logger.warning("⚠️ Brak word-level timestamps - tworzę oszacowania z segmentów")
            word_timings = self._estimate_word_timings_from_segments(transcript_data['segments'])
        
        else:
            logger.error("❌ Brak danych o słowach i segmentach")
        
        return word_timings
    
    def _optimize_word_level_timestamps(self, word_timings: List[WordTiming]) -> List[WordTiming]:
        """
        Optymalizuj word-level timestamps dla lepszej jakości
        
        Args:
            word_timings: Lista word timings
            
        Returns:
            Zoptymalizowane word timings
        """
        if not word_timings:
            return word_timings
        
        optimized = []
        
        for i, word_timing in enumerate(word_timings):
            optimized_timing = word_timing
            
            # 1. Napraw bardzo krótkie słowa (< 50ms)
            if word_timing.duration < 0.05:
                new_duration = max(0.1, len(word_timing.word) * 0.08)  # ~80ms na znak
                optimized_timing.end = optimized_timing.start + new_duration
                optimized_timing.duration = new_duration
            
            # 2. Napraw bardzo długie słowa (> 2s)
            elif word_timing.duration > 2.0:
                new_duration = min(2.0, len(word_timing.word) * 0.15)  # ~150ms na znak
                optimized_timing.end = optimized_timing.start + new_duration
                optimized_timing.duration = new_duration
            
            # 3. Napraw nakładające się słowa
            if i > 0:
                prev_timing = optimized[-1]
                if optimized_timing.start < prev_timing.end:
                    # Przesuń start lub skróć poprzednie słowo
                    gap = 0.02  # 20ms przerwy
                    optimized_timing.start = prev_timing.end + gap
                    
                    # Upewnij się, że słowo ma minimalną długość
                    min_duration = 0.08
                    if optimized_timing.end - optimized_timing.start < min_duration:
                        optimized_timing.end = optimized_timing.start + min_duration
                    
                    optimized_timing.duration = optimized_timing.end - optimized_timing.start
            
            optimized.append(optimized_timing)
        
        logger.info(f"🔧 Zoptymalizowano {len(optimized)} word-level timestamps")
        return optimized
    
    def _assess_word_timing_quality(self, word_timings: List[WordTiming]) -> float:
        """
        Oceń jakość word-level timestamps
        
        Args:
            word_timings: Lista word timings
            
        Returns:
            Wynik jakości (0.0 - 1.0)
        """
        if not word_timings:
            return 0.0
        
        quality_factors = []
        
        # 1. Sprawdź czy są to prawdziwe word-level timestamps
        estimated_count = sum(1 for wt in word_timings if getattr(wt, 'is_estimated', False))
        real_word_level_ratio = 1.0 - (estimated_count / len(word_timings))
        quality_factors.append(real_word_level_ratio)
        
        # 2. Sprawdź rozsądne długości słów
        reasonable_durations = 0
        for wt in word_timings:
            if 0.05 <= wt.duration <= 1.5:  # 50ms - 1.5s
                reasonable_durations += 1
        
        duration_quality = reasonable_durations / len(word_timings)
        quality_factors.append(duration_quality)
        
        # 3. Sprawdź brak nakładań
        overlaps = 0
        for i in range(len(word_timings) - 1):
            if word_timings[i].end > word_timings[i + 1].start:
                overlaps += 1
        
        no_overlap_quality = 1.0 - (overlaps / max(1, len(word_timings) - 1))
        quality_factors.append(no_overlap_quality)
        
        # 4. Sprawdź średnią pewność
        avg_confidence = sum(wt.confidence for wt in word_timings) / len(word_timings)
        quality_factors.append(avg_confidence)
        
        # Średnia ważona
        overall_quality = sum(quality_factors) / len(quality_factors)
        return overall_quality
    
    def _estimate_word_timings_from_segments(self, segments: List[Dict[str, Any]]) -> List[WordTiming]:
        """
        Oszacuj timing słów na podstawie segmentów
        
        Args:
            segments: Segmenty transkrypcji
            
        Returns:
            Lista oszacowanych timingów słów
        """
        word_timings = []
        
        for segment in segments:
            text = segment.get('text', '')
            start_time = segment.get('start', 0.0)
            end_time = segment.get('end', 0.0)
            confidence = segment.get('confidence', 0.8)
            speaker = segment.get('speaker', 'A')
            
            # Podziel tekst na słowa
            words = self._tokenize_words(text)
            
            if not words:
                continue
            
            # Rozłóż czas równomiernie między słowa
            segment_duration = end_time - start_time
            time_per_word = segment_duration / len(words)
            
            for i, word in enumerate(words):
                word_start = start_time + (i * time_per_word)
                word_end = word_start + time_per_word
                
                # Dodaj małe przerwy między słowami
                if i > 0:
                    word_start += self.word_gap
                if i < len(words) - 1:
                    word_end -= self.word_gap
                
                word_timing = WordTiming(
                    word=word,
                    start=word_start,
                    end=word_end,
                    confidence=confidence,
                    speaker=speaker
                )
                word_timings.append(word_timing)
        
        return word_timings
    
    def _tokenize_words(self, text: str) -> List[str]:
        """
        Podziel tekst na słowa
        
        Args:
            text: Tekst do podziału
            
        Returns:
            Lista słów
        """
        # Usuń znaki interpunkcyjne i podziel na słowa
        words = re.findall(r'\b\w+\b', text.lower())
        return [word for word in words if len(word) > 0]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Podziel tekst na zdania
        
        Args:
            text: Tekst do podziału
            
        Returns:
            Lista zdań
        """
        # Podziel na zdania używając znaków interpunkcyjnych
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def _align_words_with_translation(self, 
                                    word_timings: List[WordTiming],
                                    translated_sentences: List[str]) -> List[WordLevelSegment]:
        """
        Dopasuj słowa do przetłumaczonych zdań
        
        Args:
            word_timings: Timing słów oryginalnych
            translated_sentences: Przetłumaczone zdania
            
        Returns:
            Lista segmentów z dopasowanymi słowami
        """
        segments = []
        
        # Podziel słowa na grupy odpowiadające zdaniom
        words_per_sentence = len(word_timings) // len(translated_sentences) if translated_sentences else 1
        
        for i, sentence in enumerate(translated_sentences):
            # Określ zakres słów dla tego zdania
            start_word_idx = i * words_per_sentence
            end_word_idx = min((i + 1) * words_per_sentence, len(word_timings))
            
            # Ostatnie zdanie bierze wszystkie pozostałe słowa
            if i == len(translated_sentences) - 1:
                end_word_idx = len(word_timings)
            
            if start_word_idx >= len(word_timings):
                break
            
            # Pobierz słowa dla tego zdania
            sentence_word_timings = word_timings[start_word_idx:end_word_idx]
            
            if not sentence_word_timings:
                continue
            
            # Podziel przetłumaczone zdanie na słowa
            translated_words = self._tokenize_words(sentence)
            
            # Stwórz timing dla przetłumaczonych słów
            translated_word_timings = self._create_translated_word_timings(
                sentence_word_timings, translated_words
            )
            
            # Stwórz segment
            segment = WordLevelSegment(
                sentence_id=i,
                words=translated_word_timings,
                sentence_start=sentence_word_timings[0].start,
                sentence_end=sentence_word_timings[-1].end,
                complete_text=sentence.strip()
            )
            
            segments.append(segment)
        
        return segments
    
    def _create_translated_word_timings(self, 
                                      original_timings: List[WordTiming],
                                      translated_words: List[str]) -> List[WordTiming]:
        """
        Stwórz timing dla przetłumaczonych słów
        
        Args:
            original_timings: Oryginalne timings
            translated_words: Przetłumaczone słowa
            
        Returns:
            Lista timingów dla przetłumaczonych słów
        """
        if not original_timings or not translated_words:
            return []
        
        # Oblicz całkowity czas dla zdania
        total_start = original_timings[0].start
        total_end = original_timings[-1].end
        total_duration = total_end - total_start
        
        # Rozłóż czas między przetłumaczone słowa
        time_per_word = total_duration / len(translated_words)
        
        translated_timings = []
        
        for i, word in enumerate(translated_words):
            word_start = total_start + (i * time_per_word)
            word_end = word_start + time_per_word
            
            # Dodaj przerwy między słowami
            if i > 0:
                word_start += self.word_gap
            if i < len(translated_words) - 1:
                word_end -= self.word_gap
            
            # Użyj średniej pewności z oryginalnych słów
            avg_confidence = np.mean([wt.confidence for wt in original_timings])
            avg_speaker = original_timings[0].speaker  # Użyj pierwszego mówiącego
            
            word_timing = WordTiming(
                word=word,
                start=word_start,
                end=word_end,
                confidence=avg_confidence,
                speaker=avg_speaker
            )
            
            translated_timings.append(word_timing)
        
        return translated_timings
    
    def _optimize_word_timing(self, segments: List[WordLevelSegment]) -> List[WordLevelSegment]:
        """
        Optymalizuj timing słów
        
        Args:
            segments: Segmenty do optymalizacji
            
        Returns:
            Zoptymalizowane segmenty
        """
        optimized_segments = []
        
        for segment in segments:
            optimized_words = []
            
            for word_timing in segment.words:
                optimized_word = self._optimize_single_word_timing(word_timing)
                optimized_words.append(optimized_word)
            
            # Upewnij się, że słowa się nie nakładają
            optimized_words = self._fix_word_overlaps(optimized_words)
            
            # Zaktualizuj segment
            if optimized_words:
                optimized_segment = WordLevelSegment(
                    sentence_id=segment.sentence_id,
                    words=optimized_words,
                    sentence_start=optimized_words[0].start,
                    sentence_end=optimized_words[-1].end,
                    complete_text=segment.complete_text
                )
                optimized_segments.append(optimized_segment)
        
        return optimized_segments
    
    def _optimize_single_word_timing(self, word_timing: WordTiming) -> WordTiming:
        """
        Optymalizuj timing pojedynczego słowa
        
        Args:
            word_timing: Timing słowa do optymalizacji
            
        Returns:
            Zoptymalizowany timing
        """
        duration = word_timing.end - word_timing.start
        
        # Sprawdź czy długość słowa jest rozsądna
        if duration < self.min_word_duration:
            # Słowo za krótkie - wydłuż
            new_end = word_timing.start + self.min_word_duration
            return WordTiming(
                word=word_timing.word,
                start=word_timing.start,
                end=new_end,
                confidence=word_timing.confidence,
                speaker=word_timing.speaker
            )
        elif duration > self.max_word_duration:
            # Słowo za długie - skróć
            new_end = word_timing.start + self.max_word_duration
            return WordTiming(
                word=word_timing.word,
                start=word_timing.start,
                end=new_end,
                confidence=word_timing.confidence,
                speaker=word_timing.speaker
            )
        
        return word_timing
    
    def _fix_word_overlaps(self, word_timings: List[WordTiming]) -> List[WordTiming]:
        """
        Napraw nakładające się słowa
        
        Args:
            word_timings: Lista timingów słów
            
        Returns:
            Lista bez nakładań
        """
        if len(word_timings) <= 1:
            return word_timings
        
        fixed_timings = []
        
        for i, word_timing in enumerate(word_timings):
            fixed_timing = WordTiming(
                word=word_timing.word,
                start=word_timing.start,
                end=word_timing.end,
                confidence=word_timing.confidence,
                speaker=word_timing.speaker
            )
            
            # Sprawdź nakładanie z poprzednim słowem
            if i > 0:
                prev_timing = fixed_timings[-1]
                if fixed_timing.start < prev_timing.end:
                    # Nakładanie wykryte - dostosuj
                    fixed_timing = WordTiming(
                        word=fixed_timing.word,
                        start=prev_timing.end + self.word_gap,
                        end=max(prev_timing.end + self.word_gap + self.min_word_duration, fixed_timing.end),
                        confidence=fixed_timing.confidence,
                        speaker=fixed_timing.speaker
                    )
            
            fixed_timings.append(fixed_timing)
        
        return fixed_timings
    
    def _fallback_to_segments(self, 
                            transcript_data: Dict[str, Any],
                            translated_text: str) -> List[WordLevelSegment]:
        """
        Fallback do segmentów gdy nie ma danych o słowach
        
        Args:
            transcript_data: Dane transkrypcji
            translated_text: Przetłumaczony tekst
            
        Returns:
            Lista segmentów (bez podziału na słowa)
        """
        logger.warning("Używam fallback do segmentów - brak danych o słowach")
        
        segments = transcript_data.get('segments', [])
        translated_sentences = self._split_into_sentences(translated_text)
        
        fallback_segments = []
        
        for i, (segment, sentence) in enumerate(zip(segments, translated_sentences)):
            # Stwórz jeden "słowo" dla całego segmentu
            word_timing = WordTiming(
                word=sentence.strip(),
                start=segment.get('start', 0.0),
                end=segment.get('end', 0.0),
                confidence=segment.get('confidence', 0.8),
                speaker=segment.get('speaker', 'A')
            )
            
            fallback_segment = WordLevelSegment(
                sentence_id=i,
                words=[word_timing],
                sentence_start=word_timing.start,
                sentence_end=word_timing.end,
                complete_text=sentence.strip()
            )
            
            fallback_segments.append(fallback_segment)
        
        return fallback_segments
    
    def generate_word_level_srt(self, word_segments: List[WordLevelSegment]) -> str:
        """
        Generuj SRT z napisami na poziomie słów
        
        Args:
            word_segments: Segmenty z podziałem na słowa
            
        Returns:
            Zawartość pliku SRT
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            # Opcja 1: Każde słowo jako osobny napis
            for word_timing in segment.words:
                srt_content.append(str(subtitle_index))
                
                start_time = self._format_srt_timestamp(word_timing.start)
                end_time = self._format_srt_timestamp(word_timing.end)
                
                srt_content.append(f"{start_time} --> {end_time}")
                srt_content.append(word_timing.word)
                srt_content.append("")  # Pusta linia
                
                subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def generate_progressive_srt(self, word_segments: List[WordLevelSegment]) -> str:
        """
        Generuj SRT jak na YouTube - słowa pojawiają się i zostają do końca wypowiedzi mówiącego
        z limitem maksymalnej liczby słów na ekranie
        
        Args:
            word_segments: Segmenty z podziałem na słowa
            
        Returns:
            Zawartość pliku SRT w stylu YouTube z inteligentnym zarządzaniem słowami
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            current_speaker = segment.words[0].speaker if segment.words else "A"
            
            # Dla każdego słowa w segmencie mówiącego
            for word_idx, word_timing in enumerate(segment.words):
                # Określ zakres słów do wyświetlenia
                visible_words = self._get_visible_words_range(
                    segment.words, word_idx, current_speaker
                )
                
                # Stwórz tekst z widocznych słów
                display_text = " ".join([w.word for w in visible_words])
                
                # Sprawdź czy tekst nie jest za długi
                if len(display_text) > self.max_chars_per_line:
                    display_text = self._truncate_text_smartly(visible_words)
                
                srt_content.append(str(subtitle_index))
                
                start_time = self._format_srt_timestamp(word_timing.start)
                end_time = self._format_srt_timestamp(word_timing.end)
                
                srt_content.append(f"{start_time} --> {end_time}")
                srt_content.append(display_text)
                srt_content.append("")  # Pusta linia
                
                subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def _get_visible_words_range(self, 
                               all_words: List[WordTiming], 
                               current_word_idx: int,
                               current_speaker: str) -> List[WordTiming]:
        """
        Określ zakres słów do wyświetlenia na ekranie
        
        Args:
            all_words: Wszystkie słowa w segmencie
            current_word_idx: Indeks aktualnego słowa
            current_speaker: Aktualny mówiący
            
        Returns:
            Lista słów do wyświetlenia
        """
        # Wszystkie słowa do aktualnego (włącznie)
        words_so_far = all_words[:current_word_idx + 1]
        
        # Jeśli mieści się w limicie, pokaż wszystkie
        if len(words_so_far) <= self.max_words_on_screen:
            return words_so_far
        
        # Jeśli za dużo słów, pokaż ostatnie N słów (sliding window)
        start_idx = len(words_so_far) - self.max_words_on_screen
        return words_so_far[start_idx:]
    
    def _truncate_text_smartly(self, words: List[WordTiming]) -> str:
        """
        Inteligentnie skróć tekst zachowując najważniejsze słowa
        
        Args:
            words: Lista słów do skrócenia
            
        Returns:
            Skrócony tekst
        """
        if not words:
            return ""
        
        # Zaczynaj od końca (najnowsze słowa) i dodawaj w kierunku początku
        result_words = []
        current_length = 0
        
        for word in reversed(words):
            word_length = len(word.word) + 1  # +1 dla spacji
            if current_length + word_length <= self.max_chars_per_line:
                result_words.insert(0, word.word)
                current_length += word_length
            else:
                break
        
        # Jeśli skróciliśmy, dodaj "..." na początku
        if len(result_words) < len(words):
            text = "..." + " ".join(result_words)
        else:
            text = " ".join(result_words)
        
        return text
    
    def generate_youtube_style_srt(self, word_segments: List[WordLevelSegment]) -> str:
        """
        Generuj SRT w stylu YouTube z podświetlaniem aktualnego słowa
        
        Args:
            word_segments: Segmenty z podziałem na słowa
            
        Returns:
            Zawartość pliku SRT w stylu YouTube z podświetlaniem
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            # Dla każdego słowa w zdaniu
            for current_word_idx, current_word in enumerate(segment.words):
                srt_content.append(str(subtitle_index))
                
                start_time = self._format_srt_timestamp(current_word.start)
                end_time = self._format_srt_timestamp(current_word.end)
                
                srt_content.append(f"{start_time} --> {end_time}")
                
                # Zbuduj tekst z podświetleniem aktualnego słowa
                text_parts = []
                for i, word in enumerate(segment.words):
                    if i < current_word_idx:
                        # Słowa już wypowiedziane - normalny tekst
                        text_parts.append(word.word)
                    elif i == current_word_idx:
                        # Aktualne słowo - podświetlone (pogrubione)
                        text_parts.append(f"<b>{word.word}</b>")
                    else:
                        # Słowa jeszcze nie wypowiedziane - można je pokazać jako szare
                        text_parts.append(f"<font color='gray'>{word.word}</font>")
                
                full_text = " ".join(text_parts)
                srt_content.append(full_text)
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