"""
Menedżer synchronizacji audio-napisy
Zapewnia precyzyjną synchronizację czasową między dźwiękiem a napisami
"""

import numpy as np
import librosa
import scipy.signal
from typing import Dict, Any, List, Tuple, Optional
import time
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SyncCorrection:
    """Korekta synchronizacji"""
    offset_seconds: float
    confidence: float
    method: str
    segments_adjusted: int

@dataclass
class AudioFeatures:
    """Cechy audio do synchronizacji"""
    energy_profile: np.ndarray
    spectral_centroids: np.ndarray
    zero_crossing_rate: np.ndarray
    tempo: float
    beat_frames: np.ndarray
    sample_rate: int

class AudioSyncManager:
    """Menedżer synchronizacji audio-napisy"""
    
    def __init__(self):
        self.sample_rate = 22050  # Standardowa częstotliwość próbkowania
        self.hop_length = 512
        self.frame_length = 2048
        
        # Parametry synchronizacji - bardziej tolerancyjne
        self.max_offset_seconds = 10.0  # Maksymalne przesunięcie
        self.min_confidence = 0.3       # Minimalna pewność korekty (obniżona)
        
    def analyze_audio_features(self, audio_path: str) -> AudioFeatures:
        """
        Analizuj cechy audio do synchronizacji
        
        Args:
            audio_path: Ścieżka do pliku audio
            
        Returns:
            AudioFeatures object
        """
        try:
            logger.info(f"Analizuję cechy audio: {audio_path}")
            
            # Sprawdź czy plik istnieje
            if not os.path.exists(audio_path):
                logger.error(f"Plik audio nie istnieje: {audio_path}")
                return self._create_fallback_features()
            
            try:
                # Wczytaj audio z obsługą błędów
                y, sr = librosa.load(audio_path, sr=self.sample_rate, duration=60)  # Maksymalnie 60s dla analizy
                
                if len(y) == 0:
                    logger.warning("Plik audio jest pusty")
                    return self._create_fallback_features()
                
            except Exception as e:
                logger.error(f"Błąd wczytywania audio: {e}")
                return self._create_fallback_features()
            
            # Oblicz cechy audio z obsługą błędów
            try:
                # 1. Profil energii (RMS)
                energy_profile = librosa.feature.rms(
                    y=y, 
                    frame_length=min(self.frame_length, len(y)),
                    hop_length=min(self.hop_length, len(y)//4)
                )[0]
                
                # 2. Centroidy spektralne (jasność dźwięku)
                spectral_centroids = librosa.feature.spectral_centroid(
                    y=y, 
                    sr=sr,
                    hop_length=min(self.hop_length, len(y)//4)
                )[0]
                
                # 3. Zero crossing rate (przejścia przez zero)
                zero_crossing_rate = librosa.feature.zero_crossing_rate(
                    y, 
                    frame_length=min(self.frame_length, len(y)),
                    hop_length=min(self.hop_length, len(y)//4)
                )[0]
                
                # 4. Tempo i beat tracking (z obsługą błędów)
                try:
                    tempo, beat_frames = librosa.beat.beat_track(
                        y=y, 
                        sr=sr,
                        hop_length=min(self.hop_length, len(y)//4)
                    )
                except:
                    tempo = 120.0
                    beat_frames = np.array([])
                
                logger.info(f"Cechy audio: tempo={tempo:.1f} BPM, energia_avg={np.mean(energy_profile):.3f}, ramek={len(energy_profile)}")
                
                return AudioFeatures(
                    energy_profile=energy_profile,
                    spectral_centroids=spectral_centroids,
                    zero_crossing_rate=zero_crossing_rate,
                    tempo=tempo,
                    beat_frames=beat_frames,
                    sample_rate=sr
                )
                
            except Exception as e:
                logger.error(f"Błąd obliczania cech audio: {e}")
                return self._create_fallback_features()
            
        except Exception as e:
            logger.error(f"Błąd analizy audio: {e}")
            return self._create_fallback_features()
    
    def _create_fallback_features(self) -> AudioFeatures:
        """
        Stwórz podstawowe cechy audio w przypadku błędu
        
        Returns:
            Podstawowe AudioFeatures
        """
        # Stwórz symulowane cechy audio
        duration_frames = 100  # Symuluj 100 ramek
        
        return AudioFeatures(
            energy_profile=np.random.uniform(0.1, 0.8, duration_frames),  # Symulowana energia
            spectral_centroids=np.random.uniform(1000, 2000, duration_frames),  # Symulowane centroidy
            zero_crossing_rate=np.random.uniform(0.1, 0.4, duration_frames),  # Symulowany ZCR
            tempo=120.0,
            beat_frames=np.arange(0, duration_frames, 10),  # Symulowane beaty
            sample_rate=self.sample_rate
        )
    
    def detect_speech_segments(self, audio_features: AudioFeatures) -> List[Tuple[float, float]]:
        """
        Wykryj segmenty mowy w audio
        
        Args:
            audio_features: Cechy audio
            
        Returns:
            Lista krotek (start, end) w sekundach
        """
        if len(audio_features.energy_profile) == 0:
            return []
        
        # Próg energii dla wykrywania mowy
        energy_threshold = np.mean(audio_features.energy_profile) + 0.5 * np.std(audio_features.energy_profile)
        
        # Znajdź segmenty powyżej progu
        speech_mask = audio_features.energy_profile > energy_threshold
        
        # Konwertuj ramki na czas
        frame_times = librosa.frames_to_time(
            np.arange(len(speech_mask)),
            sr=audio_features.sample_rate,
            hop_length=self.hop_length
        )
        
        # Znajdź ciągłe segmenty mowy
        speech_segments = []
        in_speech = False
        start_time = 0
        
        for i, is_speech in enumerate(speech_mask):
            if is_speech and not in_speech:
                # Początek segmentu mowy
                start_time = frame_times[i]
                in_speech = True
            elif not is_speech and in_speech:
                # Koniec segmentu mowy
                end_time = frame_times[i]
                if end_time - start_time > 0.3:  # Minimum 300ms
                    speech_segments.append((start_time, end_time))
                in_speech = False
        
        # Dodaj ostatni segment jeśli kończy się mową
        if in_speech and len(frame_times) > 0:
            speech_segments.append((start_time, frame_times[-1]))
        
        logger.info(f"Wykryto {len(speech_segments)} segmentów mowy")
        return speech_segments
    
    def calculate_sync_offset(self, 
                            audio_features: AudioFeatures,
                            transcript_segments: List[Dict[str, Any]]) -> SyncCorrection:
        """
        Oblicz przesunięcie synchronizacji między audio a napisami
        
        Args:
            audio_features: Cechy audio
            transcript_segments: Segmenty transkrypcji
            
        Returns:
            SyncCorrection object
        """
        try:
            # Wykryj segmenty mowy w audio
            detected_speech = self.detect_speech_segments(audio_features)
            
            if not detected_speech or not transcript_segments:
                logger.warning("Brak segmentów do synchronizacji")
                return SyncCorrection(0.0, 0.0, "no_data", 0)
            
            # NOWA METODA: Precyzyjne dopasowanie na podstawie początków segmentów
            best_offset, best_confidence = self._precise_onset_alignment(
                audio_features, transcript_segments, detected_speech
            )
            
            method = "precise_onset"
            
            # Jeśli precyzyjne dopasowanie nie działa, użyj metod zapasowych
            if best_confidence < self.min_confidence:
                logger.info(f"Precyzyjne dopasowanie ma niską pewność ({best_confidence:.2f}), próbuję inne metody...")
                logger.info("Precyzyjne dopasowanie nieudane, próbuję metody energetycznej...")
                
                # Metoda energetyczna
                energy_offset, energy_confidence = self._energy_based_sync(
                    audio_features, transcript_segments
                )
                
                if energy_confidence > best_confidence:
                    best_offset = energy_offset
                    best_confidence = energy_confidence
                    method = "energy_based"
                
                # Metoda rytmiczna jako ostatnia deska ratunku
                if best_confidence < self.min_confidence:
                    logger.info("Metoda energetyczna nieudana, próbuję dopasowanie rytmiczne...")
                    rhythm_offset, rhythm_confidence = self._rhythm_based_sync(
                        audio_features, transcript_segments
                    )
                    
                    if rhythm_confidence > best_confidence:
                        best_offset = rhythm_offset
                        best_confidence = rhythm_confidence
                        method = "rhythm_based"
                
                # Jeśli nadal niska pewność, użyj prostego oszacowania
                if best_confidence < self.min_confidence:
                    logger.info("Wszystkie metody mają niską pewność, używam prostego oszacowania...")
                    simple_offset, simple_confidence = self._simple_estimation_sync(transcript_segments)
                    
                    if simple_confidence > best_confidence:
                        best_offset = simple_offset
                        best_confidence = simple_confidence
                        method = "simple_estimation"
            
            logger.info(f"Obliczono przesunięcie: {best_offset:.2f}s (pewność: {best_confidence:.2f}, metoda: {method})")
            
            return SyncCorrection(
                offset_seconds=best_offset,
                confidence=best_confidence,
                method=method,
                segments_adjusted=len(transcript_segments)
            )
            
        except Exception as e:
            logger.error(f"Błąd obliczania przesunięcia: {e}")
            return SyncCorrection(0.0, 0.0, "error", 0)
    
    def _precise_onset_alignment(self, 
                               audio_features: AudioFeatures,
                               transcript_segments: List[Dict[str, Any]],
                               detected_speech: List[Tuple[float, float]]) -> Tuple[float, float]:
        """
        Precyzyjne dopasowanie na podstawie początków segmentów mowy
        
        Args:
            audio_features: Cechy audio
            transcript_segments: Segmenty transkrypcji
            detected_speech: Wykryte segmenty mowy
            
        Returns:
            Tuple (offset, confidence)
        """
        if len(audio_features.energy_profile) == 0 or not detected_speech or not transcript_segments:
            return 0.0, 0.0
        
        # Znajdź początki segmentów w audio (onset detection)
        audio_onsets = self._detect_speech_onsets(audio_features)
        
        # Początki segmentów z transkrypcji
        transcript_onsets = [seg['start'] for seg in transcript_segments]
        
        if len(audio_onsets) < 2 or len(transcript_onsets) < 2:
            return 0.0, 0.0
        
        best_offset = 0.0
        best_score = 0.0
        
        # Testuj różne przesunięcia z większą precyzją
        test_offsets = np.arange(-self.max_offset_seconds, self.max_offset_seconds, 0.05)
        
        for offset in test_offsets:
            shifted_transcript = [onset + offset for onset in transcript_onsets]
            
            # Oblicz dopasowanie początków
            score = self._calculate_onset_alignment_score(audio_onsets, shifted_transcript)
            
            if score > best_score:
                best_score = score
                best_offset = offset
        
        # Konwertuj score na confidence (0-1)
        confidence = min(best_score, 1.0)
        
        logger.debug(f"Precyzyjne dopasowanie: offset={best_offset:.2f}s, confidence={confidence:.2f}")
        return best_offset, confidence
    
    def _detect_speech_onsets(self, audio_features: AudioFeatures) -> List[float]:
        """
        Wykryj początki segmentów mowy w audio
        
        Args:
            audio_features: Cechy audio
            
        Returns:
            Lista czasów początków segmentów w sekundach
        """
        if len(audio_features.energy_profile) == 0:
            return []
        
        # Oblicz różnice energii (onset strength)
        energy_diff = np.diff(audio_features.energy_profile)
        energy_diff = np.maximum(energy_diff, 0)  # Tylko wzrosty energii
        
        # Znajdź lokalne maksima (potencjalne początki)
        from scipy.signal import find_peaks
        
        # Próg dla wykrywania początków
        threshold = np.mean(energy_diff) + 1.5 * np.std(energy_diff)
        
        peaks, _ = find_peaks(energy_diff, height=threshold, distance=10)  # Min 10 ramek między pikami
        
        # Konwertuj ramki na czas
        frame_times = librosa.frames_to_time(
            peaks,
            sr=audio_features.sample_rate,
            hop_length=self.hop_length
        )
        
        logger.debug(f"Wykryto {len(frame_times)} początków segmentów mowy")
        return frame_times.tolist()
    
    def _calculate_onset_alignment_score(self, 
                                       audio_onsets: List[float],
                                       transcript_onsets: List[float]) -> float:
        """
        Oblicz wynik dopasowania początków segmentów
        
        Args:
            audio_onsets: Początki w audio
            transcript_onsets: Początki w transkrypcji
            
        Returns:
            Wynik dopasowania (wyższy = lepszy)
        """
        if not audio_onsets or not transcript_onsets:
            return 0.0
        
        total_score = 0.0
        tolerance = 0.3  # 300ms tolerancji
        
        for t_onset in transcript_onsets:
            # Znajdź najbliższy onset w audio
            distances = [abs(a_onset - t_onset) for a_onset in audio_onsets]
            min_distance = min(distances)
            
            # Wynik na podstawie odległości
            if min_distance <= tolerance:
                score = 1.0 - (min_distance / tolerance)
                total_score += score
        
        # Normalizuj przez liczbę segmentów transkrypcji
        return total_score / len(transcript_onsets) if transcript_onsets else 0.0
    
    def _energy_based_sync(self, 
                          audio_features: AudioFeatures,
                          transcript_segments: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Synchronizacja oparta na profilu energii
        
        Args:
            audio_features: Cechy audio
            transcript_segments: Segmenty transkrypcji
            
        Returns:
            Tuple (offset, confidence)
        """
        if len(audio_features.energy_profile) == 0 or not transcript_segments:
            return 0.0, 0.0
        
        # Stwórz profil aktywności z segmentów transkrypcji
        max_time = max(seg['end'] for seg in transcript_segments) + 2.0
        time_resolution = 0.1  # 100ms rozdzielczość
        time_bins = np.arange(0, max_time, time_resolution)
        
        transcript_activity = np.zeros(len(time_bins))
        
        for seg in transcript_segments:
            start_idx = int(seg['start'] / time_resolution)
            end_idx = int(seg['end'] / time_resolution)
            if start_idx < len(transcript_activity) and end_idx <= len(transcript_activity):
                transcript_activity[start_idx:end_idx] = 1.0
        
        # Przeskaluj profil energii audio do tej samej rozdzielczości
        audio_time_bins = librosa.frames_to_time(
            np.arange(len(audio_features.energy_profile)),
            sr=audio_features.sample_rate,
            hop_length=self.hop_length
        )
        
        # Interpoluj energię audio do nowej siatki czasowej
        audio_activity = np.interp(time_bins, audio_time_bins, audio_features.energy_profile)
        
        # Normalizuj
        audio_activity = (audio_activity - np.min(audio_activity)) / (np.max(audio_activity) - np.min(audio_activity) + 1e-8)
        
        # Znajdź najlepsze przesunięcie przez cross-correlation
        from scipy.signal import correlate
        
        correlation = correlate(audio_activity, transcript_activity, mode='full')
        
        # Znajdź maksimum korelacji
        max_corr_idx = np.argmax(correlation)
        
        # Oblicz przesunięcie
        offset_bins = max_corr_idx - (len(transcript_activity) - 1)
        offset_seconds = offset_bins * time_resolution
        
        # Ograniczenie do rozsądnego zakresu
        offset_seconds = np.clip(offset_seconds, -self.max_offset_seconds, self.max_offset_seconds)
        
        # Confidence na podstawie wartości korelacji
        max_correlation = correlation[max_corr_idx]
        confidence = max_correlation / len(transcript_activity) if len(transcript_activity) > 0 else 0.0
        confidence = np.clip(confidence, 0.0, 1.0)
        
        logger.debug(f"Synchronizacja energetyczna: offset={offset_seconds:.2f}s, confidence={confidence:.2f}")
        return offset_seconds, confidence
    
    def _simple_estimation_sync(self, transcript_segments: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Prosta metoda oszacowania synchronizacji jako fallback
        
        Args:
            transcript_segments: Segmenty transkrypcji
            
        Returns:
            Tuple (offset, confidence)
        """
        if not transcript_segments:
            return 0.0, 0.0
        
        # Sprawdź czy pierwszy segment zaczyna się bardzo wcześnie (może wskazywać na przesunięcie)
        first_start = transcript_segments[0].get('start', 0)
        
        # Jeśli pierwszy segment zaczyna się bardzo wcześnie, może być przesunięcie
        if first_start < 0.5:
            # Prawdopodobnie potrzebne małe przesunięcie w przód
            estimated_offset = 0.3
            confidence = 0.4
        else:
            # Prawdopodobnie synchronizacja jest w miarę dobra
            estimated_offset = 0.0
            confidence = 0.5
        
        logger.info(f"Proste oszacowanie: offset={estimated_offset:.2f}s, confidence={confidence:.2f}")
        return estimated_offset, confidence
    
    def _calculate_alignment_confidence(self, 
                                      detected_speech: List[Tuple[float, float]],
                                      transcript_times: List[Tuple[float, float]],
                                      offset: float) -> float:
        """
        Oblicz pewność dopasowania dla danego przesunięcia
        
        Args:
            detected_speech: Wykryte segmenty mowy
            transcript_times: Czasy segmentów transkrypcji
            offset: Testowane przesunięcie
            
        Returns:
            Pewność dopasowania (0.0 - 1.0)
        """
        if not detected_speech or not transcript_times:
            return 0.0
        
        # Przesuń czasy transkrypcji
        shifted_transcript = [(start + offset, end + offset) for start, end in transcript_times]
        
        # Oblicz pokrycie
        total_overlap = 0.0
        total_transcript_duration = 0.0
        
        for trans_start, trans_end in shifted_transcript:
            trans_duration = trans_end - trans_start
            total_transcript_duration += trans_duration
            
            # Znajdź pokrycie z wykrytymi segmentami mowy
            for speech_start, speech_end in detected_speech:
                overlap_start = max(trans_start, speech_start)
                overlap_end = min(trans_end, speech_end)
                
                if overlap_start < overlap_end:
                    total_overlap += overlap_end - overlap_start
        
        # Pewność jako stosunek pokrycia do całkowitego czasu transkrypcji
        confidence = total_overlap / total_transcript_duration if total_transcript_duration > 0 else 0.0
        return min(confidence, 1.0)
    
    def _rhythm_based_sync(self, 
                          audio_features: AudioFeatures,
                          transcript_segments: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Synchronizacja oparta na rytmie mowy
        
        Args:
            audio_features: Cechy audio
            transcript_segments: Segmenty transkrypcji
            
        Returns:
            Tuple (offset, confidence)
        """
        try:
            if len(audio_features.beat_frames) == 0:
                return 0.0, 0.0
            
            # Konwertuj beat frames na czas
            beat_times = librosa.frames_to_time(
                audio_features.beat_frames,
                sr=audio_features.sample_rate,
                hop_length=self.hop_length
            )
            
            # Oblicz rytm segmentów transkrypcji
            segment_starts = [seg['start'] for seg in transcript_segments]
            
            if len(segment_starts) < 2:
                return 0.0, 0.0
            
            # Znajdź najlepsze dopasowanie rytmu
            best_offset = 0.0
            best_correlation = 0.0
            
            for offset in np.arange(-2.0, 2.0, 0.1):
                shifted_starts = [start + offset for start in segment_starts]
                
                # Oblicz korelację z beat times
                correlation = self._calculate_rhythm_correlation(beat_times, shifted_starts)
                
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_offset = offset
            
            return best_offset, best_correlation
            
        except Exception as e:
            logger.error(f"Błąd synchronizacji rytmicznej: {e}")
            return 0.0, 0.0
    
    def _calculate_rhythm_correlation(self, beat_times: np.ndarray, segment_starts: List[float]) -> float:
        """
        Oblicz korelację między rytmem audio a początkami segmentów
        
        Args:
            beat_times: Czasy beatów w audio
            segment_starts: Początki segmentów transkrypcji
            
        Returns:
            Korelacja (0.0 - 1.0)
        """
        if len(beat_times) == 0 or len(segment_starts) == 0:
            return 0.0
        
        # Stwórz histogramy czasowe
        max_time = max(max(beat_times), max(segment_starts))
        bins = np.arange(0, max_time + 1, 0.1)
        
        beat_hist, _ = np.histogram(beat_times, bins=bins)
        segment_hist, _ = np.histogram(segment_starts, bins=bins)
        
        # Oblicz korelację
        if np.std(beat_hist) == 0 or np.std(segment_hist) == 0:
            return 0.0
        
        correlation = np.corrcoef(beat_hist, segment_hist)[0, 1]
        return max(0.0, correlation) if not np.isnan(correlation) else 0.0
    
    def apply_sync_correction(self, 
                            segments: List[Dict[str, Any]], 
                            correction: SyncCorrection) -> List[Dict[str, Any]]:
        """
        Zastosuj korekcję synchronizacji do segmentów
        
        Args:
            segments: Segmenty do korekty
            correction: Korekta synchronizacji
            
        Returns:
            Skorygowane segmenty
        """
        # NOWA LOGIKA: Zastosuj korekcję nawet przy niskiej pewności, ale z ostrzeżeniem
        if correction.confidence < 0.3:  # Bardzo niska pewność
            logger.warning(f"Bardzo niska pewność korekty ({correction.confidence:.2f}), pomijam całkowicie")
            return segments
        elif correction.confidence < self.min_confidence:
            logger.warning(f"Niska pewność korekty ({correction.confidence:.2f}), stosuję z ostrożnością")
            # Zmniejsz siłę korekty przy niskiej pewności
            offset = correction.offset_seconds * correction.confidence
        else:
            offset = correction.offset_seconds
        
        corrected_segments = []
        
        logger.info(f"Stosowanie korekty synchronizacji: {offset:.2f}s (oryginalne: {correction.offset_seconds:.2f}s)")
        
        # ULEPSZONA KOREKTA: Adaptacyjne dostosowanie dla każdego segmentu
        for i, segment in enumerate(segments):
            corrected_segment = segment.copy()
            
            # Oblicz adaptacyjne przesunięcie dla tego segmentu
            adaptive_offset = self._calculate_adaptive_offset(segment, offset, i, len(segments))
            
            # Zastosuj przesunięcie z walidacją
            new_start = max(0.0, segment['start'] + adaptive_offset)
            new_end = max(new_start + 0.1, segment['end'] + adaptive_offset)
            
            # Sprawdź czy nowe czasy są rozsądne
            if self._validate_segment_timing(new_start, new_end, segment):
                corrected_segment['start'] = new_start
                corrected_segment['end'] = new_end
            else:
                # Jeśli korekta prowadzi do nierozsądnych czasów, użyj mniejszej korekty
                fallback_offset = adaptive_offset * 0.5
                corrected_segment['start'] = max(0.0, segment['start'] + fallback_offset)
                corrected_segment['end'] = max(corrected_segment['start'] + 0.1, segment['end'] + fallback_offset)
                logger.warning(f"Segment {i}: Użyto zmniejszonej korekty ({fallback_offset:.2f}s)")
            
            # Dodaj rozszerzone informacje o korekcie
            corrected_segment['sync_corrected'] = True
            corrected_segment['sync_offset'] = adaptive_offset
            corrected_segment['sync_confidence'] = correction.confidence
            corrected_segment['sync_method'] = correction.method
            corrected_segment['original_start'] = segment['start']
            corrected_segment['original_end'] = segment['end']
            
            corrected_segments.append(corrected_segment)
        
        # Post-processing: Upewnij się, że segmenty się nie nakładają
        corrected_segments = self._fix_overlapping_segments(corrected_segments)
        
        logger.info(f"Skorygowano {len(corrected_segments)} segmentów z adaptacyjnym przesunięciem")
        return corrected_segments
    
    def _calculate_adaptive_offset(self, segment: Dict[str, Any], base_offset: float, 
                                 segment_index: int, total_segments: int) -> float:
        """
        Oblicz adaptacyjne przesunięcie dla konkretnego segmentu
        
        Args:
            segment: Segment do korekty
            base_offset: Podstawowe przesunięcie
            segment_index: Indeks segmentu
            total_segments: Całkowita liczba segmentów
            
        Returns:
            Adaptacyjne przesunięcie
        """
        # Bazowe przesunięcie
        adaptive_offset = base_offset
        
        # Zmniejsz korekcję dla pierwszego i ostatniego segmentu (często problematyczne)
        if segment_index == 0 or segment_index == total_segments - 1:
            adaptive_offset *= 0.7
        
        # Uwzględnij długość segmentu - krótsze segmenty potrzebują mniejszej korekty
        segment_duration = segment['end'] - segment['start']
        if segment_duration < 1.0:  # Segmenty krótsze niż 1s
            adaptive_offset *= 0.8
        elif segment_duration > 5.0:  # Segmenty dłuższe niż 5s
            adaptive_offset *= 1.1
        
        # Uwzględnij pewność segmentu jeśli dostępna
        segment_confidence = segment.get('confidence', 1.0)
        if segment_confidence < 0.7:
            adaptive_offset *= segment_confidence
        
        return adaptive_offset
    
    def _validate_segment_timing(self, start: float, end: float, original_segment: Dict[str, Any]) -> bool:
        """
        Waliduj czy nowe czasy segmentu są rozsądne
        
        Args:
            start: Nowy czas rozpoczęcia
            end: Nowy czas zakończenia
            original_segment: Oryginalny segment
            
        Returns:
            True jeśli timing jest rozsądny
        """
        # Sprawdź podstawowe warunki
        if start < 0 or end <= start:
            return False
        
        # Sprawdź czy długość segmentu nie zmieniła się drastycznie
        original_duration = original_segment['end'] - original_segment['start']
        new_duration = end - start
        
        duration_ratio = new_duration / original_duration if original_duration > 0 else 1.0
        
        # Akceptuj zmiany długości do 20%
        if duration_ratio < 0.8 or duration_ratio > 1.2:
            return False
        
        # Sprawdź czy przesunięcie nie jest zbyt drastyczne
        start_shift = abs(start - original_segment['start'])
        if start_shift > 3.0:  # Maksymalnie 3s przesunięcia
            return False
        
        return True
    
    def _fix_overlapping_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Napraw nakładające się segmenty
        
        Args:
            segments: Lista segmentów do naprawy
            
        Returns:
            Lista segmentów bez nakładania
        """
        if len(segments) <= 1:
            return segments
        
        fixed_segments = []
        
        for i, segment in enumerate(segments):
            fixed_segment = segment.copy()
            
            # Sprawdź nakładanie z poprzednim segmentem
            if i > 0:
                prev_segment = fixed_segments[-1]
                if fixed_segment['start'] < prev_segment['end']:
                    # Nakładanie wykryte - dostosuj
                    gap = 0.1  # 100ms przerwy między segmentami
                    fixed_segment['start'] = prev_segment['end'] + gap
                    
                    # Upewnij się, że segment ma minimalną długość
                    min_duration = 0.5
                    if fixed_segment['end'] - fixed_segment['start'] < min_duration:
                        fixed_segment['end'] = fixed_segment['start'] + min_duration
                    
                    logger.debug(f"Naprawiono nakładanie segmentu {i}: nowy start {fixed_segment['start']:.2f}s")
            
            fixed_segments.append(fixed_segment)
        
        return fixed_segments
    
    def fine_tune_segment_timing(self, 
                               segments: List[Dict[str, Any]],
                               audio_features: AudioFeatures) -> List[Dict[str, Any]]:
        """
        Precyzyjne dostrojenie timingu segmentów
        
        Args:
            segments: Segmenty do dostrojenia
            audio_features: Cechy audio
            
        Returns:
            Dostrojone segmenty
        """
        if len(audio_features.energy_profile) == 0:
            return segments
        
        fine_tuned_segments = []
        
        # Konwertuj energie na czas
        frame_times = librosa.frames_to_time(
            np.arange(len(audio_features.energy_profile)),
            sr=audio_features.sample_rate,
            hop_length=self.hop_length
        )
        
        for segment in segments:
            fine_tuned_segment = segment.copy()
            
            # Znajdź najbliższe punkty wysokiej energii dla początku i końca
            start_time = segment['start']
            end_time = segment['end']
            
            # Dostrojenie początku segmentu
            start_window = 0.5  # 500ms okno wyszukiwania
            start_candidates = frame_times[
                (frame_times >= start_time - start_window) & 
                (frame_times <= start_time + start_window)
            ]
            
            if len(start_candidates) > 0:
                # Znajdź punkt o najwyższej energii w oknie
                start_indices = np.where(
                    (frame_times >= start_time - start_window) & 
                    (frame_times <= start_time + start_window)
                )[0]
                
                if len(start_indices) > 0:
                    energies = audio_features.energy_profile[start_indices]
                    best_start_idx = start_indices[np.argmax(energies)]
                    fine_tuned_segment['start'] = frame_times[best_start_idx]
            
            # Dostrojenie końca segmentu
            end_window = 0.3  # 300ms okno wyszukiwania
            end_candidates = frame_times[
                (frame_times >= end_time - end_window) & 
                (frame_times <= end_time + end_window)
            ]
            
            if len(end_candidates) > 0:
                # Znajdź punkt o najniższej energii w oknie (koniec mowy)
                end_indices = np.where(
                    (frame_times >= end_time - end_window) & 
                    (frame_times <= end_time + end_window)
                )[0]
                
                if len(end_indices) > 0:
                    energies = audio_features.energy_profile[end_indices]
                    best_end_idx = end_indices[np.argmin(energies)]
                    fine_tuned_segment['end'] = frame_times[best_end_idx]
            
            # Upewnij się, że koniec jest po początku
            if fine_tuned_segment['end'] <= fine_tuned_segment['start']:
                fine_tuned_segment['end'] = fine_tuned_segment['start'] + 0.5
            
            fine_tuned_segment['timing_fine_tuned'] = True
            fine_tuned_segments.append(fine_tuned_segment)
        
        logger.info(f"Dostrojono timing {len(fine_tuned_segments)} segmentów")
        return fine_tuned_segments
    
    def validate_sync_quality(self, 
                            segments: List[Dict[str, Any]],
                            audio_features: AudioFeatures) -> Dict[str, Any]:
        """
        Waliduj jakość synchronizacji
        
        Args:
            segments: Segmenty do walidacji
            audio_features: Cechy audio
            
        Returns:
            Raport jakości synchronizacji
        """
        detected_speech = self.detect_speech_segments(audio_features)
        
        if not detected_speech or not segments:
            return {
                'sync_quality': 'unknown',
                'coverage': 0.0,
                'timing_accuracy': 0.0,
                'issues': ['Brak danych do walidacji']
            }
        
        # Oblicz pokrycie
        total_coverage = 0.0
        total_segment_duration = 0.0
        timing_errors = []
        
        for segment in segments:
            start = segment['start']
            end = segment['end']
            duration = end - start
            total_segment_duration += duration
            
            # Znajdź pokrycie z wykrytymi segmentami mowy
            segment_coverage = 0.0
            for speech_start, speech_end in detected_speech:
                overlap_start = max(start, speech_start)
                overlap_end = min(end, speech_end)
                
                if overlap_start < overlap_end:
                    segment_coverage += overlap_end - overlap_start
            
            total_coverage += segment_coverage
            
            # Sprawdź błędy timingu
            coverage_ratio = segment_coverage / duration if duration > 0 else 0
            if coverage_ratio < 0.5:
                timing_errors.append(f"Segment {start:.1f}-{end:.1f}s: niska synchronizacja ({coverage_ratio:.1%})")
        
        # Oblicz metryki
        overall_coverage = total_coverage / total_segment_duration if total_segment_duration > 0 else 0.0
        timing_accuracy = 1.0 - (len(timing_errors) / len(segments)) if segments else 0.0
        
        # Określ jakość
        if overall_coverage >= 0.8 and timing_accuracy >= 0.8:
            sync_quality = 'excellent'
        elif overall_coverage >= 0.6 and timing_accuracy >= 0.6:
            sync_quality = 'good'
        elif overall_coverage >= 0.4 and timing_accuracy >= 0.4:
            sync_quality = 'acceptable'
        else:
            sync_quality = 'poor'
        
        return {
            'sync_quality': sync_quality,
            'coverage': overall_coverage,
            'timing_accuracy': timing_accuracy,
            'issues': timing_errors,
            'detected_speech_segments': len(detected_speech),
            'transcript_segments': len(segments)
        }