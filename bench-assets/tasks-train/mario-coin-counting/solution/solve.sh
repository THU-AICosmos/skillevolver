#!/bin/bash

# Step 1: Extract I-frames from the gameplay video
ffmpeg -i /root/super-mario.mp4 \
    -vf "select='eq(pict_type,I)'" -vsync vfr \
    /root/frame_%03d.png

# Step 2: Convert all extracted frames to grayscale in-place
for f in /root/frame_*.png; do
    convert "$f" -colorspace Gray "$f"
done

# Step 3: Run a single Python script that does all template matching and writes the CSV
python3 << 'PYEOF'
import glob
import cv2
import numpy as np
import csv

def count_objects(frame_path, template_path, thresh=0.9):
    frame = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
    tmpl = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if frame is None or tmpl is None:
        return 0
    result = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
    locs = np.where(result >= thresh)
    unique = []
    for pt in zip(*locs[::-1]):
        if not unique or min(np.hypot(pt[0]-p[0], pt[1]-p[1]) for p in unique) > 3:
            unique.append(pt)
    return len(unique)

frames = sorted(glob.glob("/root/frame_*.png"))
with open("/root/detection_summary.csv", "w", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["frame", "gold_coins", "shell_creatures"])
    for fp in frames:
        gc = count_objects(fp, "/root/coin.png")
        sc = count_objects(fp, "/root/turtle.png")
        writer.writerow([fp, gc, sc])
PYEOF
