# Speech Translate

Real-time tab audio transcription + Vietnamese translation using WhisperLiveKit and Ollama.

## How it works

```
Tab audio → Chrome Extension → WebSocket Proxy (port 8001)
                                      ↓
                              WLK Server (port 8000)  ← Whisper transcription
                                      ↓
                              Ollama llama3.2:3b      ← Vietnamese translation
                                      ↓
                              Chrome Extension         ← Display subtitles
```

## Requirements

- macOS (Apple Silicon recommended)
- Python 3.11+
- [Homebrew](https://brew.sh)
- [Ollama](https://ollama.com) (installed via brew)
- Google Chrome

## Setup (first time)

### 1. Install Ollama + model

```bash
brew install ollama
brew services start ollama
ollama pull llama3.2:3b
```

### 2. Create Python venv + install dependencies

```bash
python3 -m venv venv
venv/bin/pip install "whisperlivekit[mlx-whisper]" websockets httpx python-multipart
```

### 3. Load Chrome Extension

- Open Chrome → `chrome://extensions`
- Enable **Developer mode**
- Click **Load unpacked** → select the `chrome-extension/` folder

## Usage

Every time you want to use it, open **3 terminals**:

**Terminal 1 — Whisper server:**
```bash
venv/bin/wlk --model base --language auto
```

**Terminal 2 — Translation proxy:**
```bash
venv/bin/python proxy.py
```

**Terminal 3 — Ollama (if not running as a service):**
```bash
ollama serve
```

Then:
1. Open Chrome, click the **WhisperLiveKit Tab Capture** extension icon
2. Press **Start** and select the tab you want to translate
3. Vietnamese subtitles appear sentence by sentence

> The first run will download the Whisper `base` model (~150MB). Use `--model small` or `--model medium` for better accuracy.

## Configuration

Edit `proxy.py` to change:

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `llama3.2:3b` | Ollama model for translation |
| `MAX_DISPLAY_LINES` | `5` | Number of subtitle lines shown |

## Tips

- If Ollama is set up as a brew service (`brew services start ollama`), Terminal 3 is not needed
- Whisper `base` model is fastest; `small` or `medium` are more accurate
- The extension WebSocket URL defaults to `ws://localhost:8001/asr` (the proxy)
