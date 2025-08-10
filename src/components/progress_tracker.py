"""
Komponent do śledzenia postępu przetwarzania
"""

import streamlit as st
import time
from typing import Optional

class ProgressTracker:
    """Komponent do śledzenia postępu przetwarzania"""
    
    def __init__(self):
        self.progress_bar = None
        self.status_text = None
        self.start_time = time.time()
        self._initialize_components()
    
    def _initialize_components(self):
        """Inicjalizuj komponenty progress trackera"""
        st.subheader("🔄 Postęp przetwarzania")
        
        # Progress bar
        self.progress_bar = st.progress(0)
        
        # Status text
        self.status_text = st.empty()
        
        # Czas przetwarzania
        self.time_text = st.empty()
    
    def update_progress(self, progress: float, message: str):
        """
        Aktualizuj postęp przetwarzania
        
        Args:
            progress: Postęp (0.0 - 1.0)
            message: Wiadomość o aktualnym stanie
        """
        if self.progress_bar:
            self.progress_bar.progress(progress)
        
        if self.status_text:
            self.status_text.text(message)
        
        # Aktualizuj czas
        elapsed_time = time.time() - self.start_time
        if self.time_text:
            self.time_text.text(f"⏱️ Czas przetwarzania: {elapsed_time:.1f}s")
        
        # Odśwież interfejs
        time.sleep(0.1)
    
    def complete(self, message: str = "✅ Przetwarzanie zakończone!"):
        """
        Oznacz przetwarzanie jako zakończone
        
        Args:
            message: Wiadomość o zakończeniu
        """
        if self.progress_bar:
            self.progress_bar.progress(1.0)
        
        if self.status_text:
            self.status_text.success(message)
        
        total_time = time.time() - self.start_time
        if self.time_text:
            self.time_text.success(f"✅ Całkowity czas przetwarzania: {total_time:.1f}s")
    
    def error(self, message: str):
        """
        Oznacz błąd w przetwarzaniu
        
        Args:
            message: Wiadomość o błędzie
        """
        if self.status_text:
            self.status_text.error(f"❌ {message}")
        
        total_time = time.time() - self.start_time
        if self.time_text:
            self.time_text.error(f"❌ Czas do błędu: {total_time:.1f}s")