#!/bin/bash
set -e

python3 << 'PYEOF'
import json
import cv2
import numpy as np
from pathlib import Path
from collections import Counter

VIDEO_PATH = Path("/root/input.mp4")
OUT = Path("/root")

# --- Configuration ---
SAMPLE_FPS = 5.0
FLOW_DEV_FLOOR = 1.0
MOTION_PIX_THRESH = 8.0
STILL_PIX_THRESH = 3.0
RANSAC_REPROJ = 5.0
BORDER_CROP = 20
MIN_FEATURES = 10

# ===================== Frame Sampling =====================

def extract_frames(vpath, fps):
    cap = cv2.VideoCapture(str(vpath))
    native_fps = cap.get(cv2.CAP_PROP_FPS)
    step = max(1, int(native_fps / fps))
    imgs, idxs, n = [], [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if n % step == 0:
            imgs.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            idxs.append(n)
        n += 1
    cap.release()
    return imgs, idxs

# ===================== Optical Flow =====================

def dense_flow(a, b):
    return cv2.calcOpticalFlowFarneback(
        a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)

# ===================== Homography =====================

def find_homography(a, b):
    det = cv2.ORB_create(500)
    k1, d1 = det.detectAndCompute(a, None)
    k2, d2 = det.detectAndCompute(b, None)
    if d1 is None or d2 is None:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(matches) < MIN_FEATURES:
        return None
    matches = sorted(matches, key=lambda m: m.distance)
    src = np.float32([k1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([k2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, RANSAC_REPROJ)
    return H

def project_flow(H, h, w):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ones = np.ones((h, w), np.float32)
    pts = np.stack([xs, ys, ones], -1).reshape(-1, 3)
    t = (pts @ H.T).reshape(h, w, 3)
    tx = t[..., 0] / (t[..., 2] + 1e-8)
    ty = t[..., 1] / (t[..., 2] + 1e-8)
    return np.stack([tx - xs, ty - ys], -1)

# ===================== Dynamic Mask Detection =====================

def spatial_weights(h, w):
    wt = np.ones((h, w), np.float32)
    for y in range(h):
        if y > h * 0.7:
            wt[y, :] *= 0.3
        elif y > h * 0.5:
            wt[y, :] *= 0.7
    for x in range(w):
        if x < w * 0.2:
            wt[:, x] *= 0.5
    return wt

def detect_moving_pixels(flow, H, h, w):
    if H is not None:
        bg_flow = project_flow(H, h, w)
        rx = flow[..., 0] - bg_flow[..., 0]
        ry = flow[..., 1] - bg_flow[..., 1]
    else:
        rx = flow[..., 0] - np.median(flow[..., 0])
        ry = flow[..., 1] - np.median(flow[..., 1])

    mag = np.sqrt(rx**2 + ry**2)
    mag *= spatial_weights(h, w)

    cut = max(FLOW_DEV_FLOOR, np.std(mag) * 2.5)
    mask = mag > cut

    # crop border
    border = np.zeros((h, w), bool)
    border[BORDER_CROP:h-BORDER_CROP, BORDER_CROP:w-BORDER_CROP] = True
    mask &= border

    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    nl, lbl, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    area_min = h * w * 0.0008
    clean = np.zeros_like(mask, dtype=bool)
    for c in range(1, nl):
        if stats[c, cv2.CC_STAT_AREA] >= area_min:
            clean[lbl == c] = True
    if clean.sum() == 0 and mask.sum() > 0:
        return mask.astype(bool)
    return clean

# ===================== Temporal Tracker =====================

class MaskTracker:
    def __init__(self):
        self.prev = None
        self.conf = None

    def step(self, cur_mask, flow):
        h, w = cur_mask.shape
        if self.prev is None:
            self.prev = cur_mask.astype(np.float32)
            self.conf = cur_mask.astype(np.float32)
            return cur_mask

        xs, ys = np.meshgrid(np.arange(w), np.arange(h))
        mx = (xs + flow[..., 0]).astype(np.float32)
        my = (ys + flow[..., 1]).astype(np.float32)

        wp = cv2.remap(self.prev, mx, my, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        wc = cv2.remap(self.conf, mx, my, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        cf = cur_mask.astype(np.float32)
        blend = cf * 0.6 + wp * 0.7 * 0.4
        self.conf = np.maximum(cf, wc * 0.7)
        out = (blend > 0.3).astype(np.uint8)
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        self.prev = out.astype(np.float32)
        return out.astype(bool)

# ===================== Motion Classification =====================

def _scale_ratio(H, h, w):
    if H is None:
        return 1.0
    cx, cy = w / 2, h / 2
    corners = np.array([
        [cx - w/4, cy - h/4, 1],
        [cx + w/4, cy - h/4, 1],
        [cx - w/4, cy + h/4, 1],
        [cx + w/4, cy + h/4, 1]], np.float32)
    t = corners @ H.T
    npts = t[:, :2] / (t[:, 2:3] + 1e-8)
    od = np.sqrt((corners[:, 0]-cx)**2 + (corners[:, 1]-cy)**2)
    nd = np.sqrt((npts[:, 0]-cx)**2 + (npts[:, 1]-cy)**2)
    return float(np.mean(nd / (od + 1e-8)))

def _translation(H, h, w):
    if H is None:
        return 0.0, 0.0
    cx, cy = w / 2, h / 2
    p = np.array([[cx, cy, 1.0]])
    t = p @ H.T
    return float(t[0, 0]/(t[0, 2]+1e-8) - cx), float(t[0, 1]/(t[0, 2]+1e-8) - cy)

def label_motion(H, h, w):
    if H is None:
        return ["Stay"]
    sc = _scale_ratio(H, h, w)
    dx, dy = _translation(H, h, w)
    if np.sqrt(dx**2+dy**2) < STILL_PIX_THRESH and abs(sc-1) < 0.02:
        return ["Stay"]
    tags = []
    if sc > 1.01:
        tags.append("Dolly In")
    elif sc < 0.99:
        tags.append("Dolly Out")
    if abs(dx) > MOTION_PIX_THRESH:
        tags.append("Pan Left" if dx > 0 else "Pan Right")
    if abs(dy) > MOTION_PIX_THRESH * 1.5:
        tags.append("Tilt Up" if dy > 0 else "Tilt Down")
    return tags or ["Stay"]

def smooth_labels(seq, win=3):
    n = len(seq)
    out = []
    for i in range(n):
        lo, hi = max(0, i - win//2), min(n, i + win//2 + 1)
        pool = []
        for j in range(lo, hi):
            pool.extend(seq[j])
        cnt = Counter(pool)
        half = (hi - lo) / 2
        voted = [l for l, c in cnt.items() if c >= half]
        if not voted:
            voted = [cnt.most_common(1)[0][0]]
        out.append(sorted(voted))
    return out

def build_intervals(seq):
    if not seq:
        return {}
    mapping = {}
    start = 0
    prev = tuple(sorted(seq[0]))
    for i in range(1, len(seq)):
        cur = tuple(sorted(seq[i]))
        if cur != prev:
            mapping[f"{start}->{i}"] = list(prev)
            start = i
            prev = cur
    mapping[f"{start}->{len(seq)}"] = list(prev)
    return mapping

# ===================== Sparse Mask IO =====================

def write_sparse_masks(masks, dims, dest):
    blob = {'shape': np.array(dims)}
    for i, m in enumerate(masks):
        rs, cs = np.where(m)
        blob[f'f_{i}_data'] = np.ones(len(rs), dtype=bool)
        blob[f'f_{i}_indices'] = cs.astype(np.int32)
        ip = np.zeros(dims[0] + 1, np.int32)
        for r in rs:
            ip[r + 1:] += 1
        blob[f'f_{i}_indptr'] = ip
    np.savez_compressed(dest, **blob)

# ===================== Main Pipeline =====================

print("Extracting sampled frames...")
frames, _, = extract_frames(VIDEO_PATH, SAMPLE_FPS)
print(f"Got {len(frames)} frames")
assert len(frames) >= 2, "Video too short"

h, w = frames[0].shape

tracker = MaskTracker()
all_masks = []
per_frame_labels = []

for i in range(len(frames) - 1):
    fl = dense_flow(frames[i], frames[i + 1])
    H = find_homography(frames[i], frames[i + 1])

    raw = detect_moving_pixels(fl, H, h, w)
    refined = tracker.step(raw, fl)
    all_masks.append(refined)
    per_frame_labels.append(label_motion(H, h, w))

# duplicate last
per_frame_labels.append(per_frame_labels[-1])
all_masks.append(all_masks[-1].copy())

smoothed = smooth_labels(per_frame_labels, win=3)
intervals = build_intervals(smoothed)

print("Intervals:")
for k, v in sorted(intervals.items(), key=lambda x: int(x[0].split("->")[0])):
    print(f"  {k}: {v}")

# Save outputs
with open(OUT / "camera_motion.json", "w") as fh:
    json.dump(intervals, fh, indent=2)

write_sparse_masks(all_masks, (h, w), OUT / "moving_objects.npz")
print("Done.")
PYEOF
