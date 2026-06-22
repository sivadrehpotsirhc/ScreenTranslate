import mss
from PIL import Image

class ScreenCapturer:
    """Handles high-speed screen capture of specific regions using the mss library."""
    
    def __init__(self):
        self._sct = mss.mss()

    def capture_region(self, bbox: tuple[int, int, int, int]) -> Image.Image:
        """
        Captures a specific bounding box on the screen.
        
        Args:
            bbox: A tuple of (left, top, width, height) in screen coordinates.
            
        Returns:
            A PIL Image object in RGB mode.
        """
        left, top, width, height = bbox
        monitor = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height)
        }
        
        # Grab the frame from the screen
        sct_img = self._sct.grab(monitor)
        
        # sct_img.rgb returns the raw RGB pixel data (converting from internal BGRA)
        img = Image.frombytes("RGB", (sct_img.width, sct_img.height), sct_img.rgb)
        return img

    def close(self) -> None:
        """Closes the mss instance to free resources."""
        if self._sct:
            self._sct.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
