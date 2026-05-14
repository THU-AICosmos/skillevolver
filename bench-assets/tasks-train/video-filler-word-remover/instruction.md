You have a recorded interview at `/root/input.mp4` that contains many verbal hesitations and filler expressions. Your goal is to produce a polished version of this video by removing those fillers.

Your task has two parts:

1. **Transcribe and identify fillers**: Use speech recognition to transcribe the audio and locate all instances of the following filler words/phrases (with timestamps in seconds):
   - Hesitation sounds: um, uh, hum, hmm, mhm
   - Filler words: like, yeah, so, well, okay, basically
   - Filler phrases: you know, i mean, kind of, I guess

   Save the results to `/root/detected_fillers.json` as a JSON array where each element has:
   - `filler`: the detected filler word/phrase
   - `start_time`: the timestamp in seconds when the filler begins

   Example:
   ```json
   [
     {"filler": "um", "start_time": 3.5},
     {"filler": "you know", "start_time": 25.8}
   ]
   ```

2. **Produce a cleaned video**: Remove all detected filler segments from the original video and concatenate the remaining (non-filler) portions into a single cleaned video saved at `/root/cleaned.mp4`. The cleaned video should contain only the meaningful speech with fillers cut out.
