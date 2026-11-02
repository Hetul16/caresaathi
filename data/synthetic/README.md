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

- The offline test suite reads the `.txt` files (`backend/tests/test_synthetic_set.py`, and the `extraction_offline` cases in `backend/app/trust/suite.py`).
  The offline reader is a small rule-based stand-in, so those numbers measure the pipeline, not a model.
- `render.py` makes phone-photo style images (tilt, shadow, blur, noise). Those are what the live Muse Spark reader is tested on.
- Visit audio is **not** included. Record the scripts with two real voices (or label any text-to-speech audio as such).
  Without audio, the "mock visit" button replays a script's recorded answer through the same pipeline; it is labeled in the app.
- Hindi, Marathi and German text must be reviewed by a native speaker before it is shown in the demo.

## Sunita Deshmukh (leg and back set, added Oct 31)

A fictional 68-year-old with low back pain going down the left leg. Files in `sunita/docs`: S1 allergy card (an NSAID class allergy), S2 orthopaedic prescription, S3 MRI lumbar spine report, S4 physiotherapy plan with written warning signs, S5 a second doctor's prescription (Diclofenac, which is in the NSAID family, and a second paracetamol brand (Calpol in S2, Dolo in S5)), S6 a lab report. Upload order for the demo: S1, S2, S3, S4, S6, then S5. Expected: a drug-family flag on Diclofenac, a paracetamol duplicate question, written warning signs with levels from the document's own words, follow-ups in 2 and 4 weeks. All of it is fictional and none of it is medical advice. Never upload real family records to the live model: the contributor tier may train on prompts.
