"""
Debugger timestampów - diagnozuje i naprawia problemy z synchronizacją
"""

import os
import subprocess
import json
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class TimestampIssue:
    """Problem z timestampem"""
    issue_type: str
    description: str
    severity: str  # low, medium, high, critical
    suggested_fix: str

class TimestampDebugger:
    """Debugger problemów z timestampami"""
    
    def __init__(self):
        self.issues_found = []
        
    def diagnose_timestamp_issues(self, video_path: str, audio_path: str, transcript_data: Dict) -> List[TimestampIssue]:
        """
        Zdiagnozuj problemy z timestampami
        
        Args:
            video_path: Ścieżka do wideo
            audio_path: Ścieżka do audio
            transcript_data: Dane transkrypcji
            
        Returns:
            Lista znalezionych problemów
        """
        self.issues_found = []
        
        logger.info("🔍 Diagnozowanie problemów z timestampami...")
        
        # 1. Sprawdź długość plików
        self._check_file_durations(video_path, audio_path, transcript_data)
        
        # 2. Sprawdź jakość timestampów z AssemblyAI
        self._check_assemblyai_timestamps(transcript_data)
        
        # 3. Sprawdź ekstraktowanie audio
        self._check_audio_extraction(video_path, audio_path)
        
        # 4. Sprawdź offset między video a audio
        self._check_av_sync_offset(video_path, audio_path)
        
        # 5. Sprawdź segmentację
        self._check_segmentation_quality(transcript_data)
        
        logger.info(f"🔍 Znaleziono {len(self.issues_found)} problemów z timestampami")
        return self.issues_found
    
    def _check_file_durations(self, video_path: str, audio_path: str, transcript_data: Dict):
        """Sprawdź długości plików"""
        try:
            # Długość wideo
            video_duration = self._get_media_duration(video_path)
            
            # Długość audio
            audio_duration = self._get_media_duration(audio_path) if os.path.exists(audio_path) else 0
            
            # Długość transkrypcji
            transcript_duration = 0
            if 'segments' in transcript_data and transcript_data['segments']:
                last_segment = transcript_data['segments'][-1]
                transcript_duration = last_segment.get('end', 0)
            
            logger.info(f"📊 Długości: Video={video_duration:.1f}s, Audio={audio_duration:.1f}s, Transkrypcja={transcript_duration:.1f}s")
            
            # Sprawdź różnice
            if abs(video_duration - audio_duration) > 1.0:
                self.issues_found.append(TimestampIssue(
                    issue_type="duration_mismatch",
                    description=f"Różnica długości video ({video_duration:.1f}s) i audio ({audio_duration:.1f}s): {abs(video_duration - audio_duration):.1f}s",
                    severity="high",
                    suggested_fix="Sprawdź proces ekstraktowania audio z wideo"
                ))
            
            if abs(transcript_duration - audio_duration) > 2.0:
                self.issues_found.append(TimestampIssue(
                    issue_type="transcript_duration_mismatch",
                    description=f"Transkrypcja ({transcript_duration:.1f}s) nie pasuje do audio ({audio_duration:.1f}s)",
                    severity="critical",
                    suggested_fix="Sprawdź czy AssemblyAI otrzymało prawidłowy plik audio"
                ))
                
        except Exception as e:
            logger.error(f"Błąd sprawdzania długości: {e}")
    
    def _get_media_duration(self, file_path: str) -> float:
        """Pobierz długość pliku multimedialnego"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                return duration
            else:
                logger.warning(f"Nie można pobrać długości {file_path}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Błąd pobierania długości {file_path}: {e}")
            return 0.0
    
    def _check_assemblyai_timestamps(self, transcript_data: Dict):
        """Sprawdź jakość timestampów z AssemblyAI"""
        
        # Sprawdź czy mamy segmenty
        segments = transcript_data.get('segments', [])
        if not segments:
            self.issues_found.append(TimestampIssue(
                issue_type="no_segments",
                description="Brak segmentów w transkrypcji",
                severity="critical",
                suggested_fix="Sprawdź czy transkrypcja się udała"
            ))
            return
        
        # Sprawdź timestampy segmentów
        for i, segment in enumerate(segments):
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            # Sprawdź czy end > start
            if end <= start:
                self.issues_found.append(TimestampIssue(
                    issue_type="invalid_segment_timing",
                    description=f"Segment {i}: koniec ({end}) <= początek ({start})",
                    severity="high",
                    suggested_fix="Napraw timestampy segmentów"
                ))
            
            # Sprawdź czy segment nie jest za krótki
            duration = end - start
            if duration < 0.1:
                self.issues_found.append(TimestampIssue(
                    issue_type="too_short_segment",
                    description=f"Segment {i}: za krótki ({duration:.3f}s)",
                    severity="medium",
                    suggested_fix="Połącz z sąsiednimi segmentami"
                ))
            
            # Sprawdź nakładanie z następnym segmentem
            if i < len(segments) - 1:
                next_start = segments[i + 1].get('start', 0)
                if end > next_start:
                    self.issues_found.append(TimestampIssue(
                        issue_type="overlapping_segments",
                        description=f"Segmenty {i} i {i+1} nakładają się",
                        severity="high",
                        suggested_fix="Dostosuj timestampy aby uniknąć nakładania"
                    ))
        
        # Sprawdź czy mamy word-level timestamps
        words = transcript_data.get('words', [])
        if not words:
            self.issues_found.append(TimestampIssue(
                issue_type="no_word_timestamps",
                description="Brak word-level timestamps",
                severity="medium",
                suggested_fix="Włącz word-level timestamps w AssemblyAI"
            ))
        else:
            # Sprawdź jakość word timestamps
            self._check_word_timestamps(words)
    
    def _check_word_timestamps(self, words: List[Dict]):
        """Sprawdź jakość word-level timestamps"""
        
        very_short_words = 0
        very_long_words = 0
        overlapping_words = 0
        
        for i, word in enumerate(words):
            start = word.get('start', 0)
            end = word.get('end', 0)
            duration = end - start
            
            # Bardzo krótkie słowa
            if duration < 0.05:  # < 50ms
                very_short_words += 1
            
            # Bardzo długie słowa
            if duration > 3.0:  # > 3s
                very_long_words += 1
            
            # Nakładanie z następnym słowem
            if i < len(words) - 1:
                next_start = words[i + 1].get('start', 0)
                if end > next_start:
                    overlapping_words += 1
        
        # Raportuj problemy
        if very_short_words > len(words) * 0.1:  # > 10% słów
            self.issues_found.append(TimestampIssue(
                issue_type="many_short_words",
                description=f"{very_short_words} bardzo krótkich słów (< 50ms)",
                severity="medium",
                suggested_fix="Zwiększ minimalną długość słów"
            ))
        
        if very_long_words > 0:
            self.issues_found.append(TimestampIssue(
                issue_type="very_long_words",
                description=f"{very_long_words} bardzo długich słów (> 3s)",
                severity="medium",
                suggested_fix="Podziel długie słowa"
            ))
        
        if overlapping_words > 0:
            self.issues_found.append(TimestampIssue(
                issue_type="overlapping_words",
                description=f"{overlapping_words} nakładających się słów",
                severity="high",
                suggested_fix="Napraw nakładające się timestampy słów"
            ))
    
    def _check_audio_extraction(self, video_path: str, audio_path: str):
        """Sprawdź proces ekstraktowania audio"""
        
        if not os.path.exists(audio_path):
            self.issues_found.append(TimestampIssue(
                issue_type="missing_audio_file",
                description="Brak wyekstraktowanego pliku audio",
                severity="critical",
                suggested_fix="Sprawdź proces ekstraktowania audio z wideo"
            ))
            return
        
        # Sprawdź czy audio ma odpowiednią jakość
        try:
            # Sprawdź parametry audio
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-select_streams', 'a:0', audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if 'streams' in data and data['streams']:
                    audio_stream = data['streams'][0]
                    
                    sample_rate = int(audio_stream.get('sample_rate', 0))
                    channels = int(audio_stream.get('channels', 0))
                    
                    logger.info(f"📊 Audio: {sample_rate}Hz, {channels} kanałów")
                    
                    # Sprawdź czy parametry są odpowiednie
                    if sample_rate < 16000:
                        self.issues_found.append(TimestampIssue(
                            issue_type="low_sample_rate",
                            description=f"Niska częstotliwość próbkowania: {sample_rate}Hz",
                            severity="medium",
                            suggested_fix="Użyj wyższej częstotliwości (min. 16kHz)"
                        ))
                    
                    if channels > 2:
                        self.issues_found.append(TimestampIssue(
                            issue_type="too_many_channels",
                            description=f"Za dużo kanałów audio: {channels}",
                            severity="low",
                            suggested_fix="Konwertuj do mono lub stereo"
                        ))
                        
        except Exception as e:
            logger.error(f"Błąd sprawdzania audio: {e}")
    
    def _check_av_sync_offset(self, video_path: str, audio_path: str):
        """Sprawdź offset między video a audio"""
        
        # To jest zaawansowana analiza - na razie podstawowa implementacja
        try:
            # Sprawdź czy video ma audio track
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                has_video = False
                has_audio = False
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        has_video = True
                    elif stream.get('codec_type') == 'audio':
                        has_audio = True
                
                if has_video and not has_audio:
                    self.issues_found.append(TimestampIssue(
                        issue_type="video_without_audio",
                        description="Wideo nie ma ścieżki audio",
                        severity="high",
                        suggested_fix="Sprawdź czy wideo ma dźwięk"
                    ))
                
                if not has_video:
                    self.issues_found.append(TimestampIssue(
                        issue_type="no_video_stream",
                        description="Brak ścieżki wideo",
                        severity="critical",
                        suggested_fix="Sprawdź czy plik to rzeczywiście wideo"
                    ))
                        
        except Exception as e:
            logger.error(f"Błąd sprawdzania A/V sync: {e}")
    
    def _check_segmentation_quality(self, transcript_data: Dict):
        """Sprawdź jakość segmentacji"""
        
        segments = transcript_data.get('segments', [])
        if not segments:
            return
        
        # Sprawdź rozkład długości segmentów
        durations = [seg.get('end', 0) - seg.get('start', 0) for seg in segments]
        
        if durations:
            avg_duration = sum(durations) / len(durations)
            
            # Bardzo krótkie segmenty
            short_segments = len([d for d in durations if d < 0.5])
            if short_segments > len(segments) * 0.3:  # > 30%
                self.issues_found.append(TimestampIssue(
                    issue_type="many_short_segments",
                    description=f"{short_segments} bardzo krótkich segmentów (< 0.5s)",
                    severity="medium",
                    suggested_fix="Połącz krótkie segmenty"
                ))
            
            # Bardzo długie segmenty
            long_segments = len([d for d in durations if d > 10.0])
            if long_segments > 0:
                self.issues_found.append(TimestampIssue(
                    issue_type="very_long_segments",
                    description=f"{long_segments} bardzo długich segmentów (> 10s)",
                    severity="low",
                    suggested_fix="Podziel długie segmenty"
                ))
    
    def get_suggested_fixes(self) -> List[str]:
        """Pobierz sugerowane poprawki"""
        fixes = []
        
        for issue in self.issues_found:
            if issue.severity in ['high', 'critical']:
                fixes.append(f"🔴 {issue.suggested_fix}")
            elif issue.severity == 'medium':
                fixes.append(f"🟡 {issue.suggested_fix}")
            else:
                fixes.append(f"🟢 {issue.suggested_fix}")
        
        return fixes
    
    def generate_debug_report(self) -> str:
        """Generuj raport debug"""
        
        report = ["🔍 RAPORT DEBUGOWANIA TIMESTAMPÓW", "=" * 50, ""]
        
        if not self.issues_found:
            report.append("✅ Nie znaleziono problemów z timestampami!")
            return "\n".join(report)
        
        # Grupuj problemy według ważności
        critical = [i for i in self.issues_found if i.severity == 'critical']
        high = [i for i in self.issues_found if i.severity == 'high']
        medium = [i for i in self.issues_found if i.severity == 'medium']
        low = [i for i in self.issues_found if i.severity == 'low']
        
        if critical:
            report.append("🔴 KRYTYCZNE PROBLEMY:")
            for issue in critical:
                report.append(f"   • {issue.description}")
                report.append(f"     Rozwiązanie: {issue.suggested_fix}")
            report.append("")
        
        if high:
            report.append("🟠 WAŻNE PROBLEMY:")
            for issue in high:
                report.append(f"   • {issue.description}")
                report.append(f"     Rozwiązanie: {issue.suggested_fix}")
            report.append("")
        
        if medium:
            report.append("🟡 ŚREDNIE PROBLEMY:")
            for issue in medium:
                report.append(f"   • {issue.description}")
            report.append("")
        
        if low:
            report.append("🟢 DROBNE PROBLEMY:")
            for issue in low:
                report.append(f"   • {issue.description}")
            report.append("")
        
        return "\n".join(report)