# TTS with Google Gemini GenAI SDK

This directory contains a standalone text-to-speech engine using Google's `gemini-3.1-flash-tts-preview` model.

## Prerequisites

1. Ensure Python 3 is installed.
2. Activate the virtual environment in this folder:
   ```bash
   cd tts
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `tts/` directory (you can copy `.env.example`) and add your API key:
   ```env
   GEMINI_API_KEY=your_secret_agent_key_here
   ```

## Usage

You can generate highly realistic speech using the `generate_audio.py` script.

```bash
python generate_audio.py --text "Hello world" --voice Kore --output out.wav --style "excitedly"
```

### Command-line Arguments

- `--text`: The text to convert to speech (required).
- `--voice`: The prebuilt voice name (optional, defaults to 'Aoede').
- `--output`: The path to save the output file (optional, defaults to 'output.wav').
- `--style`: Instructions for tone/emotion (e.g., "cheerful", "whispering", "excited") (optional).

### Available Voices

| Voice Name | Description |
|---|---|
| Aoede | Default voice |
| Kore | |
| Puck | |
| Fenrir | |
| Zephyr | |
