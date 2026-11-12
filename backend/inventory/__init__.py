"""Turning the per-image detections of a door-close event into the fridge inventory.

    event_collector -> wait until all cameras of one event are analyzed (or a timeout)
    merge           -> combine the cameras' detections into one snapshot, without double-counting
    diff            -> classify each product as added / removed / quantity_changed / unchanged
"""
