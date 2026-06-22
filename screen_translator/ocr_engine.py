import io
import asyncio
from PIL import Image
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import (
    SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode, BitmapDecoder
)
from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

class WinOcrEngine:
    """Wraps Windows.Media.Ocr to perform offline OCR using native language packs."""

    def __init__(self, language_code: str = "ja"):
        """
        Initializes the OCR Engine for the requested language.
        
        Raises:
            RuntimeError: If the specified language pack is not installed on the system.
        """
        lang = Language(language_code)
        
        # Check if the requested language is supported by the installed OCR packs
        if not OcrEngine.is_language_supported(lang):
            available = self.available_languages()
            raise RuntimeError(
                f"Language '{language_code}' is not supported by installed Windows OCR packs.\n"
                f"Available languages: {available}\n"
                f"Please install the Windows Language Pack for '{language_code}' with the OCR component."
            )
            
        self._engine = OcrEngine.try_create_from_language(lang)
        if not self._engine:
            raise RuntimeError(f"Failed to create OcrEngine for language '{language_code}'.")

    async def _image_to_software_bitmap(self, image: Image.Image) -> SoftwareBitmap:
        """
        Converts a Pillow Image into a WinRT SoftwareBitmap object.
        Uses InMemoryRandomAccessStream and BitmapDecoder.
        """
        # 1. Save Pillow image to an in-memory BMP byte buffer
        buf = io.BytesIO()
        image.save(buf, format="BMP")
        bmp_bytes = buf.getvalue()

        # 2. Write bytes into a WinRT InMemoryRandomAccessStream
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(bmp_bytes)
        
        # Await the WinRT operations directly (natively supported in modular winrt packages)
        await writer.store_async()
        await writer.flush_async()
        
        stream.seek(0)

        # 3. Decode via BitmapDecoder
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        
        return software_bitmap

    async def recognize(self, image: Image.Image) -> str:
        """
        Performs OCR on the provided Pillow image.
        
        Args:
            image: PIL Image to run OCR on (must be in RGB mode).
            
        Returns:
            Extracted text as a single space-separated string.
        """
        # Convert image to WinRT SoftwareBitmap
        software_bitmap = await self._image_to_software_bitmap(image)
        
        # Run OCR (native await)
        result = await self._engine.recognize_async(software_bitmap)
        
        # Join lines of text with spaces
        lines = [line.text for line in result.lines]
        return " ".join(lines)

    @staticmethod
    def available_languages() -> list[str]:
        """
        Lists all locally installed language tags available for Windows OCR.
        """
        return [lang.language_tag for lang in OcrEngine.available_recognizer_languages]

    @staticmethod
    def available_languages_detailed() -> list[tuple[str, str]]:
        """
        Lists all locally installed languages with (tag, display_name).
        """
        return [(lang.language_tag, lang.display_name) for lang in OcrEngine.available_recognizer_languages]
