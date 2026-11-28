"""Where the cameras' views overlap, so a product seen by two cameras is counted once.

Measured on door event 0032_98dec90b9e9481a4 (28/11/2026), with the cameras in their final positions
and the images no longer mirrored (firmware sets hmirror):
- Upper shelf: camera 1 sees one part (Rich's, cream cheese) and camera 4 the other (eggs). The mustard,
  mayonnaise and butter between them are at camera 1's right side and at camera 4's left side.
- Lower shelf: camera 2 sees one part (peppers, milk, sauce bottles) and camera 3 the other (tomatoes,
  carrots, grape juice, garlic sauce). The ketchup, cheese, sweet chili and cucumbers between them are at
  camera 2's left side and at camera 3's right side (camera 2 sees all 3 cucumbers, camera 3 two of them).
The two shelves don't overlap. The strips are a little wider than the shared products: a product only
one camera sees inside a strip is still counted, while a shared one outside it would be counted twice.
Measure again if a camera is moved or turned.
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
    # Upper shelf: mustard, mayonnaise, butter
    Overlap(zones={1: (0.70, 1.0), 4: (0.0, 0.35)}),
    # Lower shelf: ketchup, cheese, sweet chili, cucumbers
    Overlap(zones={2: (0.0, 0.30), 3: (0.66, 1.0)}),
)
