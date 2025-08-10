#!/usr/bin/env python3
"""
Video Subtitle Translation System
Główny punkt wejścia aplikacji - System tłumaczenia napisów wideo
Wykorzystuje AssemblyAI do ASR i DeepL do tłumaczenia maszynowego

Autor: [Twoje imię]
Praca magisterska: System tłumaczenia mowy w treściach wideo
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Dodaj główny katalog do ścieżki Python
sys.path.append(str(Path(__file__).parent))

def main():
    """Główna funkcja uruchamiająca aplikację Streamlit"""
    st.set_page_config(
        page_title="Video Subtitle Translator",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Import głównej aplikacji
    from src.app import run_app
    
    # Uruchom aplikację
    run_app()

if __name__ == "__main__":
    main()