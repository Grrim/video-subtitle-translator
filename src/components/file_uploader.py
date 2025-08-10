"""
Komponent do przesyłania plików wideo
"""

import streamlit as st
from typing import Optional
from ..utils.config import Config

class FileUploader:
    """Komponent do przesyłania plików wideo"""
    
    @staticmethod
    def render_video_uploader() -> Optional[st.runtime.uploaded_file_manager.UploadedFile]:
        """
        Renderuj komponent do przesyłania plików wideo
        
        Returns:
            Przesłany plik wideo lub None
        """
        config = Config()
        
        st.subheader("📁 Przesyłanie pliku wideo")
        
        # Informacje o obsługiwanych formatach
        with st.expander("ℹ️ Obsługiwane formaty", expanded=False):
            st.write("**Obsługiwane formaty wideo:**")
            formats_text = ", ".join([f".{fmt}" for fmt in config.supported_video_formats])
            st.write(formats_text)
            st.write(f"**Maksymalny rozmiar pliku:** {config.max_file_size_mb} MB")
        
        # Upload pliku
        uploaded_file = st.file_uploader(
            "Wybierz plik wideo",
            type=config.supported_video_formats,
            help=f"Maksymalny rozmiar: {config.max_file_size_mb} MB"
        )
        
        if uploaded_file is not None:
            # Sprawdź rozmiar pliku
            file_size_mb = uploaded_file.size / (1024 * 1024)
            
            if file_size_mb > config.max_file_size_mb:
                st.error(f"❌ Plik jest za duży! Maksymalny rozmiar: {config.max_file_size_mb} MB")
                return None
            
            # Wyświetl informacje o pliku
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Nazwa pliku", uploaded_file.name)
            
            with col2:
                st.metric("Rozmiar", f"{file_size_mb:.1f} MB")
            
            with col3:
                st.metric("Typ", uploaded_file.type)
            
            return uploaded_file
        
        return None