"""
Serwis kontroli jakości dla systemu tłumaczenia napisów
Obsługuje walidację, weryfikację i kontrolę jakości na wszystkich etapach przetwarzania
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

from ..utils.logger import get_logger

logger = get_logger(__name__)

class QualityFlag(Enum):
    """Flagi jakości dla różnych aspektów przetwarzania"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"

@dataclass
class ConfidenceMetrics:
    """Metryki ufności dla segmentu"""
    transcription_confidence: float
    translation_confidence: float
    timing_confidence: float
    overall_confidence: float
    quality_flag: QualityFlag

@dataclass
class SpeakerInfo:
    """Informacje o mówiącym"""
    speaker_id: str
    confidence: float
    segments_count: int
    total_duration: float

@dataclass
class QualityReport:
    """Raport jakości przetwarzania"""
    overall_quality: QualityFlag
    confidence_metrics: ConfidenceMetrics
    speaker_analysis: List[SpeakerInfo]
    timing_issues: List[str]
    translation_issues: List[str]
    recommendations: List[str]
    processing_time: float
    retry_count: int

class QualityController:
    """Kontroler jakości dla całego procesu przetwarzania"""
    
    def __init__(self):
        self.min_confidence_threshold = 0.7
        self.min_segment_duration = 0.5
        self.max_segment_duration = 10.0
        self.max_chars_per_second = 20
        self.min_chars_per_second = 5
        
    def validate_transcription_quality(self, transcript_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Waliduj jakość transkrypcji
        
        Args:
            transcript_data: Dane transkrypcji z AssemblyAI
            
        Returns:
            Tuple (is_valid, issues_list)
        """
        issues = []
        
        # Sprawdź ogólną pewność
        overall_confidence = transcript_data.get('confidence', 0.0)
        if overall_confidence < self.min_confidence_threshold:
            issues.append(f"Niska ogólna pewność transkrypcji: {overall_confidence:.2f}")
        
        # Sprawdź segmenty
        segments = transcript_data.get('segments', [])
        if not segments:
            issues.append("Brak segmentów w transkrypcji")
            return False, issues
        
        low_confidence_segments = 0
        timing_issues = 0
        
        for i, segment in enumerate(segments):
            # Sprawdź pewność segmentu
            seg_confidence = segment.get('confidence', 0.0)
            if seg_confidence < self.min_confidence_threshold:
                low_confidence_segments += 1
            
            # Sprawdź timing
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            duration = end - start
            
            if duration < self.min_segment_duration:
                timing_issues += 1
            elif duration > self.max_segment_duration:
                timing_issues += 1
        
        # Sprawdź proporcję problemów
        if low_confidence_segments > len(segments) * 0.3:
            issues.append(f"Zbyt wiele segmentów o niskiej pewności: {low_confidence_segments}/{len(segments)}")
        
        if timing_issues > len(segments) * 0.2:
            issues.append(f"Problemy z timingiem w {timing_issues} segmentach")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def validate_translation_quality(self, original_segments: List[Dict], translated_segments: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Waliduj jakość tłumaczenia
        
        Args:
            original_segments: Oryginalne segmenty
            translated_segments: Przetłumaczone segmenty
            
        Returns:
            Tuple (is_valid, issues_list)
        """
        issues = []
        
        # Sprawdź zgodność liczby segmentów
        if len(original_segments) != len(translated_segments):
            issues.append(f"Niezgodność liczby segmentów: {len(original_segments)} vs {len(translated_segments)}")
        
        # Sprawdź długość tłumaczeń
        for i, (orig, trans) in enumerate(zip(original_segments, translated_segments)):
            orig_text = orig.get('text', '')
            trans_text = trans.get('text', '')
            
            # Sprawdź czy tłumaczenie nie jest zbyt krótkie lub długie
            length_ratio = len(trans_text) / len(orig_text) if len(orig_text) > 0 else 0
            
            if length_ratio < 0.3:
                issues.append(f"Segment {i}: Tłumaczenie zbyt krótkie (ratio: {length_ratio:.2f})")
            elif length_ratio > 3.0:
                issues.append(f"Segment {i}: Tłumaczenie zbyt długie (ratio: {length_ratio:.2f})")
            
            # Sprawdź czy tłumaczenie nie jest puste
            if not trans_text.strip():
                issues.append(f"Segment {i}: Puste tłumaczenie")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def validate_subtitle_timing(self, segments: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Waliduj timing napisów
        
        Args:
            segments: Segmenty z napisami
            
        Returns:
            Tuple (is_valid, issues_list)
        """
        issues = []
        
        for i, segment in enumerate(segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            text = segment.get('text', '')
            
            duration = end - start
            chars_per_second = len(text) / duration if duration > 0 else 0
            
            # Sprawdź prędkość czytania
            if chars_per_second > self.max_chars_per_second:
                issues.append(f"Segment {i}: Zbyt szybkie napisy ({chars_per_second:.1f} znaków/s)")
            elif chars_per_second < self.min_chars_per_second and len(text) > 10:
                issues.append(f"Segment {i}: Zbyt wolne napisy ({chars_per_second:.1f} znaków/s)")
            
            # Sprawdź nakładanie się segmentów
            if i > 0:
                prev_end = segments[i-1].get('end', 0)
                if start < prev_end:
                    issues.append(f"Segment {i}: Nakładanie się z poprzednim segmentem")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def calculate_confidence_metrics(self, transcript_data: Dict, translation_quality: float = 0.8) -> ConfidenceMetrics:
        """
        Oblicz metryki ufności
        
        Args:
            transcript_data: Dane transkrypcji
            translation_quality: Oszacowana jakość tłumaczenia
            
        Returns:
            ConfidenceMetrics object
        """
        # Pewność transkrypcji
        transcription_confidence = transcript_data.get('confidence', 0.0)
        
        # Pewność tłumaczenia (oszacowana na podstawie długości i spójności)
        translation_confidence = translation_quality
        
        # Pewność timingu (na podstawie jakości segmentacji)
        segments = transcript_data.get('segments', [])
        timing_confidences = []
        
        for segment in segments:
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            duration = end - start
            
            # Wyższa pewność dla segmentów o optymalnej długości
            if 1.0 <= duration <= 5.0:
                timing_confidences.append(0.9)
            elif 0.5 <= duration <= 8.0:
                timing_confidences.append(0.7)
            else:
                timing_confidences.append(0.5)
        
        timing_confidence = statistics.mean(timing_confidences) if timing_confidences else 0.5
        
        # Ogólna pewność
        overall_confidence = (transcription_confidence * 0.4 + 
                            translation_confidence * 0.4 + 
                            timing_confidence * 0.2)
        
        # Określ flagę jakości
        if overall_confidence >= 0.9:
            quality_flag = QualityFlag.EXCELLENT
        elif overall_confidence >= 0.8:
            quality_flag = QualityFlag.GOOD
        elif overall_confidence >= 0.6:
            quality_flag = QualityFlag.ACCEPTABLE
        elif overall_confidence >= 0.4:
            quality_flag = QualityFlag.POOR
        else:
            quality_flag = QualityFlag.FAILED
        
        return ConfidenceMetrics(
            transcription_confidence=transcription_confidence,
            translation_confidence=translation_confidence,
            timing_confidence=timing_confidence,
            overall_confidence=overall_confidence,
            quality_flag=quality_flag
        )
    
    def analyze_speakers(self, transcript_data: Dict) -> List[SpeakerInfo]:
        """
        Analizuj informacje o mówiących
        
        Args:
            transcript_data: Dane transkrypcji
            
        Returns:
            Lista informacji o mówiących
        """
        speakers = {}
        segments = transcript_data.get('segments', [])
        
        for segment in segments:
            speaker_id = segment.get('speaker', 'A')
            confidence = segment.get('confidence', 0.0)
            duration = segment.get('end', 0) - segment.get('start', 0)
            
            if speaker_id not in speakers:
                speakers[speaker_id] = {
                    'confidences': [],
                    'segments_count': 0,
                    'total_duration': 0.0
                }
            
            speakers[speaker_id]['confidences'].append(confidence)
            speakers[speaker_id]['segments_count'] += 1
            speakers[speaker_id]['total_duration'] += duration
        
        speaker_info_list = []
        for speaker_id, data in speakers.items():
            avg_confidence = statistics.mean(data['confidences']) if data['confidences'] else 0.0
            
            speaker_info_list.append(SpeakerInfo(
                speaker_id=speaker_id,
                confidence=avg_confidence,
                segments_count=data['segments_count'],
                total_duration=data['total_duration']
            ))
        
        return speaker_info_list
    
    def generate_quality_report(self, 
                              transcript_data: Dict, 
                              translated_segments: List[Dict],
                              processing_time: float,
                              retry_count: int = 0) -> QualityReport:
        """
        Generuj pełny raport jakości
        
        Args:
            transcript_data: Dane transkrypcji
            translated_segments: Przetłumaczone segmenty
            processing_time: Czas przetwarzania
            retry_count: Liczba ponownych prób
            
        Returns:
            QualityReport object
        """
        # Walidacje
        trans_valid, trans_issues = self.validate_transcription_quality(transcript_data)
        orig_segments = transcript_data.get('segments', [])
        transl_valid, transl_issues = self.validate_translation_quality(orig_segments, translated_segments)
        timing_valid, timing_issues = self.validate_subtitle_timing(translated_segments)
        
        # Metryki ufności
        confidence_metrics = self.calculate_confidence_metrics(transcript_data)
        
        # Analiza mówiących
        speaker_analysis = self.analyze_speakers(transcript_data)
        
        # Określ ogólną jakość
        if all([trans_valid, transl_valid, timing_valid]) and confidence_metrics.overall_confidence >= 0.8:
            overall_quality = QualityFlag.EXCELLENT
        elif confidence_metrics.overall_confidence >= 0.6:
            overall_quality = QualityFlag.GOOD
        elif confidence_metrics.overall_confidence >= 0.4:
            overall_quality = QualityFlag.ACCEPTABLE
        else:
            overall_quality = QualityFlag.POOR
        
        # Rekomendacje
        recommendations = []
        if not trans_valid:
            recommendations.append("Rozważ użycie wyższej jakości transkrypcji (premium)")
        if not transl_valid:
            recommendations.append("Sprawdź ustawienia tłumaczenia lub wybierz inny język")
        if not timing_valid:
            recommendations.append("Dostosuj parametry segmentacji czasowej")
        if confidence_metrics.overall_confidence < 0.6:
            recommendations.append("Rozważ ręczną weryfikację wyników")
        
        return QualityReport(
            overall_quality=overall_quality,
            confidence_metrics=confidence_metrics,
            speaker_analysis=speaker_analysis,
            timing_issues=timing_issues,
            translation_issues=transl_issues,
            recommendations=recommendations,
            processing_time=processing_time,
            retry_count=retry_count
        )