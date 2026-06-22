from PIL import Image, ImageChops

class ChangeDetector:
    """
    Detects whether a newly captured frame is significantly different from the 
    previous one. This prevents redundant OCR and translation calls.
    """
    
    def __init__(self, threshold: float = 0.02, pixel_delta: int = 10):
        """
        Args:
            threshold: The fraction of pixels (0.0 to 1.0) that must change to trigger a reload.
            pixel_delta: The minimum difference in grayscale intensity (0-255) for a pixel to be considered "changed".
        """
        self.threshold = threshold
        self.pixel_delta = pixel_delta
        self.last_image = None

    def has_changed(self, new_image: Image.Image) -> bool:
        """
        Checks if the new image is significantly different from the last one.
        
        Args:
            new_image: The PIL Image of the screen capture.
            
        Returns:
            True if the image has changed beyond the threshold, False otherwise.
        """
        # Convert to grayscale to remove subpixel sub-rendering noise and color channels
        new_gray = new_image.convert("L")
        
        if self.last_image is None:
            self.last_image = new_gray
            return True
            
        if new_gray.size != self.last_image.size:
            self.last_image = new_gray
            return True
            
        # Calculate absolute difference image
        diff = ImageChops.difference(new_gray, self.last_image)
        
        # Obtain histogram of difference values (0 to 255)
        hist = diff.histogram()
        
        # Sum up all pixels with difference greater than the threshold delta
        # index 0 to pixel_delta represent unchanged/slightly changed pixels
        changed_pixel_count = sum(hist[self.pixel_delta + 1:])
        total_pixels = new_gray.width * new_gray.height
        
        change_ratio = changed_pixel_count / total_pixels
        
        # If the change ratio exceeds our threshold, save the image and notify
        if change_ratio >= self.threshold:
            self.last_image = new_gray
            return True
            
        return False
