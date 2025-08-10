"""
Komponent do wyboru języka docelowego tłumaczenia
"""

import streamlit as st
from ..utils.config import Config

class LanguageSelector:
    """Komponent do wyboru języka docelowego"""
    
    @staticmethod
    def render_target_language_selector() -> str:
        """
        Renderuj selektor języka docelowego
        
        Returns:
            Kod wybranego języka
        """
        config = Config()
        
        st.subheader("🌍 Język docelowy")
        
        # Stwórz opcje dla selectbox
        language_options = {}
        for code, name in config.language_names.items():
            language_options[f"{name} ({code})"] = code
        
        # Domyślny język (Polski)
        default_option = "Polski (PL)"
        if default_option not in language_options:
            default_option = list(language_options.keys())[0]
        
        # Selectbox z językami
        selected_option = st.selectbox(
            "Wybierz język napisów:",
            options=list(language_options.keys()),
            index=list(language_options.keys()).index(default_option),
            help="Język, na który zostanie przetłumaczony tekst z wideo"
        )
        
        selected_language_code = language_options[selected_option]
        
        # Wyświetl informacje o wybranym języku
        st.info(f"🎯 Napisy zostaną wygenerowane w języku: **{config.get_language_name(selected_language_code)}**")
        
        return selected_language_code
    
    @staticmethod
    def render_source_language_selector() -> str:
        """
        Renderuj selektor języka źródłowego (opcjonalnie)
        
        Returns:
            Kod wybranego języka źródłowego
        """
        config = Config()
        
        st.subheader("🎤 Język źródłowy")
        
        # Opcja automatycznego wykrywania
        auto_detect = st.checkbox(
            "Automatyczne wykrywanie języka",
            value=True,
            help="AssemblyAI automatycznie wykryje język mówiony w wideo"
        )
        
        if auto_detect:
            return "auto"
        
        # Selektor języka źródłowego
        language_options = {}
        for code, name in config.language_names.items():
            language_options[f"{name} ({code})"] = code
        
        selected_option = st.selectbox(
            "Wybierz język mówiony w wideo:",
            options=list(language_options.keys()),
            help="Język, w którym mówią osoby w wideo"
        )
        
        return language_options[selected_option]