"""Computer-vision pipeline for fridge images sent by the ESP32-CAMs.

Stages, each in its own module:
    preprocess  -> clean and enhance the raw image, reject black/corrupted ones (OpenCV)
    detector    -> find the products in the image (YOLO)
    ocr         -> read brand names from each detected product (Tesseract)
    pipeline    -> runs the stages in order for one uploaded image
"""
