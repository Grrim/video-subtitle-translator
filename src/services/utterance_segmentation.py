"""
Segmentacja na utterances (wypowiedzi/frazy) z automatycznym wykrywaniem pauz
Wykorzystuje naturalne przerwy w mowie do tworzenia lepszych napisów
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import statistics

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class UtteranceSegment:
    """Segment wypowiedzi z automatycznym wykrywaniem pauz"""
    text: str
    start: float
    end: float
    confidence: float
    speaker: str
    words: List[Dict]
    pause_before: float = 0.0  # Długość pauzy przed tym segmentem
    pause_after: float = 0.0   # Długość pauzy po tym segmencie
    is_natural_break: bool = True  # Czy to naturalna przerwa w mowie
    segment_id: int = 0

@dataclass
class PauseInfo:
    """Informacje o pauzie między segmentami"""
    start_time: float
    end_time: float
    duration: float
    confidence: float  # Pewność że to rzeczywiście pauza

class UtteranceSegmentator:
    """Segmentator na utterances z wykrywaniem pauz"""
    
    def __init__(self):
        self.min_pause_duration = 0.3  # Minimalna długość pauzy (300ms)
        self.max_pause_duration = 5.0  # Maksymalna długość pauzy (5s)
        self.natural_break_threshold = 0.5  # Próg dla naturalnych przerw (500ms)
        self.sentence_end_bonus = 0.2  # Bonus dla przerw po końcu zdania
        
    def segment_by_utterances(self, transcript_data: Dict[str, Any]) -> List[UtteranceSegment]:
        """
        Podziel transkrypcję na utterances na podstawie naturalnych pauz
        
        Args:
            transcript_data: Dane transkrypcji z AssemblyAI
            
        Returns:
            Lista segmentów utterances
        """
        try:
            logger.info("🎯 Segmentacja na utterances z wykrywaniem pauz...")
            
            # Sprawdź czy mamy utterances z AssemblyAI
            if 'utterances' in transcript_data and transcript_data['utterances']:
                utterances = self._process_assemblyai_utterances(transcript_data['utterances'])
                logger.info(f"✅ Użyto {len(utterances)} utterances z AssemblyAI")
            else:
                # Stwórz utterances z segmentów i słów
                utterances = self._create_utterances_from_segments(transcript_data)
                logger.info(f"🔧 Utworzono {len(utterances)} utterances z segmentów")
            
            # Analizuj pauzy między utterances
            utterances_with_pauses = self._analyze_pauses(utterances)
            
            # Optymalizuj segmentację
            optimized_utterances = self._optimize_utterance_segmentation(utterances_with_pauses)
            
            # Waliduj jakość segmentacji
            quality_score = self._assess_segmentation_quality(optimized_utterances)
            logger.info(f"📊 Jakość segmentacji utterances: {quality_score:.1%}")
            
            return optimized_utterances
            
        except Exception as e:
            logger.error(f"Błąd segmentacji utterances: {e}")
            return self._fallback_segmentation(transcript_data)
    
    def _process_assemblyai_utterances(self, utterances_data: List[Dict]) -> List[UtteranceSegment]:
        """
        Przetwórz utterances z AssemblyAI
        
        Args:
            utterances_data: Dane utterances z AssemblyAI
            
        Returns:
            Lista przetworzonych utterances
        """
        utterances = []
        
        for i, utterance in enumerate(utterances_data):
            # Konwertuj z milisekund na sekundy
            start_seconds = utterance.get('start', 0) / 1000.0
            end_seconds = utterance.get('end', 0) / 1000.0
            
            # Wyciągnij słowa dla tego utterance
            words = self._extract_words_for_utterance(utterance)
            
            utterance_segment = UtteranceSegment(
                text=utterance.get('text', ''),
                start=start_seconds,
                end=end_seconds,
                confidence=utterance.get('confidence', 0.8),
                speaker=utterance.get('speaker', 'A'),
                words=words,
                segment_id=i,
                is_natural_break=True  # AssemblyAI już wykrył naturalne przerwy
            )
            
            utterances.append(utterance_segment)
        
        return utterances
    
    def _extract_words_for_utterance(self, utterance: Dict) -> List[Dict]:
        """
        Wyciągnij słowa dla utterance
        
        Args:
            utterance: Dane utterance
            
        Returns:
            Lista słów w utterance
        """
        words = []
        
        if 'words' in utterance and utterance['words']:
            for word in utterance['words']:
                word_data = {
                    'text': word.get('text', ''),
                    'start': word.get('start', 0) / 1000.0,
                    'end': word.get('end', 0) / 1000.0,
                    'confidence': word.get('confidence', 0.8)
                }
                words.append(word_data)
        
        return words
    
    def _create_utterances_from_segments(self, transcript_data: Dict[str, Any]) -> List[UtteranceSegment]:
        """
        Stwórz utterances z segmentów gdy brak danych utterances
        
        Args:
            transcript_data: Dane transkrypcji
            
        Returns:
            Lista utterances
        """
        utterances = []
        segments = transcript_data.get('segments', [])
        
        if not segments:
            return utterances
        
        # Analizuj przerwy między segmentami
        for i, segment in enumerate(segments):
            start_seconds = segment.get('start', 0)
            end_seconds = segment.get('end', 0)
            
            # Sprawdź czy to naturalny podział
            is_natural = self._is_natural_utterance_break(segment, segments, i)
            
            # Wyciągnij słowa dla segmentu
            words = self._extract_words_for_segment(segment, transcript_data.get('words', []))
            
            utterance = UtteranceSegment(
                text=segment.get('text', ''),
                start=start_seconds,
                end=end_seconds,
                confidence=segment.get('confidence', 0.8),
                speaker=segment.get('speaker', 'A'),
                words=words,
                segment_id=i,
                is_natural_break=is_natural
            )
            
            utterances.append(utterance)
        
        return utterances
    
    def _is_natural_utterance_break(self, segment: Dict, all_segments: List[Dict], index: int) -> bool:
        """
        Sprawdź czy segment reprezentuje naturalną przerwę w utterance
        
        Args:
            segment: Aktualny segment
            all_segments: Wszystkie segmenty
            index: Indeks aktualnego segmentu
            
        Returns:
            True jeśli to naturalna przerwa
        """
        # Sprawdź czy tekst kończy się znakiem interpunkcyjnym
        text = segment.get('text', '').strip()
        if text.endswith(('.', '!', '?', ';')):
            return True
        
        # Sprawdź przerwę do następnego segmentu
        if index < len(all_segments) - 1:
            current_end = segment.get('end', 0)
            next_start = all_segments[index + 1].get('start', 0)
            pause_duration = next_start - current_end
            
            if pause_duration >= self.natural_break_threshold:
                return True
        
        return False
    
    def _extract_words_for_segment(self, segment: Dict, all_words: List[Dict]) -> List[Dict]:
        """
        Wyciągnij słowa należące do segmentu
        
        Args:
            segment: Segment
            all_words: Wszystkie słowa z transkrypcji
            
        Returns:
            Lista słów w segmencie
        """
        if not all_words:
            return []
        
        segment_start = segment.get('start', 0)
        segment_end = segment.get('end', 0)
        
        segment_words = []
        
        for word in all_words:
            word_start = word.get('start', 0)
            word_end = word.get('end', 0)
            
            # Sprawdź czy słowo należy do segmentu (z tolerancją)
            if (word_start >= segment_start - 0.1 and 
                word_end <= segment_end + 0.1):
                segment_words.append(word)
        
        return segment_words
    
    def _analyze_pauses(self, utterances: List[UtteranceSegment]) -> List[UtteranceSegment]:
        """
        Analizuj pauzy między utterances
        
        Args:
            utterances: Lista utterances
            
        Returns:
            Utterances z informacjami o pauzach
        """
        if len(utterances) < 2:
            return utterances
        
        analyzed_utterances = []
        
        for i, utterance in enumerate(utterances):
            updated_utterance = utterance
            
            # Pauza przed utterance
            if i > 0:
                prev_end = utterances[i-1].end
                pause_before = utterance.start - prev_end
                updated_utterance.pause_before = max(0, pause_before)
            
            # Pauza po utterance
            if i < len(utterances) - 1:
                next_start = utterances[i+1].start
                pause_after = next_start - utterance.end
                updated_utterance.pause_after = max(0, pause_after)
            
            analyzed_utterances.append(updated_utterance)
        
        # Loguj statystyki pauz
        pauses = [u.pause_before for u in analyzed_utterances if u.pause_before > 0]
        if pauses:
            avg_pause = statistics.mean(pauses)
            max_pause = max(pauses)
            logger.info(f"📊 Pauzy: średnia {avg_pause:.2f}s, maksymalna {max_pause:.2f}s")
        
        return analyzed_utterances
    
    def _optimize_utterance_segmentation(self, utterances: List[UtteranceSegment]) -> List[UtteranceSegment]:
        """
        Optymalizuj segmentację utterances
        
        Args:
            utterances: Lista utterances
            
        Returns:
            Zoptymalizowane utterances
        """
        if not utterances:
            return utterances
        
        optimized = []
        
        for utterance in utterances:
            # Sprawdź czy utterance nie jest za krótkie
            duration = utterance.end - utterance.start
            
            if duration < 0.5 and optimized:
                # Połącz z poprzednim utterance jeśli za krótkie
                prev_utterance = optimized[-1]
                
                # Sprawdź czy można połączyć (ten sam mówiący, krótka pauza)
                if (prev_utterance.speaker == utterance.speaker and 
                    utterance.pause_before < 1.0):
                    
                    # Połącz utterances
                    combined_utterance = UtteranceSegment(
                        text=prev_utterance.text + " " + utterance.text,
                        start=prev_utterance.start,
                        end=utterance.end,
                        confidence=(prev_utterance.confidence + utterance.confidence) / 2,
                        speaker=prev_utterance.speaker,
                        words=prev_utterance.words + utterance.words,
                        pause_before=prev_utterance.pause_before,
                        pause_after=utterance.pause_after,
                        is_natural_break=utterance.is_natural_break,
                        segment_id=prev_utterance.segment_id
                    )
                    
                    optimized[-1] = combined_utterance
                    continue
            
            # Sprawdź czy utterance nie jest za długie
            if duration > 10.0:
                # Podziel długie utterance
                split_utterances = self._split_long_utterance(utterance)
                optimized.extend(split_utterances)
            else:
                optimized.append(utterance)
        
        logger.info(f"🔧 Optymalizacja: {len(utterances)} → {len(optimized)} utterances")
        return optimized
    
    def _split_long_utterance(self, utterance: UtteranceSegment) -> List[UtteranceSegment]:
        """
        Podziel długie utterance na mniejsze części
        
        Args:
            utterance: Długie utterance
            
        Returns:
            Lista mniejszych utterances
        """
        if not utterance.words:
            return [utterance]
        
        # Podziel na podstawie słów i naturalnych przerw
        target_duration = 5.0  # Docelowa długość utterance
        split_utterances = []
        
        current_words = []
        current_start = utterance.start
        
        for word in utterance.words:
            current_words.append(word)
            
            # Sprawdź czy osiągnęliśmy docelową długość
            if word['end'] - current_start >= target_duration:
                # Sprawdź czy to dobre miejsce na podział
                if self._is_good_split_point(word, utterance.words):
                    # Stwórz utterance z aktualnych słów
                    split_text = " ".join([w['text'] for w in current_words])
                    
                    split_utterance = UtteranceSegment(
                        text=split_text,
                        start=current_start,
                        end=word['end'],
                        confidence=utterance.confidence,
                        speaker=utterance.speaker,
                        words=current_words.copy(),
                        is_natural_break=False,  # Sztuczny podział
                        segment_id=utterance.segment_id
                    )
                    
                    split_utterances.append(split_utterance)
                    
                    # Reset dla następnej części
                    current_words = []
                    current_start = word['end']
        
        # Dodaj pozostałe słowa
        if current_words:
            split_text = " ".join([w['text'] for w in current_words])
            
            final_utterance = UtteranceSegment(
                text=split_text,
                start=current_start,
                end=utterance.end,
                confidence=utterance.confidence,
                speaker=utterance.speaker,
                words=current_words,
                is_natural_break=utterance.is_natural_break,
                segment_id=utterance.segment_id
            )
            
            split_utterances.append(final_utterance)
        
        return split_utterances if split_utterances else [utterance]
    
    def _is_good_split_point(self, word: Dict, all_words: List[Dict]) -> bool:
        """
        Sprawdź czy to dobre miejsce na podział utterance
        
        Args:
            word: Aktualne słowo
            all_words: Wszystkie słowa w utterance
            
        Returns:
            True jeśli to dobre miejsce na podział
        """
        word_text = word.get('text', '').lower()
        
        # Dobry punkt po znakach interpunkcyjnych
        if any(punct in word_text for punct in [',', ';', ':']):
            return True
        
        # Dobry punkt przed spójnikami
        word_index = next((i for i, w in enumerate(all_words) if w == word), -1)
        if word_index < len(all_words) - 1:
            next_word = all_words[word_index + 1]['text'].lower()
            if next_word in ['i', 'a', 'ale', 'oraz', 'lub', 'bo', 'że', 'gdy', 'jeśli']:
                return True
        
        return False
    
    def _assess_segmentation_quality(self, utterances: List[UtteranceSegment]) -> float:
        """
        Oceń jakość segmentacji utterances
        
        Args:
            utterances: Lista utterances
            
        Returns:
            Wynik jakości (0.0 - 1.0)
        """
        if not utterances:
            return 0.0
        
        quality_factors = []
        
        # 1. Sprawdź rozsądne długości utterances
        reasonable_durations = 0
        for utterance in utterances:
            duration = utterance.end - utterance.start
            if 1.0 <= duration <= 8.0:  # 1-8 sekund
                reasonable_durations += 1
        
        duration_quality = reasonable_durations / len(utterances)
        quality_factors.append(duration_quality)
        
        # 2. Sprawdź naturalne przerwy
        natural_breaks = sum(1 for u in utterances if u.is_natural_break)
        natural_quality = natural_breaks / len(utterances)
        quality_factors.append(natural_quality)
        
        # 3. Sprawdź rozsądne pauzy
        reasonable_pauses = 0
        for utterance in utterances:
            if utterance.pause_before <= 3.0:  # Maksymalnie 3s pauzy
                reasonable_pauses += 1
        
        pause_quality = reasonable_pauses / len(utterances)
        quality_factors.append(pause_quality)
        
        # 4. Sprawdź średnią pewność
        avg_confidence = sum(u.confidence for u in utterances) / len(utterances)
        quality_factors.append(avg_confidence)
        
        overall_quality = sum(quality_factors) / len(quality_factors)
        return overall_quality
    
    def _fallback_segmentation(self, transcript_data: Dict[str, Any]) -> List[UtteranceSegment]:
        """
        Fallback segmentacja w przypadku błędu
        
        Args:
            transcript_data: Dane transkrypcji
            
        Returns:
            Podstawowe utterances
        """
        logger.warning("Używam fallback segmentacji")
        
        segments = transcript_data.get('segments', [])
        utterances = []
        
        for i, segment in enumerate(segments):
            utterance = UtteranceSegment(
                text=segment.get('text', ''),
                start=segment.get('start', 0),
                end=segment.get('end', 0),
                confidence=segment.get('confidence', 0.8),
                speaker=segment.get('speaker', 'A'),
                words=[],
                segment_id=i,
                is_natural_break=True
            )
            utterances.append(utterance)
        
        return utterances
    
    def get_pause_statistics(self, utterances: List[UtteranceSegment]) -> Dict[str, Any]:
        """
        Pobierz statystyki pauz
        
        Args:
            utterances: Lista utterances
            
        Returns:
            Statystyki pauz
        """
        pauses = [u.pause_before for u in utterances if u.pause_before > 0]
        
        if not pauses:
            return {}
        
        return {
            'total_pauses': len(pauses),
            'average_pause': statistics.mean(pauses),
            'median_pause': statistics.median(pauses),
            'min_pause': min(pauses),
            'max_pause': max(pauses),
            'total_pause_time': sum(pauses),
            'pauses_over_1s': len([p for p in pauses if p > 1.0]),
            'pauses_over_2s': len([p for p in pauses if p > 2.0])
        }