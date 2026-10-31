# End-to-end browser run (live model)

`full_live.mjs` walks the demo video's path in a real Chrome against the running app and the LIVE Meta model: three photos to a plan, the
allergy flag, label check, the two-reader choice, the care crew with approval, the doctor window and reply, reading the reply, the outcomes
answer, a visit, confirming a change, the picture schedule, elder mode, the Emergency Card and its revoke, and the Trust page. 26 checks.

Last full run: Oct 31, 2026, 26 of 26 passed, 0 console errors. It found two real defects on the way (see `docs/09-decisions.md`, D-57).

To run it (fictional data only; costs a few cents):

1. Start the backend with `MODEL_MODE=live` on port 8000 and the website on http://localhost:3000 (not 127.0.0.1).
2. Make the sample pictures: `python data/synthetic/render.py` and `python data/synthetic/render_labels.py`.
3. In a scratch folder: `npm init -y`, `npm i playwright-core`, copy this file in, set the Chrome path and the picture folder at the top, then `node full_live.mjs`.
