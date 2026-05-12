In this task, you are given a screen recording of a Super Mario game session. Your goal is to perform a game replay analysis by extracting keyframes, processing them, and counting only **collectibles (coins)** and **hazards (turtles)** visible in each frame. Write the results to a CSV file at `/root/replay_analysis.csv`.

Step 1. The video file is located at `/root/super-mario.mp4`. Extract the I-frames (keyframes) from the video and save them as `/root/keyframes_001.png`, `/root/keyframes_002.png`, etc., in timeline order.

Step 2. Verify that the template images exist at `/root/coin.png` and `/root/turtle.png`. These serve as reference templates for object detection.

Step 3. Convert each extracted keyframe to grayscale IN-PLACE, overwriting the original color image files.

Step 4. For each grayscale keyframe, use template matching to count the number of coins visible in the frame.

Step 5. Repeat the template matching process to count the number of turtles in each frame.

Step 6. Generate a CSV file at `/root/replay_analysis.csv` with exactly 3 columns: "frame_id", "coins", and "turtles". The frame_id column should contain the keyframe file paths (e.g., `/root/keyframes_001.png`), formatted as `/root/keyframes_%03d.png`. The coins and turtles columns contain the respective counts per frame.
