# Reference images

The YOLOE visual-prompt workflow expects these local reference files in this folder:

- `ball_front.jpg`
- `ball_back.jpg`
- `wheel.jpg`
- `prompt.jpg`

`prompt.json` and `targets.json` are already included in the repository.

The four JPG files are binary project assets. If you cloned the repository from GitHub and they are not present, copy them from the complete project ZIP into this `references` folder before launching the tracker.

The required runtime path is especially important for `prompt.jpg`, because `detector.py` loads it when preparing the YOLOE visual prompt.
