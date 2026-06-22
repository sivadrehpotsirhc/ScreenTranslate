# ScreenTranslate
**Python Real-Time Screen Translator via Windows OCR & Local CTranslate2**

ScreenTranslate is a high-performance, fully offline, real-time screen translation utility designed for Windows 10/11. It captures a designated region of your screen, extracts text using the native Windows OCR engine (`winrt.windows.media.ocr`), and translates it locally using `ctranslate2` and Helsinki-NLP models.

## Key Features
*   **Fully Offline:** No cloud API calls, ensuring zero latency, absolute privacy, and offline functionality.
*   **Dynamic Language Selection:** Change source and target languages on the fly directly from the overlay GUI. The source dropdown automatically populates with all installed Windows OCR language packs.
*   **Always-on-Top Resizable Overlay:** Displays translations in a clean, draggable, dark-themed Tkinter display window. Easily resize the window by dragging the bottom-right corner ("◢").
*   **Live Status Indicator:** Visually displays whether the translator is running with a local offline model (`● Offline Model`) or using a mock fallback if a translation model is missing (`● Mock (Missing: ja-en)`).
*   **Smart Change Detection:** Grayscale pixel-delta comparison prevents redundant OCR/translation cycles when the screen region hasn't changed.

---

## Installation

### 1. Install Dependencies
Make sure you are running a 64-bit version of Python 3.9+. Run the following command to install the required libraries:

```bash
pip install -r requirements.txt
```

### 2. Download Translation Models (e.g., Japanese → English)
We use pre-converted Helsinki-NLP models from Hugging Face. The application looks for models under `./models/{src}-{tgt}`.

To download the default **Japanese-to-English** model, run:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='gaudi/opus-mt-ja-en-ctranslate2', local_dir='./models/ja-en', ignore_patterns=['*.md', '.gitattributes'])"
```

To translate from **Spanish-to-English**, run:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Helsinki-NLP/opus-mt-es-en', local_dir='./models/es-en', ignore_patterns=['*.md', '.gitattributes'])"
```
*(Note: Helsinki-NLP models on HuggingFace Hub are compatible and run with high speed using INT8 quantization).*

### 3. Add Windows OCR Language Packs
The OCR engine utilizes language packs installed on Windows. To add support for another language:
1.  Open Windows **Settings** (`Win + I`).
2.  Navigate to **Time & Language** -> **Language & Region** (or **Preferred languages**).
3.  Click **Add a language** and search for your target language (e.g. Spanish, German, Japanese).
4.  Ensure that **Optical Character Recognition (OCR)** is checked during the installation options.
5.  Wait for the download to finish. It will automatically show up in the app's dropdown.

---

## Verification

Before running the main application, run the environment check script to verify your setup:

```bash
python verify_setup.py --src ja --tgt en
```

This script validates:
*   Python version and architecture.
*   PyWinRT modules and base runtime.
*   Windows OCR support for the selected source language pack.
*   Screen capture capabilities (`mss` & `Pillow`).
*   CTranslate2 local model and SentencePiece tokenizer loading.
*   A translation smoke test.

---

## How to Run

### Interactive Continuous Mode (Default)
This mode lets you select a region of your screen to monitor continuously. Every `1.5` seconds, if the text changes, it is translated and shown in the floating overlay.

```bash
python main.py --src ja --tgt en --mode continuous
```

1.  A fullscreen translucent overlay will appear.
2.  **Click and drag** a red box over the screen region containing the text you want to translate (e.g. PDF, game, or browser window).
3.  Upon releasing the mouse, the selection overlay closes, and the main translation overlay appears.
4.  **Drag the overlay** from anywhere in the window.
5.  **Resize the overlay** by clicking and dragging the **◢** handle in the bottom-right corner.
6.  **Switch languages** on the fly using the dropdown menus. If a model for that language pair has not been downloaded to `./models/`, the status indicator will show `● Mock (Missing: src-tgt)` and output text with a `[MOCK]` prefix.
7.  Press **Escape** during selection to cancel. Click the **✕** in the overlay header to exit.

### Single Capture Mode
Captures the selected region exactly once, prints the OCR text and translation directly to your console, and exits.

```bash
python main.py --src ja --tgt en --mode single
```

---

## CLI Options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--src` | `str` | `ja` | Default source language code for OCR (e.g. `ja`, `es`, `zh-CN`). |
| `--tgt` | `str` | `en` | Default target translation language code (e.g. `en`, `es`). |
| `--mode` | `str` | `continuous` | `single` or `continuous`. |
| `--interval` | `float` | `1.5` | Sampling interval in seconds for continuous mode. |
| `--model-dir` | `str` | `./models` | Directory holding local translation models. |

---

## Known Pitfalls & Solutions

### OpenMP / WinRT Threading Apartment Conflict
On Windows, initializing the WinRT COM Multithreaded Apartment (MTA) before OpenMP (used by `ctranslate2` for CPU execution) can result in a silent segmentation fault (crash with exit code 1).
*   **Solution:** ScreenTranslate enforces a strict import and instantiation order, ensuring the `translator` module is loaded and its model initialized *before* `WinOcrEngine` (which imports `winrt`).
