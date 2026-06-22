# ScreenTranslate
**Python Real-Time Screen Translator via Windows OCR & Local CTranslate2**

ScreenTranslate is a high-performance, fully offline, real-time screen translation utility designed for Windows 10/11. It captures a designated region of your screen, extracts text using the native Windows OCR engine (`winrt.windows.media.ocr`), and translates it locally using `ctranslate2` and Helsinki-NLP models.

## Key Features
*   **Fully Offline:** No cloud API calls, ensuring zero latency, absolute privacy, and offline functionality.
*   **Native Windows OCR:** Utilizes Windows 10/11 built-in OCR packs (no Tesseract or heavy EasyOCR dependencies).
*   **Low Latency Inference:** Employs CTranslate2 with INT8 quantization, giving 3x speedups on CPU.
*   **Smart Change Detection:** Grayscale pixel-delta comparison prevents redundant OCR/translation cycles when the screen region hasn't changed.
*   **Always-on-Top Overlay:** Displays translations in a clean, draggable dark-themed Tkinter display window.

---

## Installation

### 1. Install Dependencies
Make sure you are running a 64-bit version of Python 3.9+. Run the following command to install the required libraries:

```bash
pip install -r requirements.txt
```

### 2. Download Translation Models (e.g., Japanese → English)
We use the pre-converted Helsinki-NLP models from Hugging Face. To download the default Japanese-to-English model, run:

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='gaudi/opus-mt-ja-en-ctranslate2', local_dir='./models/ja-en', ignore_patterns=['*.md', '.gitattributes'])"
```

### 3. Add Windows OCR Language Packs
The OCR engine utilizes language packs installed on your system. If you want to translate from Japanese:
1.  Open Windows **Settings** (`Win + I`).
2.  Navigate to **Time & Language** -> **Language & Region** (or **Preferred languages**).
3.  Click **Add a language** and search for **Japanese** (or your target language).
4.  Ensure that **Optical Character Recognition (OCR)** is checked during the installation options.
5.  Wait for the download to finish.

---

## Verification

Before running the main application, run the environment check script to verify your setup:

```bash
python verify_setup.py --src ja --tgt en
```

This script will validate:
*   Python version and architecture.
*   PyWinRT modules and base runtime.
*   Windows OCR support for the source language pack.
*   Screen capture capabilities (`mss` & `Pillow`).
*   CTranslate2 local model and SentencePiece tokenizer loading.
*   A translation smoke test of a Japanese sentence.

---

## How to Run

### Interactive Continuous Mode (Default)
This mode lets you select a region of your screen to monitor continuously. Every `1.5` seconds, if the text changes, it is translated and shown in the floating overlay.

```bash
python main.py --src ja --tgt en --mode continuous
```

1.  A fullscreen translucent overlay will appear.
2.  **Click and drag** a red box over the screen region containing the text you want to translate (e.g., a PDF, game, or browser window).
3.  Upon releasing the mouse, the selection overlay closes, and a small, floating translation display appears in the bottom-right corner.
4.  **Drag the overlay** anywhere you want.
5.  Press **Escape** during selection to cancel. Click the **✕** in the overlay to exit the program.

### Single Capture Mode
Captures the selected region exactly once, prints the OCR text and translation directly to your console, and exits.

```bash
python main.py --src ja --tgt en --mode single
```

---

## CLI Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--src` | `str` | `ja` | Source language code for OCR (e.g., `ja`, `zh-CN`, `es`). |
| `--tgt` | `str` | `en` | Target translation language code (e.g., `en`). |
| `--mode` | `str` | `continuous` | `single` or `continuous`. |
| `--interval` | `float` | `1.5` | Sampling interval in seconds for continuous mode. |
| `--model-dir` | `str` | `./models` | Directory holding local translation models. |

---

## Known Pitfalls & Solutions

### OpenMP / WinRT Threading Apartment Conflict
On Windows, initializing the WinRT COM Multithreaded Apartment (MTA) before OpenMP (used by `ctranslate2` for CPU execution) can result in a silent segmentation fault (crash with exit code 1). 
*   **Solution:** ScreenTranslate enforces a strict import and instantiation order, ensuring the `translator` module is loaded and its model initialized *before* `WinOcrEngine` (which imports `winrt`).
