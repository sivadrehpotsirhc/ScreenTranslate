import os
import sys
import argparse
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox as msgbox

# Import translator first to prevent OpenMP/WinRT COM thread initialization conflict on Windows
from screen_translator.translator import CTranslate2Translator, MockTranslator
from screen_translator.capture import ScreenCapturer
from screen_translator.ocr_engine import WinOcrEngine
from screen_translator.change_detector import ChangeDetector
from screen_translator.overlay import RegionSelector, TranslationOverlay

# Global flag to control the background capture loop
running = True

async def capture_loop(
    capturer: ScreenCapturer,
    detector: ChangeDetector,
    overlay: TranslationOverlay,
    root: tk.Tk,
    bbox: tuple[int, int, int, int],
    interval: float
):
    """
    Main loop running on the background thread. Captures frames, detects changes,
    runs OCR, performs translation, and updates the overlay.
    """
    global running
    print(f"Background capture loop started. Monitoring region {bbox} every {interval}s.")
    
    while running:
        try:
            # 1. Grab image from screen region
            image = capturer.capture_region(bbox)
            
            # 2. Check if region content has changed
            if detector.has_changed(image):
                # Retrieve current engines thread-safely
                with overlay.lock:
                    current_ocr = overlay.ocr
                    current_translator = overlay.translator
                
                if current_ocr and current_translator:
                    # 3. Perform OCR
                    text = await current_ocr.recognize(image)
                    text = text.strip()
                    
                    if text:
                        print(f"[OCR] Detected: {text}")
                        # 4. Perform local translation
                        translated = await current_translator.translate_async(text)
                        print(f"[Translation] Result: {translated}")
                        
                        # 5. Schedule UI update on Tkinter's main thread
                        if running:
                            root.after(0, lambda t=text, tr=translated: overlay.update(t, tr))
                    else:
                        # Clean the display if no text was found
                        if running:
                            root.after(0, lambda: overlay.update("", "No text detected in region"))
        except Exception as e:
            print(f"Error in capture loop: {e}", file=sys.stderr)
            
        await asyncio.sleep(interval)

def run_single_mode(args):
    """Runs OCR and translation exactly once for the selected region, then exits."""
    root = tk.Tk()
    root.withdraw()
    
    print("Select a screen region to translate (Click and drag, or ESC to cancel)...")
    selector = RegionSelector(root)
    bbox = selector.select()
    
    if bbox is None:
        print("Selection cancelled.")
        return
        
    print(f"Selected region: {bbox}")
    
    # Initialize components
    capturer = ScreenCapturer()
    
    # Initialize translator first to initialize OpenMP before winrt initializes COM MTA
    model_path = os.path.join(args.model_dir, f"{args.src}-{args.tgt}")
    if os.path.exists(os.path.join(model_path, "model.bin")):
        try:
            print(f"Loading local CTranslate2 translator from {model_path}...")
            translator = CTranslate2Translator(model_path, args.src, args.tgt)
        except Exception as e:
            print(f"Failed to load CTranslate2 translator: {e}. Falling back to Mock.", file=sys.stderr)
            translator = MockTranslator()
    else:
        print(f"CTranslate2 model files not found at {model_path}. Using MockTranslator.")
        translator = MockTranslator()

    try:
        ocr = WinOcrEngine(args.src)
    except Exception as e:
        error_msg = (
            f"OCR Initialization Error: {e}\n\n"
            f"If it complains about language packs, make sure you have the '{args.src}' language pack installed on Windows with OCR support."
        )
        print(error_msg, file=sys.stderr)
        msgbox.showerror("OCR Engine Error", error_msg)
        capturer.close()
        translator.close()
        return

    # Process capture
    image = capturer.capture_region(bbox)
    
    async def process():
        text = await ocr.recognize(image)
        if text.strip():
            translated = await translator.translate_async(text)
            print("\n" + "="*40)
            print(f"OCR ({args.src}):\n{text}")
            print("-"*40)
            print(f"Translation ({args.tgt}):\n{translated}")
            print("="*40 + "\n")
        else:
            print("No text detected in selected region.")
            
    asyncio.run(process())
    
    # Cleanup
    capturer.close()
    translator.close()

def main():
    parser = argparse.ArgumentParser(description="Python Real-Time Screen Translator via Windows OCR")
    parser.add_argument("--src", type=str, default="ja", help="Source language code for OCR (default: ja)")
    parser.add_argument("--tgt", type=str, default="en", help="Target translation language code (default: en)")
    parser.add_argument("--mode", type=str, default="continuous", choices=["single", "continuous"],
                        help="Execution mode: single or continuous (default: continuous)")
    parser.add_argument("--interval", type=float, default=1.5,
                        help="Time interval between captures in continuous mode in seconds (default: 1.5)")
    parser.add_argument("--model-dir", type=str, default="./models",
                        help="Path to CTranslate2 models directory (default: ./models)")
    args = parser.parse_args()

    if args.mode == "single":
        run_single_mode(args)
        return

    # Continuous Mode implementation
    root = tk.Tk()
    root.withdraw()
    
    print("Select a screen region to monitor (Click and drag, or ESC to cancel)...")
    selector = RegionSelector(root)
    bbox = selector.select()
    
    if bbox is None:
        print("Selection cancelled.")
        return
        
    print(f"Selected region: {bbox}")
    
    # Initialize components
    capturer = ScreenCapturer()
    
    # Initialize translator and OCR through the TranslationOverlay
    try:
        overlay = TranslationOverlay(root, args.model_dir, args.src, args.tgt)
    except Exception as e:
        error_msg = (
            f"Initialization Error: {e}\n\n"
            f"Please verify your language configuration and ensure at least one OCR language pack is installed."
        )
        print(error_msg, file=sys.stderr)
        msgbox.showerror("Initialization Error", error_msg)
        capturer.close()
        return

    detector = ChangeDetector()
    
    # Start asyncio loop in background thread
    global running
    running = True
    loop = asyncio.new_event_loop()
    
    def run_async_loop():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                capture_loop(capturer, detector, overlay, root, bbox, args.interval)
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Async loop exception: {e}", file=sys.stderr)
        finally:
            loop.close()

    bg_thread = threading.Thread(target=run_async_loop, daemon=True)
    bg_thread.start()
    
    # Run Tkinter mainloop on main thread
    try:
        print("Starting main overlay. Close the window to exit.")
        root.mainloop()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received, cleaning up...")
    finally:
        running = False
        # Stop background loop
        loop.call_soon_threadsafe(loop.stop)
        bg_thread.join(timeout=2.0)
        
        # Free hardware/model resources
        capturer.close()
        with overlay.lock:
            if overlay.translator:
                overlay.translator.close()
        print("Cleanup completed. Exiting.")

if __name__ == "__main__":
    main()
