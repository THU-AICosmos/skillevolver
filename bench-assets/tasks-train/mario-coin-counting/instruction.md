You have a screen recording of a Super Mario gameplay session. Your objective is to extract keyframes from the video, convert them to grayscale, and then detect how many gold coins and shell creatures (turtles) appear in each frame using template matching. You do NOT need to count enemies for this task.

1. The gameplay video is at `/root/super-mario.mp4`. Use ffmpeg to pull out the I-frames (keyframes) and save them as `/root/frame_001.png`, `/root/frame_002.png`, etc. (use the pattern `/root/frame_%03d.png`).

2. Template images for matching are already provided at `/root/coin.png` and `/root/turtle.png`.

3. Convert every extracted keyframe to grayscale IN PLACE, overwriting the original color image.

4. For each grayscale keyframe, use OpenCV template matching to count the number of gold coins and shell creatures visible, using the respective template images.

5. Write all results to `/root/detection_summary.csv` with three columns: `frame`, `gold_coins`, `shell_creatures`. The `frame` column should contain the full path like `/root/frame_001.png`. Rows should be ordered by frame number.
