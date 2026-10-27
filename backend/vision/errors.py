class ImageRejectedError(Exception):
    """Raised when an image cannot be used for analysis (black, corrupted, unreadable).

    The pipeline catches it, logs the reason and skips the image instead of crashing.
    """
