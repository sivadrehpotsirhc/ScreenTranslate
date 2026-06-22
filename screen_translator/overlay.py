import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox as msgbox
from screen_translator.ocr_engine import WinOcrEngine
from screen_translator.translator import CTranslate2Translator, MockTranslator

def clean_lang_code(tag: str) -> str:
    """Extracts base language code (e.g. ja-JP -> ja)."""
    return tag.split('-')[0].split('_')[0].lower()

class RegionSelector:
    """Provides a transparent fullscreen Tkinter overlay to select a screen region."""
    
    def __init__(self, root: tk.Tk = None):
        self.root = root or tk.Tk()
        if root is None:
            self.root.withdraw()  # Hide main window if we created it
        self.bbox = None
        self.top = None
        self.canvas = None
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

    def select(self) -> tuple[int, int, int, int] | None:
        """
        Opens the fullscreen selector window. Blocks execution until selection is finished.
        
        Returns:
            A tuple of (left, top, width, height) in screen coordinates, or None if cancelled.
        """
        self.bbox = None
        self.top = tk.Toplevel(self.root)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.3)
        self.top.configure(bg='black')
        self.top.attributes('-topmost', True)
        
        # Canvas for drawing selection rect
        self.canvas = tk.Canvas(self.top, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Mouse event bindings
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", self._on_escape)
        
        # Force focus on the overlay
        self.top.focus_force()
        
        # Block until top window is destroyed
        self.top.wait_window(self.top)
        return self.bbox

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        # Draw red selection border
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#FF3333", width=2
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        end_x = event.x
        end_y = event.y
        
        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        width = abs(self.start_x - end_x)
        height = abs(self.start_y - end_y)
        
        # Prevent tiny accidental selections (minimum 5x5 pixels)
        if width > 5 and height > 5:
            self.bbox = (left, top, width, height)
        else:
            self.bbox = None
            
        self.top.destroy()

    def _on_escape(self, event):
        self.bbox = None
        self.top.destroy()


class TranslationOverlay:
    """An elegant, semi-transparent, always-on-top floating Tkinter overlay for displaying translations."""
    
    def __init__(self, root: tk.Tk, model_dir: str, initial_src: str, initial_tgt: str):
        self.root = root
        self.model_dir = model_dir
        self.src_lang = initial_src
        self.tgt_lang = initial_tgt
        self.ocr = None
        self.translator = None
        self.lock = threading.Lock()
        
        self.window = tk.Toplevel(self.root)
        
        # Remove standard OS window frame and title bar
        self.window.overrideredirect(True)
        # Always keep on top
        self.window.attributes('-topmost', True)
        # Semi-transparency (85%)
        self.window.attributes('-alpha', 0.85)
        # Dark theme background with light gray border
        self.window.configure(
            bg='#121212',
            highlightbackground='#333333',
            highlightcolor='#333333',
            highlightthickness=1
        )
        
        # Position at the bottom-right of screen by default (larger default window size)
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        width = 600
        height = 250
        x = screen_width - width - 20
        y = screen_height - height - 60
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Enable dragging the window
        self.window.bind("<ButtonPress-1>", self._start_drag)
        self.window.bind("<B1-Motion>", self._on_drag)
        
        # Bind Configure to dynamically adjust wraplength of text labels when resized
        self.window.bind("<Configure>", self._on_configure)
        
        # Header container
        self.header = tk.Frame(self.window, bg='#121212')
        self.header.pack(fill='x', padx=10, pady=(8, 0))
        
        self.title_lbl = tk.Label(
            self.header,
            text="TRANSLATION",
            font=("Segoe UI", 9, "bold"),
            fg="#666666",
            bg="#121212"
        )
        self.title_lbl.pack(side='left')
        
        # Hover-responsive close button
        self.close_btn = tk.Label(
            self.header,
            text="✕",
            font=("Segoe UI", 10),
            fg="#666666",
            bg="#121212",
            cursor="hand2"
        )
        self.close_btn.pack(side='right')
        self.close_btn.bind("<Button-1>", lambda e: self.close())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#FF5555"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg="#666666"))
        
        # Get installed Windows OCR languages
        try:
            installed_langs = WinOcrEngine.available_languages_detailed()
        except Exception:
            installed_langs = [("ja", "Japanese"), ("en-US", "English (United States)")]
            
        self.src_options = [f"{name} ({tag})" for tag, name in installed_langs]
        self.src_map = {f"{name} ({tag})": tag for tag, name in installed_langs}
        
        # Standard target languages
        target_langs = [
            ("en", "English"),
            ("es", "Spanish"),
            ("ja", "Japanese"),
            ("zh", "Chinese"),
            ("de", "German"),
            ("fr", "French"),
            ("ko", "Korean"),
            ("ru", "Russian"),
            ("it", "Italian"),
            ("pt", "Portuguese")
        ]
        self.tgt_options = [f"{name} ({tag})" for tag, name in target_langs]
        self.tgt_map = {f"{name} ({tag})": tag for tag, name in target_langs}
        
        # Select initial values based on arguments
        initial_src_val = self.src_options[0] if self.src_options else ""
        for opt in self.src_options:
            tag = self.src_map[opt]
            if tag.lower() == initial_src.lower() or clean_lang_code(tag) == clean_lang_code(initial_src):
                initial_src_val = opt
                break
                
        initial_tgt_val = self.tgt_options[0] if self.tgt_options else ""
        for opt in self.tgt_options:
            tag = self.tgt_map[opt]
            if tag.lower() == initial_tgt.lower() or clean_lang_code(tag) == clean_lang_code(initial_tgt):
                initial_tgt_val = opt
                break
                
        # Toolbar for language selection (dark themed Comboboxes)
        self.toolbar = tk.Frame(self.window, bg='#121212')
        self.toolbar.pack(fill='x', padx=10, pady=5)
        
        # Styling for comboboxes
        style = ttk.Style(self.window)
        style.theme_use('clam')
        style.configure('TCombobox',
            fieldbackground='#1e1e1e',
            background='#333333',
            foreground='#FFFFFF',
            bordercolor='#333333',
            arrowcolor='#FFFFFF'
        )
        style.map('TCombobox',
            fieldbackground=[('readonly', '#1e1e1e')],
            foreground=[('readonly', '#FFFFFF')]
        )
        self.window.option_add('*TCombobox*Listbox.background', '#1e1e1e')
        self.window.option_add('*TCombobox*Listbox.foreground', '#FFFFFF')
        self.window.option_add('*TCombobox*Listbox.selectBackground', '#333333')
        self.window.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')
        
        self.src_combo = ttk.Combobox(self.toolbar, values=self.src_options, state="readonly", width=22)
        self.src_combo.set(initial_src_val)
        self.src_combo.pack(side='left', padx=(0, 5))
        
        self.arrow_lbl = tk.Label(self.toolbar, text="→", fg="#8A8A8A", bg="#121212", font=("Segoe UI", 10))
        self.arrow_lbl.pack(side='left', padx=5)
        
        self.tgt_combo = ttk.Combobox(self.toolbar, values=self.tgt_options, state="readonly", width=15)
        self.tgt_combo.set(initial_tgt_val)
        self.tgt_combo.pack(side='left', padx=5)
        
        self.status_indicator = tk.Label(
            self.toolbar,
            text="● Loading...",
            fg="#FFFF55",
            bg="#121212",
            font=("Segoe UI", 9)
        )
        self.status_indicator.pack(side='right', padx=(5, 0))
        
        # Text display container
        self.text_frame = tk.Frame(self.window, bg='#121212')
        self.text_frame.pack(fill='both', expand=True, padx=12, pady=(5, 10))
        
        # OCR Text (Source): small, italicized, gray (larger than original)
        self.src_label = tk.Label(
            self.text_frame,
            text="Drag a region to begin...",
            font=("Segoe UI", 11, "italic"),
            fg="#8A8A8A",
            bg="#121212",
            wraplength=width-30,
            justify="left",
            anchor="w"
        )
        self.src_label.pack(fill="x", anchor="w", pady=(0, 5))
        
        # Translated Text (Target): large, white
        self.tgt_label = tk.Label(
            self.text_frame,
            text="",
            font=("Segoe UI", 14),
            fg="#FFFFFF",
            bg="#121212",
            wraplength=width-30,
            justify="left",
            anchor="w"
        )
        self.tgt_label.pack(fill="both", expand=True, anchor="w")
        
        # Resizing grip at bottom right
        self.grip = tk.Label(
            self.window,
            text="◢",
            font=("Segoe UI", 12),
            fg="#333333",
            bg="#121212",
            cursor="size_nw_se"
        )
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<ButtonPress-1>", self._start_resize)
        self.grip.bind("<B1-Motion>", self._on_resize)
        
        self.src_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)
        self.tgt_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)
        
        # Run first load synchronously so errors propagate to startup if needed
        self._update_engines(self.src_map.get(initial_src_val, initial_src), self.tgt_map.get(initial_tgt_val, initial_tgt), first_load=True)
        
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 0
        self._resize_start_h = 0

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        x = self.window.winfo_x() + (event.x - self._drag_start_x)
        y = self.window.winfo_y() + (event.y - self._drag_start_y)
        self.window.geometry(f"+{x}+{y}")

    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.window.winfo_width()
        self._resize_start_h = self.window.winfo_height()

    def _on_resize(self, event):
        delta_w = event.x_root - self._resize_start_x
        delta_h = event.y_root - self._resize_start_y
        new_w = max(400, self._resize_start_w + delta_w)
        new_h = max(180, self._resize_start_h + delta_h)
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.geometry(f"{new_w}x{new_h}+{x}+{y}")

    def _on_configure(self, event):
        if event.widget == self.window:
            w = event.width
            self.src_label.config(wraplength=w - 30)
            self.tgt_label.config(wraplength=w - 30)

    def _on_lang_changed(self, event=None):
        src_disp = self.src_combo.get()
        tgt_disp = self.tgt_combo.get()
        
        src_tag = self.src_map.get(src_disp, "ja")
        tgt_tag = self.tgt_map.get(tgt_disp, "en")
        
        self.status_indicator.config(text="● Loading...", fg="#FFFF55")
        threading.Thread(target=self._update_engines, args=(src_tag, tgt_tag), daemon=True).start()

    def _update_engines(self, src_tag: str, tgt_tag: str, first_load=False):
        try:
            src_clean = clean_lang_code(src_tag)
            tgt_clean = clean_lang_code(tgt_tag)
            
            new_ocr = WinOcrEngine(src_tag)
            
            model_path = os.path.join(self.model_dir, f"{src_clean}-{tgt_clean}")
            if os.path.exists(os.path.join(model_path, "model.bin")):
                try:
                    new_translator = CTranslate2Translator(model_path, src_clean, tgt_clean)
                    status_text = "● Offline Model"
                    status_color = "#55FF55"
                except Exception as e:
                    print(f"Failed to load CTranslate2 translator: {e}. Falling back to Mock.", file=sys.stderr)
                    new_translator = MockTranslator()
                    status_text = f"● Mock (Error: {src_clean}-{tgt_clean})"
                    status_color = "#FF9933"
            else:
                new_translator = MockTranslator()
                status_text = f"● Mock (Missing: {src_clean}-{tgt_clean})"
                status_color = "#FF9933"
                
            with self.lock:
                old_ocr = self.ocr
                old_translator = self.translator
                self.ocr = new_ocr
                self.translator = new_translator
                self.src_lang = src_tag
                self.tgt_lang = tgt_tag
                
            if old_translator:
                old_translator.close()
                
            self.window.after(0, lambda: self.status_indicator.config(text=status_text, fg=status_color))
        except Exception as e:
            error_msg = f"Failed to load language {src_tag}: {e}"
            print(error_msg, file=sys.stderr)
            if first_load:
                raise
            else:
                self.window.after(0, lambda msg=error_msg: msgbox.showerror("Error Swapping Language", msg))
                self.window.after(0, lambda: self.status_indicator.config(text="● Load Error", fg="#FF5555"))

    def update(self, source_text: str, translated_text: str) -> None:
        """Updates the labels in the overlay with new texts."""
        if len(source_text) > 120:
            source_text = source_text[:117] + "..."
        self.src_label.config(text=source_text)
        self.tgt_label.config(text=translated_text)

    def close(self) -> None:
        """Destroys the overlay window and stops the Tkinter event loop."""
        self.window.destroy()
        self.root.quit()
