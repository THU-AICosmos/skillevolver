Analyze the video located at /root/input.mp4 to perform two tasks: classify the camera movement type for each temporal segment and produce a per-frame segmentation of independently moving objects.

Produce two output files:

1. `/root/camera_motion.json` — A JSON object mapping temporal intervals (frame index ranges) to lists of camera movement categories. Use "start->end" as keys (e.g., "0->5") where both start and end are integer sample indices. Each value is a list of one or more applicable motion types from the following set: Stay, Dolly In, Dolly Out, Pan Left, Pan Right, Tilt Up, Tilt Down, Roll Left, Roll Right.

2. `/root/moving_objects.npz` — A compressed NumPy archive containing binary segmentation masks identifying pixels belonging to independently moving objects. The archive must include a "shape" key storing [H, W] (the mask resolution). For each sampled frame i, store the mask in CSR (Compressed Sparse Row) sparse format using keys: `f_{i}_data`, `f_{i}_indices`, and `f_{i}_indptr`. The CSR encoding records which columns are True in each row.

Sample the video at fps = 6.
