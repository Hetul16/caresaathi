# Synthetic data

Everything in this folder is **fictional**. Every name, date, number and organisation is invented, every document carries a
`SYNTHETIC DOCUMENT - FICTIONAL PATIENT` line, and there are no real hospitals, doctors, insurers or brands. No real patient
data may ever be added here (the repository is public).

| Folder | What |
| --- | --- |
| `ramesh/docs` | R1 to R10: the hero patient's documents, each with a planted case |
| `ramesh/visits` | V1 to V4 (V4 is plain English): scripted visits (segments, speakers, and a recorded expected extraction) |
| `ramesh/truth` | `<id>.truth.json`: what the app must find, plus the planted cases |
| `margaret/`, `hans/` | Smaller sets: US pharmacy style and German formats |
| `render.py` | Turns the text documents into PNG photos and PDFs (fixed seeds) for testing the live reader |

## How it is used

- The offline test suite reads the `.txt` files (`backend/tests/test_synthetic_set.py`, `backend/scripts/eval_synthetic.py`).
  The offline reader is a small rule-based stand-in, so those numbers measure the pipeline, not a model.
- `render.py` makes phone-photo style images (tilt, shadow, blur, noise). Those are what the live Muse Spark reader is tested on.
- Visit audio is **not** included. Record the scripts with two real voices (or label any text-to-speech audio as such).
  Without audio, the "mock visit" button replays a script's recorded answer through the same pipeline; it is labeled in the app.
- Hindi, Marathi and German text must be reviewed by a native speaker before it is shown in the demo.
