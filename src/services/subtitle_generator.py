"""
Serwis do generowania napisów w różnych formatach
"""

import re
from typing import List, Dict, Any
from datetime import timedelta
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SubtitleGenerator:
    """Klasa do generowania napisów w różnych formatach"""
    
    def __init__(self):
        self.supported_formats = ['SRT', 'VTT', 'ASS']
    
    def generate_subtitles(
        self, 
        segments: List[Dict[str, Any]], 
        translated_text: str, 
        format: str = 'SRT',
        max_chars_per_line: int = 42
    ) -> str:
        """
        Generuj napisy na podstawie segmentów i przetłumaczonego tekstu
        
        Args:
            segments: Lista segmentów z timestampami z AssemblyAI
            translated_text: Przetłumaczony tekst
            format: Format napisów (SRT, VTT, ASS)
            max_chars_per_line: Maksymalna liczba znaków w linii
            
        Returns:
            Zawartość pliku z napisami
        """
        try:
            # Podziel przetłumaczony tekst na segmenty
            subtitle_segments = self._align_translation_with_segments(segments, translated_text)
            
            # Podziel długie linie
            subtitle_segments = self._split_long_lines(subtitle_segments, max_chars_per_line)
            
            # Generuj napisy w odpowiednim formacie
            if format.upper() == 'SRT':
                return self._generate_srt(subtitle_segments)
            elif format.upper() == 'VTT':
                return self._generate_vtt(subtitle_segments)
            elif format.upper() == 'ASS':
                return self._generate_ass(subtitle_segments)
            else:
                raise ValueError(f"Nieobsługiwany format: {format}")
                
        except Exception as e:
            logger.error(f"Błąd podczas generowania napisów: {e}")
            raise
    
    def _align_translation_with_segments(
        self, 
        segments: List[Dict[str, Any]], 
        translated_text: str
    ) -> List[Dict[str, Any]]:
        """
        Dopasuj przetłumaczony tekst do segmentów czasowych zachowując dokładną synchronizację
        """
        # Podziel tekst na słowa
        words = translated_text.split()
        
        # Oblicz ile słów przypada na każdy segment
        words_per_segment = len(words) / len(segments) if segments else 0
        
        aligned_segments = []
        word_index = 0
        
        for i, segment in enumerate(segments):
            # Zachowaj DOKŁADNIE oryginalne timestampy z AssemblyAI
            start_time = segment.get('start', 0)
            end_time = segment.get('end', 0)
            
            # Oblicz które słowa należą do tego segmentu
            if i == len(segments) - 1:
                # Ostatni segment - weź wszystkie pozostałe słowa
                segment_words = words[word_index:]
            else:
                # Oblicz końcowy indeks dla tego segmentu
                end_word_index = min(len(words), int((i + 1) * words_per_segment))
                segment_words = words[word_index:end_word_index]
                word_index = end_word_index
            
            # Stwórz tekst dla tego segmentu
            segment_text = ' '.join(segment_words).strip()
            
            # Dodaj segment z oryginalnymi timestampami
            aligned_segments.append({
                'start': start_time,
                'end': end_time,
                'text': segment_text,
                'confidence': segment.get('confidence', 0.9),
                'speaker': segment.get('speaker', 'A')
            })
        
        return aligned_segments
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Podziel tekst na zdania"""
        # Użyj regex do podziału na zdania
        sentence_endings = r'[.!?]+\s+'
        sentences = re.split(sentence_endings, text)
        
        # Usuń puste zdania
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    
    def _redistribute_text(self, text: str, num_segments: int) -> List[str]:
        """Redystrybuuj tekst na określoną liczbę segmentów"""
        words = text.split()
        words_per_segment = len(words) // num_segments
        
        segments = []
        for i in range(num_segments):
            start_idx = i * words_per_segment
            if i == num_segments - 1:  # Ostatni segment - weź wszystkie pozostałe słowa
                end_idx = len(words)
            else:
                end_idx = (i + 1) * words_per_segment
            
            segment_text = ' '.join(words[start_idx:end_idx])
            segments.append(segment_text)
        
        return segments
    
    def _split_long_lines(
        self, 
        segments: List[Dict[str, Any]], 
        max_chars_per_line: int
    ) -> List[Dict[str, Any]]:
        """Podziel długie linie na krótsze"""
        result_segments = []
        
        for segment in segments:
            text = segment['text']
            
            if len(text) <= max_chars_per_line:
                result_segments.append(segment)
                continue
            
            # Podziel długi tekst na linie
            lines = self._wrap_text(text, max_chars_per_line)
            
            # Oblicz czas trwania dla każdej linii
            duration = segment['end'] - segment['start']
            time_per_line = duration / len(lines)
            
            for i, line in enumerate(lines):
                new_segment = {
                    'start': segment['start'] + (i * time_per_line),
                    'end': segment['start'] + ((i + 1) * time_per_line),
                    'text': line
                }
                result_segments.append(new_segment)
        
        return result_segments
    
    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        """Zawiń tekst do określonej długości linii"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            # Sprawdź czy dodanie słowa nie przekroczy limitu
            if current_length + word_length + len(current_line) <= max_chars:
                current_line.append(word)
                current_length += word_length
            else:
                # Zakończ obecną linię i rozpocznij nową
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        # Dodaj ostatnią linię
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _generate_srt(self, segments: List[Dict[str, Any]]) -> str:
        """Generuj napisy w formacie SRT"""
        srt_content = []
        
        for i, segment in enumerate(segments, 1):
            start_time = self._format_srt_timestamp(segment['start'])
            end_time = self._format_srt_timestamp(segment['end'])
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment['text'])
            srt_content.append("")  # Pusta linia
        
        return '\n'.join(srt_content)
    
    def _generate_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """Generuj napisy w formacie VTT"""
        vtt_content = ["WEBVTT", ""]
        
        for segment in segments:
            start_time = self._format_vtt_timestamp(segment['start'])
            end_time = self._format_vtt_timestamp(segment['end'])
            
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(segment['text'])
            vtt_content.append("")  # Pusta linia
        
        return '\n'.join(vtt_content)
    
    def _generate_ass(self, segments: List[Dict[str, Any]]) -> str:
        """Generuj napisy w formacie ASS"""
        ass_header = """[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,16,&Hffffff,&Hffffff,&H0,&H0,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        ass_content = [ass_header]
        
        for segment in segments:
            start_time = self._format_ass_timestamp(segment['start'])
            end_time = self._format_ass_timestamp(segment['end'])
            
            ass_content.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{segment['text']}")
        
        return '\n'.join(ass_content)
    
    def _format_srt_timestamp(self, seconds: float) -> str:
        """Formatuj timestamp dla SRT (HH:MM:SS,mmm)"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        milliseconds = int((seconds - total_seconds) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def _format_vtt_timestamp(self, seconds: float) -> str:
        """Formatuj timestamp dla VTT (HH:MM:SS.mmm)"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        milliseconds = int((seconds - total_seconds) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    def _format_ass_timestamp(self, seconds: float) -> str:
        """Formatuj timestamp dla ASS (H:MM:SS.cc)"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        centiseconds = int((seconds - total_seconds) * 100)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"