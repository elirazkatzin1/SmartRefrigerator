"""Where the cameras' views overlap, so a product seen by two cameras is counted once.

Measured on door event 0016_749423be91ecfe8a (27/11/2026), after the cameras were mounted:
- Upper shelf: camera 4 sees its left part (lettuce, butter, mayonnaise) and camera 1 its right part
  (cream cheese, eggs, Rich's). The mustard jar between them is at camera 4's right edge and at
  camera 1's left edge.
- Lower shelf: camera 2 sees its left part (milk, sauce bottles, peppers) and camera 3 its right part
  (grape juice, garlic sauce, tomatoes, carrots). The ketchup is at camera 2's right edge and at
  camera 3's left edge.
The two shelves don't overlap. Measure again if a camera is moved or turned.
"""
from dataclasses import dataclass

# The width of the cameras' frames (FRAMESIZE_SVGA in the firmware), to turn box pixels into a fraction
FRAME_WIDTH = 800


@dataclass(frozen=True)
class Overlap:
    """Two cameras that see the same strip of the fridge.

    zones maps each of the two cameras to the horizontal range of its image, as a fraction of the
    width from 0 (left) to 1 (right), in which it sees that strip. A detection whose box center is
    in that range may also be seen by the other camera.
    """
    zones: dict[int, tuple[float, float]]


CAMERA_OVERLAPS = (
    # Upper shelf, around the mustard
    Overlap(zones={4: (0.85, 1.0), 1: (0.0, 0.13)}),
    # Lower shelf, around the ketchup
    Overlap(zones={2: (0.72, 1.0), 3: (0.0, 0.10)}),
)
