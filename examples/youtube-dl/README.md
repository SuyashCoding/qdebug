# A harder real bug: youtube-dl

This folder only holds the recipe ([Dockerfile](Dockerfile) and [demo.sh](demo.sh)). The youtube-dl code
itself is downloaded from GitHub when you build the container:

- **buggy:** [`2c6da7d`](https://github.com/ytdl-org/youtube-dl/tree/2c6da7df4a4d69ec933688e3c53795fd3436a1c6)
  (2016), plus `test/test_YoutubeDL.py` from the fix, which adds the test that shows the bug. This is how
  [BugsInPy](https://github.com/soarsmu/BugsInPy) sets up its bug 24 of youtube-dl.
- **fixed:** [`e5a088d`](https://github.com/ytdl-org/youtube-dl/commit/e5a088dc4be4fdcc96927a9f1b7284d4cd49c415),
  the developers' fix, used only by `demo watch` to answer the questions automatically.

The bug and the step-by-step walkthrough are in the main [README](../../README.md#4-a-harder-one-youtube-dl).

youtube-dl is released into the public domain (the Unlicense).
