# 🎬 System Tłumaczenia Napisów Wideo

**Profesjonalny system tłumaczenia mowy w treściach wideo dla pracy magisterskiej**

## 📋 Opis

System wykorzystuje najnowsze technologie AI do automatycznego generowania napisów w wybranym języku:
- 🎤 **AssemblyAI** - rozpoznawanie mowy (ASR)
- 🌍 **DeepL** - tłumaczenie maszynowe (MT)
- 🎬 **FFmpeg** - przetwarzanie wideo

## 🚀 Szybkie uruchomienie

### 1. Wymagania systemowe
- Python 3.8 lub nowszy
- FFmpeg (zainstalowany w systemie)
- Połączenie z internetem

### 2. Instalacja

```bash
# Sklonuj/pobierz projekt
cd video-subtitle-translator

# Zainstaluj zależności
pip install -r requirements.txt
```

### 3. Uruchomienie

```bash
# Uruchom aplikację
streamlit run main.py
```

Aplikacja otworzy się automatycznie w przeglądarce pod adresem: `http://localhost:8501`

## 🔧 Konfiguracja

Klucze API są już skonfigurowane w pliku `.env`:
- AssemblyAI API Key: `ba934c79d9f84dafadaac077837937d9`
- DeepL API Key: `89fdb42c-3fb6-47df-b07d-ff14b19f6cc8:fx`

## 📖 Instrukcja użytkowania

1. **Prześlij wideo** - wybierz plik wideo z dysku
2. **Wybierz język** - wybierz język docelowy dla napisów
3. **Rozpocznij przetwarzanie** - kliknij przycisk "Rozpocznij przetwarzanie"
4. **Pobierz wyniki** - pobierz wideo z napisami i plik napisów

## 🎯 Obsługiwane formaty

### Wideo
- MP4, AVI, MOV, MKV, WMV, FLV, WEBM
- M4V, 3GP, OGV, TS, MTS, M2TS

### Napisy
- SRT (SubRip)
- VTT (WebVTT)
- ASS (Advanced SubStation Alpha)

## 🌍 Obsługiwane języki

System obsługuje tłumaczenie na ponad 30 języków, w tym:
- Polski, Angielski, Niemiecki, Francuski
- Hiszpański, Włoski, Portugalski, Rosyjski
- Japoński, Chiński, Koreański, Arabski
- I wiele innych...

## 📁 Struktura projektu

```
video-subtitle-translator/
├── main.py                 # Punkt wejścia aplikacji
├── requirements.txt        # Zależności Python
├── .env                   # Konfiguracja API
├── README.md              # Ta dokumentacja
└── src/
    ├── app.py             # Główna aplikacja Streamlit
    ├── components/        # Komponenty UI
    │   ├── file_uploader.py
    │   ├── language_selector.py
    │   ├── progress_tracker.py
    │   └── video_player.py
    ├── services/          # Serwisy biznesowe
    │   ├── transcription_service.py
    │   ├── translation_service.py
    │   ├── subtitle_generator.py
    │   └── video_processor.py
    └── utils/             # Narzędzia pomocnicze
        ├── config.py
        └── logger.py
```

## 🔍 Rozwiązywanie problemów

### Błąd: "FFmpeg not found"
```bash
# Windows (przez Chocolatey)
choco install ffmpeg

# Windows (przez winget)
winget install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### Błąd: "Module not found"
```bash
# Zainstaluj ponownie zależności
pip install -r requirements.txt --upgrade
```

### Błąd API
- Sprawdź połączenie z internetem
- Upewnij się, że klucze API są prawidłowe
- Sprawdź limity API (AssemblyAI/DeepL)

## 📊 Wydajność

- **Transkrypcja**: ~1-2 minuty na minutę wideo
- **Tłumaczenie**: ~10-30 sekund na 1000 słów
- **Przetwarzanie wideo**: ~30 sekund na minutę wideo

## 🎓 Praca magisterska

Ten system został opracowany jako część pracy magisterskiej na temat:
**"Zintegrowany system tłumaczenia mowy w treściach wideo z wykorzystaniem technologii ASR i MT"**

### Technologie użyte:
- **Python 3.8+** - język programowania
- **Streamlit** - framework webowy
- **AssemblyAI API** - rozpoznawanie mowy
- **DeepL API** - tłumaczenie maszynowe
- **FFmpeg** - przetwarzanie multimediów

## 📝 Licencja

Projekt edukacyjny - praca magisterska

## 👨‍💻 Autor

[Twoje imię i nazwisko]
[Uczelnia]
[Rok akademicki]

python -m streamlit run main.py