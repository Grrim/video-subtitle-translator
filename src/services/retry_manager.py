"""
Menedżer ponownych prób i korekty opóźnień dla systemu tłumaczenia napisów
Obsługuje automatyczne ponowne przetwarzanie segmentów i synchronizację modułów
"""

import time
import asyncio
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

from ..utils.logger import get_logger

logger = get_logger(__name__)

class RetryReason(Enum):
    """Powody ponownych prób"""
    LOW_CONFIDENCE = "low_confidence"
    API_ERROR = "api_error"
    TIMEOUT = "timeout"
    QUALITY_CHECK_FAILED = "quality_check_failed"
    TIMING_MISMATCH = "timing_mismatch"
    TRANSLATION_ERROR = "translation_error"

@dataclass
class RetryConfig:
    """Konfiguracja ponownych prób"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_backoff: bool = True
    confidence_threshold: float = 0.7
    timeout_seconds: float = 300.0

@dataclass
class DelayCompensation:
    """Kompensacja opóźnień między modułami"""
    transcription_delay: float = 0.0
    translation_delay: float = 0.0
    processing_delay: float = 0.0
    total_compensation: float = 0.0

class RetryManager:
    """Menedżer ponownych prób i korekty opóźnień"""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.retry_history: List[Dict] = []
        self.delay_measurements: List[float] = []
        
    async def execute_with_retry(self, 
                                operation: Callable,
                                operation_name: str,
                                *args, 
                                **kwargs) -> Tuple[Any, int]:
        """
        Wykonaj operację z automatycznymi ponownymi próbami
        
        Args:
            operation: Funkcja do wykonania
            operation_name: Nazwa operacji (do logowania)
            *args, **kwargs: Argumenty dla operacji
            
        Returns:
            Tuple (result, retry_count)
        """
        retry_count = 0
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()
                
                # Wykonaj operację
                if asyncio.iscoroutinefunction(operation):
                    result = await operation(*args, **kwargs)
                else:
                    result = operation(*args, **kwargs)
                
                execution_time = time.time() - start_time
                
                # Sprawdź jakość wyniku
                if self._validate_result_quality(result, operation_name):
                    logger.info(f"{operation_name} zakończona pomyślnie po {attempt + 1} próbach")
                    self._record_successful_attempt(operation_name, execution_time, retry_count)
                    return result, retry_count
                else:
                    raise Exception(f"Wynik operacji {operation_name} nie spełnia kryteriów jakości")
                    
            except Exception as e:
                last_exception = e
                retry_count += 1
                
                logger.warning(f"{operation_name} - próba {attempt + 1} nieudana: {str(e)}")
                
                if attempt < self.config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.info(f"Ponowna próba za {delay:.1f} sekund...")
                    
                    self._record_failed_attempt(operation_name, str(e), attempt + 1)
                    
                    if asyncio.iscoroutinefunction(operation):
                        await asyncio.sleep(delay)
                    else:
                        time.sleep(delay)
                else:
                    logger.error(f"{operation_name} - wszystkie próby wyczerpane")
        
        # Wszystkie próby nieudane
        self._record_final_failure(operation_name, str(last_exception), retry_count)
        raise Exception(f"Operacja {operation_name} nieudana po {retry_count} próbach: {last_exception}")
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Oblicz opóźnienie przed ponowną próbą"""
        if self.config.exponential_backoff:
            delay = self.config.base_delay * (2 ** attempt)
        else:
            delay = self.config.base_delay
        
        return min(delay, self.config.max_delay)
    
    def _validate_result_quality(self, result: Any, operation_name: str) -> bool:
        """
        Waliduj jakość wyniku operacji
        
        Args:
            result: Wynik operacji
            operation_name: Nazwa operacji
            
        Returns:
            True jeśli wynik jest akceptowalny
        """
        if result is None:
            return False
        
        if operation_name == "transcription":
            return self._validate_transcription_result(result)
        elif operation_name == "translation":
            return self._validate_translation_result(result)
        elif operation_name == "subtitle_generation":
            return self._validate_subtitle_result(result)
        
        return True
    
    def _validate_transcription_result(self, result: Dict) -> bool:
        """Waliduj wynik transkrypcji"""
        if not isinstance(result, dict):
            return False
        
        # Sprawdź czy ma wymagane pola
        required_fields = ['text', 'segments', 'confidence']
        if not all(field in result for field in required_fields):
            return False
        
        # Sprawdź pewność
        confidence = result.get('confidence', 0.0)
        if confidence < self.config.confidence_threshold:
            logger.warning(f"Niska pewność transkrypcji: {confidence}")
            return False
        
        # Sprawdź czy ma segmenty
        segments = result.get('segments', [])
        if not segments:
            return False
        
        return True
    
    def _validate_translation_result(self, result: str) -> bool:
        """Waliduj wynik tłumaczenia"""
        if not isinstance(result, str):
            return False
        
        # Sprawdź czy nie jest pusty
        if not result.strip():
            return False
        
        # Sprawdź czy nie jest zbyt krótki (może wskazywać na błąd)
        if len(result.strip()) < 3:
            return False
        
        return True
    
    def _validate_subtitle_result(self, result: str) -> bool:
        """Waliduj wynik generowania napisów"""
        if not isinstance(result, str):
            return False
        
        # Sprawdź czy nie jest pusty
        if not result.strip():
            return False
        
        # Sprawdź czy zawiera znaczniki czasowe (dla SRT)
        if '-->' not in result:
            return False
        
        return True
    
    def measure_module_delay(self, module_name: str, start_time: float, end_time: float):
        """
        Zmierz opóźnienie modułu
        
        Args:
            module_name: Nazwa modułu
            start_time: Czas rozpoczęcia
            end_time: Czas zakończenia
        """
        delay = end_time - start_time
        self.delay_measurements.append(delay)
        
        logger.debug(f"Opóźnienie modułu {module_name}: {delay:.2f}s")
    
    def calculate_delay_compensation(self, 
                                   transcription_time: float,
                                   translation_time: float,
                                   processing_time: float) -> DelayCompensation:
        """
        Oblicz kompensację opóźnień między modułami
        
        Args:
            transcription_time: Czas transkrypcji
            translation_time: Czas tłumaczenia
            processing_time: Czas przetwarzania wideo
            
        Returns:
            DelayCompensation object
        """
        # Oblicz średnie opóźnienia z historii
        avg_delay = statistics.mean(self.delay_measurements) if self.delay_measurements else 0.0
        
        # Kompensacja dla każdego modułu
        transcription_compensation = max(0, transcription_time - avg_delay * 0.3)
        translation_compensation = max(0, translation_time - avg_delay * 0.2)
        processing_compensation = max(0, processing_time - avg_delay * 0.5)
        
        total_compensation = transcription_compensation + translation_compensation + processing_compensation
        
        compensation = DelayCompensation(
            transcription_delay=transcription_compensation,
            translation_delay=translation_compensation,
            processing_delay=processing_compensation,
            total_compensation=total_compensation
        )
        
        logger.info(f"Kompensacja opóźnień: {total_compensation:.2f}s")
        return compensation
    
    def adjust_segment_timing(self, 
                            segments: List[Dict], 
                            compensation: DelayCompensation) -> List[Dict]:
        """
        Dostosuj timing segmentów na podstawie kompensacji opóźnień
        
        Args:
            segments: Lista segmentów
            compensation: Kompensacja opóźnień
            
        Returns:
            Lista segmentów z dostosowanym timingiem
        """
        adjusted_segments = []
        
        # Oblicz współczynnik korekty
        correction_factor = 1.0 - (compensation.total_compensation * 0.01)  # Maksymalnie 1% korekty
        
        for segment in segments:
            adjusted_segment = segment.copy()
            
            # Dostosuj czasy z kompensacją
            original_start = segment.get('start', 0)
            original_end = segment.get('end', 0)
            
            adjusted_start = original_start * correction_factor
            adjusted_end = original_end * correction_factor
            
            # Upewnij się, że segmenty nie nakładają się
            if adjusted_segments:
                prev_end = adjusted_segments[-1].get('end', 0)
                if adjusted_start < prev_end:
                    adjusted_start = prev_end + 0.1  # 100ms przerwy
                    adjusted_end = adjusted_start + (original_end - original_start)
            
            adjusted_segment['start'] = adjusted_start
            adjusted_segment['end'] = adjusted_end
            adjusted_segment['timing_adjusted'] = True
            
            adjusted_segments.append(adjusted_segment)
        
        logger.info(f"Dostosowano timing {len(adjusted_segments)} segmentów")
        return adjusted_segments
    
    def _record_successful_attempt(self, operation: str, execution_time: float, retry_count: int):
        """Zapisz udaną próbę"""
        self.retry_history.append({
            'operation': operation,
            'status': 'success',
            'execution_time': execution_time,
            'retry_count': retry_count,
            'timestamp': time.time()
        })
    
    def _record_failed_attempt(self, operation: str, error: str, attempt: int):
        """Zapisz nieudaną próbę"""
        self.retry_history.append({
            'operation': operation,
            'status': 'failed_attempt',
            'error': error,
            'attempt': attempt,
            'timestamp': time.time()
        })
    
    def _record_final_failure(self, operation: str, error: str, total_attempts: int):
        """Zapisz ostateczną porażkę"""
        self.retry_history.append({
            'operation': operation,
            'status': 'final_failure',
            'error': error,
            'total_attempts': total_attempts,
            'timestamp': time.time()
        })
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """
        Pobierz statystyki ponownych prób
        
        Returns:
            Słownik ze statystykami
        """
        if not self.retry_history:
            return {}
        
        total_operations = len([h for h in self.retry_history if h['status'] in ['success', 'final_failure']])
        successful_operations = len([h for h in self.retry_history if h['status'] == 'success'])
        failed_operations = len([h for h in self.retry_history if h['status'] == 'final_failure'])
        
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
        
        # Średni czas wykonania
        execution_times = [h['execution_time'] for h in self.retry_history if 'execution_time' in h]
        avg_execution_time = statistics.mean(execution_times) if execution_times else 0
        
        # Średnia liczba ponownych prób
        retry_counts = [h['retry_count'] for h in self.retry_history if 'retry_count' in h]
        avg_retry_count = statistics.mean(retry_counts) if retry_counts else 0
        
        return {
            'total_operations': total_operations,
            'successful_operations': successful_operations,
            'failed_operations': failed_operations,
            'success_rate': success_rate,
            'average_execution_time': avg_execution_time,
            'average_retry_count': avg_retry_count,
            'total_delay_measurements': len(self.delay_measurements),
            'average_delay': statistics.mean(self.delay_measurements) if self.delay_measurements else 0
        }

class SegmentReprocessor:
    """Klasa do ponownego przetwarzania problematycznych segmentów"""
    
    def __init__(self, retry_manager: RetryManager):
        self.retry_manager = retry_manager
        
    async def reprocess_low_confidence_segments(self, 
                                              segments: List[Dict],
                                              transcription_service,
                                              translation_service,
                                              confidence_threshold: float = 0.6) -> List[Dict]:
        """
        Ponownie przetwórz segmenty o niskiej pewności
        
        Args:
            segments: Lista segmentów
            transcription_service: Serwis transkrypcji
            translation_service: Serwis tłumaczenia
            confidence_threshold: Próg pewności
            
        Returns:
            Lista przetworzonych segmentów
        """
        reprocessed_segments = []
        
        for i, segment in enumerate(segments):
            confidence = segment.get('confidence', 1.0)
            
            if confidence < confidence_threshold:
                logger.info(f"Ponowne przetwarzanie segmentu {i} (pewność: {confidence:.2f})")
                
                try:
                    # Ponowna transkrypcja z wyższą jakością
                    # (w rzeczywistej implementacji wymagałoby to ponownej ekstrakcji audio dla segmentu)
                    
                    # Ponowne tłumaczenie
                    original_text = segment.get('text', '')
                    if original_text:
                        retranslated = await self.retry_manager.execute_with_retry(
                            translation_service.translate_text,
                            "segment_retranslation",
                            original_text,
                            target_language=segment.get('target_language', 'PL')
                        )
                        
                        segment['text'] = retranslated[0]  # retranslated is (result, retry_count)
                        segment['reprocessed'] = True
                        segment['original_confidence'] = confidence
                        segment['confidence'] = min(confidence + 0.2, 1.0)  # Zwiększ pewność
                
                except Exception as e:
                    logger.error(f"Błąd podczas ponownego przetwarzania segmentu {i}: {e}")
                    segment['reprocessing_failed'] = True
            
            reprocessed_segments.append(segment)
        
        return reprocessed_segments
    
    def identify_problematic_segments(self, segments: List[Dict]) -> List[int]:
        """
        Zidentyfikuj problematyczne segmenty
        
        Args:
            segments: Lista segmentów
            
        Returns:
            Lista indeksów problematycznych segmentów
        """
        problematic = []
        
        for i, segment in enumerate(segments):
            issues = []
            
            # Sprawdź pewność
            confidence = segment.get('confidence', 1.0)
            if confidence < 0.6:
                issues.append('low_confidence')
            
            # Sprawdź długość
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            duration = end - start
            
            if duration < 0.3:
                issues.append('too_short')
            elif duration > 15.0:
                issues.append('too_long')
            
            # Sprawdź tekst
            text = segment.get('text', '')
            if not text.strip():
                issues.append('empty_text')
            elif len(text) < 3:
                issues.append('very_short_text')
            
            # Sprawdź timing
            if i > 0:
                prev_end = segments[i-1].get('end', 0)
                if start < prev_end:
                    issues.append('timing_overlap')
            
            if issues:
                problematic.append(i)
                segment['issues'] = issues
        
        logger.info(f"Zidentyfikowano {len(problematic)} problematycznych segmentów")
        return problematic