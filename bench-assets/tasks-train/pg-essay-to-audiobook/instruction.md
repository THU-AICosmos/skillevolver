I'd like you to grab some Wikipedia articles about computing pioneers and turn them into a podcast-style audio file using text-to-speech.

The articles I want are:
- Alan Turing (https://en.wikipedia.org/wiki/Alan_Turing)
- Grace Hopper (https://en.wikipedia.org/wiki/Grace_Hopper)
- Ada Lovelace (https://en.wikipedia.org/wiki/Ada_Lovelace)

For each article, extract the lead section (the introductory paragraphs before the first heading/table of contents). Don't include the full article - just the introduction.

Use elevenlabs or openai TTS if api-keys are available in the env, otherwise fall back to a local/free TTS solution.

Save the final combined audio to `/root/podcast.mp3`.
