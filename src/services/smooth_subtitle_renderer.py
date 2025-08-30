"""
Renderer napisów bez migotania z wysoką jakością
Eliminuje migotanie i poprawia płynność wyświetlania napisów
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import re

from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SmoothSubtitleConfig:
    """Konfiguracja płynnych napisów"""
    min_display_duration: float = 0.3  # Minimalna długość wyświetlania
    overlap_duration: float = 0.1      # Nakładanie między napisami
    fade_duration: float = 0.05        # Czas fade in/out
    stability_threshold: float = 0.2   # Próg stabilności dla eliminacji migotania
    max_words_per_line: int = 8        # Maksymalna liczba słów w linii
    font_size: int = 18                # Rozmiar czcionki
    outline_width: int = 2             # Szerokość obramowania
    shadow_offset: int = 1             # Przesunięcie cienia

class SmoothSubtitleRenderer:
    """Renderer napisów bez migotania"""
    
    def __init__(self, config: SmoothSubtitleConfig = None):
        self.config = config or SmoothSubtitleConfig()
        
    def generate_smooth_srt(self, word_segments: List[Dict], display_mode: str = "smooth_progressive") -> str:
        """
        Generuj płynne napisy SRT bez migotania
        
        Args:
            word_segments: Segmenty z podziałem na słowa
            display_mode: Tryb wyświetlania
            
        Returns:
            Zawartość SRT z płynnymi napisami
        """
        try:
            logger.info(f"Generowanie płynnych napisów w trybie: {display_mode}")
            
            if display_mode == "smooth_progressive":
                return self._generate_smooth_progressive(word_segments)
            elif display_mode == "stable_blocks":
                return self._generate_stable_blocks(word_segments)
            elif display_mode == "fade_transitions":
                return self._generate_fade_transitions(word_segments)
            else:
                return self._generate_smooth_progressive(word_segments)
                
        except Exception as e:
            logger.error(f"Błąd generowania płynnych napisów: {e}")
            return self._fallback_generation(word_segments)
    
    def _generate_smooth_progressive(self, word_segments: List[Dict]) -> str:
        """
        Generuj progresywne napisy z eliminacją migotania
        
        Args:
            word_segments: Segmenty słów
            
        Returns:
            Zawartość SRT
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            words = segment.get('words', [])
            if not words:
                continue
            
            # Grupuj słowa w stabilne bloki
            stable_blocks = self._create_stable_blocks(words)
            
            for block in stable_blocks:
                # Każdy blok to grupa słów wyświetlanych razem
                display_text = " ".join([w.get('word', '') for w in block])
                
                # Oblicz timing z nakładaniem
                start_time = block[0].get('start', 0)
                end_time = block[-1].get('end', 0)
                
                # Przedłuż wyświetlanie dla stabilności
                extended_end = max(end_time, start_time + self.config.min_display_duration)
                
                # Dodaj nakładanie z następnym blokiem
                if subtitle_index < len(stable_blocks):
                    extended_end += self.config.overlap_duration
                
                srt_content.append(str(subtitle_index))
                srt_content.append(f"{self._format_timestamp(start_time)} --> {self._format_timestamp(extended_end)}")
                srt_content.append(self._format_text_with_styling(display_text))
                srt_content.append("")
                
                subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def _create_stable_blocks(self, words: List[Dict]) -> List[List[Dict]]:
        """
        Stwórz stabilne bloki słów eliminujące migotanie
        
        Args:
            words: Lista słów
            
        Returns:
            Lista bloków słów
        """
        if not words:
            return []
        
        blocks = []
        current_block = []
        
        for i, word in enumerate(words):
            current_block.append(word)
            
            # Sprawdź czy zakończyć blok
            should_end_block = (
                len(current_block) >= self.config.max_words_per_line or  # Maksymalna długość
                i == len(words) - 1 or  # Ostatnie słowo
                self._is_natural_break_point(word, words[i+1] if i+1 < len(words) else None)  # Naturalna przerwa
            )
            
            if should_end_block:
                # Sprawdź czy blok jest wystarczająco długi
                block_duration = current_block[-1].get('end', 0) - current_block[0].get('start', 0)
                
                if block_duration >= self.config.stability_threshold or len(current_block) >= 3:
                    blocks.append(current_block.copy())
                    current_block = []
                elif blocks:
                    # Dodaj do poprzedniego bloku jeśli za krótki
                    blocks[-1].extend(current_block)
                    current_block = []
                else:
                    # Pierwszy blok - zachowaj nawet jeśli krótki
                    blocks.append(current_block.copy())
                    current_block = []
        
        return blocks
    
    def _is_natural_break_point(self, current_word: Dict, next_word: Optional[Dict]) -> bool:
        """
        Sprawdź czy to naturalne miejsce na przerwę
        
        Args:
            current_word: Aktualne słowo
            next_word: Następne słowo
            
        Returns:
            True jeśli to dobre miejsce na przerwę
        """
        if not next_word:
            return True
        
        current_text = current_word.get('word', '').lower()
        next_text = next_word.get('word', '').lower()
        
        # Przerwa po znakach interpunkcyjnych
        if any(punct in current_text for punct in ['.', '!', '?', ',', ';', ':']):
            return True
        
        # Przerwa przed spójnikami
        if next_text in ['i', 'a', 'ale', 'oraz', 'lub', 'bo', 'że', 'gdy', 'jeśli']:
            return True
        
        # Przerwa po długiej pauzie
        current_end = current_word.get('end', 0)
        next_start = next_word.get('start', 0)
        
        if next_start - current_end > 0.3:  # 300ms pauzy
            return True
        
        return False
    
    def _generate_stable_blocks(self, word_segments: List[Dict]) -> str:
        """
        Generuj napisy w stabilnych blokach (bez migotania)
        
        Args:
            word_segments: Segmenty słów
            
        Returns:
            Zawartość SRT
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            words = segment.get('words', [])
            if not words:
                continue
            
            # Podziel na większe, stabilne bloki
            blocks = self._create_larger_blocks(words, min_words=3, max_words=6)
            
            for block in blocks:
                display_text = " ".join([w.get('word', '') for w in block])
                
                start_time = block[0].get('start', 0)
                end_time = block[-1].get('end', 0)
                
                # Zapewnij minimalną długość wyświetlania
                min_end = start_time + self.config.min_display_duration * 2  # Dłużej dla stabilności
                end_time = max(end_time, min_end)
                
                srt_content.append(str(subtitle_index))
                srt_content.append(f"{self._format_timestamp(start_time)} --> {self._format_timestamp(end_time)}")
                srt_content.append(self._format_text_with_styling(display_text))
                srt_content.append("")
                
                subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def _create_larger_blocks(self, words: List[Dict], min_words: int = 3, max_words: int = 6) -> List[List[Dict]]:
        """
        Stwórz większe bloki słów dla stabilności
        
        Args:
            words: Lista słów
            min_words: Minimalna liczba słów w bloku
            max_words: Maksymalna liczba słów w bloku
            
        Returns:
            Lista bloków
        """
        blocks = []
        current_block = []
        
        for word in words:
            current_block.append(word)
            
            if len(current_block) >= max_words:
                blocks.append(current_block.copy())
                current_block = []
        
        # Dodaj ostatni blok
        if current_block:
            if len(current_block) >= min_words or not blocks:
                blocks.append(current_block)
            else:
                # Dodaj do poprzedniego bloku jeśli za mały
                blocks[-1].extend(current_block)
        
        return blocks
    
    def _generate_fade_transitions(self, word_segments: List[Dict]) -> str:
        """
        Generuj napisy z płynnymi przejściami fade
        
        Args:
            word_segments: Segmenty słów
            
        Returns:
            Zawartość SRT z efektami fade
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            words = segment.get('words', [])
            if not words:
                continue
            
            # Grupuj słowa z nakładaniem
            overlapping_groups = self._create_overlapping_groups(words)
            
            for group in overlapping_groups:
                display_text = " ".join([w.get('word', '') for w in group])
                
                start_time = group[0].get('start', 0) - self.config.fade_duration
                end_time = group[-1].get('end', 0) + self.config.fade_duration
                
                # Dodaj efekty fade w formacie ASS (jeśli obsługiwane)
                styled_text = self._add_fade_effects(display_text)
                
                srt_content.append(str(subtitle_index))
                srt_content.append(f"{self._format_timestamp(max(0, start_time))} --> {self._format_timestamp(end_time)}")
                srt_content.append(styled_text)
                srt_content.append("")
                
                subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def _create_overlapping_groups(self, words: List[Dict]) -> List[List[Dict]]:
        """
        Stwórz nakładające się grupy słów
        
        Args:
            words: Lista słów
            
        Returns:
            Lista grup z nakładaniem
        """
        groups = []
        group_size = 4
        overlap = 2
        
        for i in range(0, len(words), group_size - overlap):
            group = words[i:i + group_size]
            if group:
                groups.append(group)
        
        return groups
    
    def _format_text_with_styling(self, text: str) -> str:
        """
        Formatuj tekst z wysokiej jakości stylizacją
        
        Args:
            text: Tekst do sformatowania
            
        Returns:
            Sformatowany tekst
        """
        # Podstawowe formatowanie dla lepszej czytelności
        styled_text = text.strip()
        
        # Usuń automatyczne dodawanie tagów HTML <b></b>
        # Pozostaw czysty tekst dla lepszej kompatybilności
        # Jeśli potrzebujesz pogrubienia, możesz to włączyć opcjonalnie
        
        # Opcjonalne formatowanie (wyłączone domyślnie)
        # styled_text = f"<b>{styled_text}</b>"
        
        return styled_text
    
    def _add_fade_effects(self, text: str) -> str:
        """
        Dodaj efekty fade do tekstu
        
        Args:
            text: Tekst
            
        Returns:
            Tekst z efektami fade
        """
        # Dla SRT można użyć podstawowych tagów
        return f"<b>{text}</b>"
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Formatuj timestamp z wysoką precyzją
        
        Args:
            seconds: Czas w sekundach
            
        Returns:
            Sformatowany timestamp
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    def _fallback_generation(self, word_segments: List[Dict]) -> str:
        """
        Fallback generation w przypadku błędu
        
        Args:
            word_segments: Segmenty słów
            
        Returns:
            Podstawowe napisy SRT
        """
        srt_content = []
        subtitle_index = 1
        
        for segment in word_segments:
            words = segment.get('words', [])
            if not words:
                continue
            
            text = " ".join([w.get('word', '') for w in words])
            start_time = words[0].get('start', 0)
            end_time = words[-1].get('end', 0)
            
            srt_content.append(str(subtitle_index))
            srt_content.append(f"{self._format_timestamp(start_time)} --> {self._format_timestamp(end_time)}")
            srt_content.append(text)
            srt_content.append("")
            
            subtitle_index += 1
        
        return '\n'.join(srt_content)
    
    def generate_high_quality_ass(self, word_segments: List[Dict]) -> str:
        """
        Generuj napisy w formacie ASS z wysoką jakością
        
        Args:
            word_segments: Segmenty słów
            
        Returns:
            Zawartość pliku ASS
        """
        ass_header = f"""[Script Info]
Title: High Quality Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{self.config.font_size},&Hffffff,&Hffffff,&H000000,&H80000000,1,0,0,0,100,100,0,0,1,{self.config.outline_width},{self.config.shadow_offset},2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        ass_content = [ass_header]
        
        # Generuj płynne napisy w formacie ASS
        stable_blocks = []
        for segment in word_segments:
            words = segment.get('words', [])
            if words:
                blocks = self._create_stable_blocks(words)
                stable_blocks.extend(blocks)
        
        for block in stable_blocks:
            display_text = " ".join([w.get('word', '') for w in block])
            start_time = block[0].get('start', 0)
            end_time = block[-1].get('end', 0)
            
            # Przedłuż dla stabilności
            end_time = max(end_time, start_time + self.config.min_display_duration)
            
            start_ass = self._format_ass_timestamp(start_time)
            end_ass = self._format_ass_timestamp(end_time)
            
            # Dodaj efekty fade dla płynności
            fade_in = int(self.config.fade_duration * 1000)
            fade_out = int(self.config.fade_duration * 1000)
            
            text_with_effects = f"{{\\fad({fade_in},{fade_out})}}{display_text}"
            
            ass_content.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text_with_effects}")
        
        return '\n'.join(ass_content)
    
    def _format_ass_timestamp(self, seconds: float) -> str:
        """Formatuj timestamp dla ASS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds - int(seconds)) * 100)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"