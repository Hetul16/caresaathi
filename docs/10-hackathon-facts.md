# Hackathon and platform facts

Checked on Oct 24, 2026 against Meta's and Cerebral Valley's pages. Re-check anything marked unverified. Models, prices and credits can change.

## Event facts

| Item | Fact |
| --- | --- |
| Name | Meta Global AI Developer Hackathon, hosted by Meta and Cerebral Valley |
| Format | Virtual and remote, worldwide. Free for selected participants |
| Spots | Up to 20,000 accepted applicants, reviewed on a rolling basis. May close early |
| Application review | Two equal criteria: project idea (clarity, feasibility, theme fit) and technical skill shown in the described AI project. Only the form answers are used; GitHub, LinkedIn or shipped-product links are optional |
| Tracks | Indie developer (individual builders and students; judged on creativity, technical ambition, and whether it works). Startup (teams and founders; judged on technical execution and whether it holds up in production). Each project enters one track |
| Themes | Build for Your World; Push the Frontier |
| Prizes | $1,000,000 total, split across the two tracks. No per-place breakdown is published |
| Required technology | Projects are built with Meta's models: Muse Spark series, Muse Wonder, Muse Image and SAM 3.1 via the Meta Model API, Meta open-weights models, and Muse Code |
| Partners | Baseten ($100 credits for select participants), Modal ($100), Fireworks ($25 plus a workshop) |
| Eligibility | Open worldwide except sanctioned regions and persons, and listed countries (Belarus, China, Russia, Ukraine, Syria and other comprehensively sanctioned regions). Meta and Cerebral Valley staff, government-affiliated individuals and their families are excluded. India is not excluded |
| Rules | Official Rules were to be published before Oct 26 and must be accepted by selected participants. The owner pasted a rules summary on Oct 26 (not independently verified); see `18-rules-and-compliance.md`. Dates can change at Meta's discretion |

## Timeline (ET to IST)

US daylight saving time ends on Nov 1, 2026, so ET is UTC-4 until then and UTC-5 after. Event times are assumed to be ET.

| Event | ET | IST |
| --- | --- | --- |
| Applications opened | Oct 13, 9:00 AM | Oct 13, about 6:30 PM |
| Application deadline | Oct 25, 11:59 PM | Oct 26, about 9:29 AM |
| Kickoff and build starts | Oct 26, 12:00 PM | Oct 26, about 9:30 PM |
| Workshops and Discord office hours | Oct 27 to Nov 4 | Same dates |
| Submission deadline | Nov 4, 9:00 PM | Nov 5, 7:30 AM |
| Judging | Nov 4 to 8 | Same dates |
| Closing ceremony, live finals, winners | Nov 9 | Same date |

## Platform facts (Meta Model API)

Base URL: `https://api.meta.ai/v1`. Docs: https://dev.meta.ai/docs

| Model | ID | Facts |
| --- | --- | --- |
| Muse Spark | `muse-spark-1.3` (also 1.2, 1.1; Contributor variants `1.3-contributor`, `1.2-contributor`) | Context window 1,048,576 tokens; parallel tool calls; streamed tool-call arguments; pay-as-you-go; Contributor mode is discounted. The docs page does not state the hosted model's input modalities |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` | Audio to transcript with turn timing and optional speaker labels; 25 evaluated languages with code-switching; diarization for 20+ speakers on non-overlapping speech; $3.00 per 1,000 minutes ($0.18 per hour); speech to text only, no speech synthesis |
| SAM 3.1 | `sam-3.1` | Text prompt, image or video in; boxes and masks out; priced per frame |
| Muse Image | `muse-image-1.0` | Text to image and image edits; priced per image |
| Muse Wonder | `muse-wonder-1.0` (preview) | 1M-token context; parallel tool calls; delegates to sub-agents |
| Muse Spark Open | open weights, self-hosted | 816B mixture-of-experts (42B active); reads text, images, audio and video; not on the Model API |
| Muse Glimmer | open weights, self-hosted | Distilled from Spark for local and edge use; Apache 2.0; not on the Model API |

### Muse Voice Transcribe details

- Endpoints: streaming `wss://api.meta.ai/v1/asr/realtime`; file `https://api.meta.ai/v1/asr/transcribe`.
- Modes: `PUSH_TO_TALK` (default), `ENDPOINTING`, `DIARIZATION`. The mode is fixed at the handshake and cannot change mid-session.
- Speaker labels are bare letters ("A", "B"). Correlate turn events by `turnId`, not arrival order.
- Audio: mono 16-bit PCM at 24 kHz (native) or 16 kHz. Convert other formats first (for example with ffmpeg).
- `keywords` and `languageBias` hints do not guarantee spelling.
- Published results: streaming WER 3.1% and average diarization error rate 17.5%, without named languages for the WER and without Indian-language benchmarks. Meta recommends testing with your own audio and accents.

### Muse Voice Transcribe file endpoint: request and response (read from dev.meta.ai on Oct 27, 2026; NOT yet called)

Sources: `dev.meta.ai/docs/speech-to-text` and `/docs/api-reference/voice/transcribe`.

- `POST https://api.meta.ai/v1/asr/transcribe?sessionId=<optional>`, header `Authorization: Bearer <key>`, `Accept: application/json` for one buffered reply.
- Body is `multipart/form-data` with two parts: `request`, JSON with `{"mode":"DIARIZATION","model":"muse-voice-transcribe-1.0","audioEncoding":"WAV"}`, and `audio`, the clip.
- Audio must be a RIFF/WAVE container, mono, 16-bit integer PCM at 16 or 24 kHz. Limits: 32 MB (413 above) and 10 minutes (400 above). Convert anything else first.
- The reply carries `sessionId`, `transcript`, `audioDurationMs` and `turns[]` of `{turnId, startMs, endMs, transcript, speaker}`. `speaker` is a bare letter and appears only in `DIARIZATION`; `turns` is empty in `PUSH_TO_TALK`; there are no word-level timestamps.
- Not stated in what was read: the request field names for a language hint and keywords. The client sends neither. Check the Voice schemas page (`/docs/api-reference/voice/schemas`) before relying on them.
- Implemented in `backend/app/clients/models.py` (`LiveModelClient.transcribe_audio`) and `backend/app/safety/audio.py` (the browser records exactly this WAV). Run `backend/scripts/live_smoke.py --audio V1 <file.wav>` for real numbers.

### First live measurements with Muse Spark (Oct 28, 2026; contributor model, synthetic data only; total spend about $0.10)

- Endpoint, key and `muse-spark-1.3-contributor` work. Images (data URL) and PDFs (inline `file` part) are accepted on Chat Completions.
- **Reasoning is billed as output and slow by default.** One trivial judge call took 37 s and 4,367 output tokens. `reasoning_effort` (`minimal` to `max`; `none` is rejected for Spark) fixes it: judge calls now take about 3 s. `max_tokens` counts reasoning too (a limit of 5 returned empty content). Settings: `EFFORT_READ=low`, `EFFORT_JUDGE=minimal`, `EFFORT_WORD=minimal`.
- Prices (dev.meta.ai/docs/pricing-rate-limits): contributor $0.10 in / $0.20 out per 1M tokens; standard $1.25 / $4.25; Voice Transcribe $0.18 per audio hour; rate limit for contributor 150 requests/min.
- **Second-pass judge:** caught 40 of 40 reassuring or advising drafts (including the 4 paraphrases the keyword guard misses and Hinglish), and flagged 0 of 8 plain read-backs and questions.
- **Document reading (7 documents, photo and PDF, 14 files):** 14 of 14 exact on medicines and schedules after one prompt fix (the first run was 8 of 14 because `frequency_text` was sometimes left out). The ambiguous-strength page (R7) is read as the clear medicine plus the smudge note in `unreadable` only some of the time; that case is the two-reader check's job.
- **Visit extraction:** forcing the `visit.v1` JSON schema made the live model return empty results in 3 of 4 runs. A prompt with an example and temperature 0, no schema, gave the right items in 4 of 4. Code still validates. About 20 s per visit.
- **Hindi/Marathi wording** is correct but stiff. Not yet reviewed by a native speaker.
- **Found by testing in the website (Oct 28):** forcing the `extract.v1` schema also failed on a clear allergy card once: the live model returned `unreadable: "Tool call is pending"` and no allergy, so the penicillin check could not have fired. The document reader now uses an example prompt, temperature 0 and one retry, like the visit reader. Re-measured: allergy card 3 of 3; 12 of 14 files exact, the 2 misses are the smudged-strength page (R7), which the model now declines to extract and notes as unreadable (safe, but the medicine is absent from the plan).
- **Not yet measured:** Voice Transcribe (needs a real recorded WAV), Marathi/Hindi speech accuracy, the whole flow through the website in live mode.

### Label check and care crew, live (Oct 28, 2026)

- **Label reader (Muse Spark vision, 5 synthetic pictures from `data/synthetic/render_labels.py`):** 5 of 5 read correctly: two strips (5 mg and 10 mg, batch and expiry), two boxes with a brand and an ingredient, and a loose pill with no text, which came back as `loose_pill_without_text: true` with empty lists (the refusal case). About 6 to 7 s and 400 to 800 output tokens each. Not yet tried on real, blurred or curved packaging photos.
- **Care crew planner:** the live model picked the right tool in the right order for a visit-prep goal in 7 of 7 steps (about 2.5 s and 150 tokens a step). If its answer cannot be used, the code falls back to a fixed plan.

### Whole-flow live run through the API (Oct 29, 2026)

- Allergy card, clinic prescription and a second doctor's prescription uploaded as photos by a new user: all three read (17 to 49 s each). The plan listed 5 medicines with schedules, the penicillin allergy was recorded, and the Amoxicillin line raised a `drug_family` conflict found by code, with a drafted question. The care crew ran 5 steps and built the brief. About $0.002 for the three documents.
- **A second failure the earlier smoke test missed:** the allergy card was read correctly but the reader labelled it `doc_type: "allergy_card"`, which is not an allowed value, so the whole extraction failed validation and the allergy was lost (the document showed "needs review" and allergies "not recorded"). The smoke test only compared medicines, so it passed. Fix: `app/clients/repair.py` maps unknown labels to neutral values before validation (never invents a fact), plus a retry that tells the model what was wrong; 6 tests. After the fix the same flow recorded the allergy. Lesson: measure the whole pipeline, not one field.

### Muse Voice Transcribe on real Hindi and Marathi speech (Oct 31, 2026)

- **Test set:** the first 20 clips of the public Google FLEURS test split (CC BY 4.0) for each language: real human voices reading sentences, with reference text. Scripts: `backend/scripts/speech_eval.py`. This is read speech, NOT a doctor-visit conversation, so it shows how well the model hears the two languages, not how well it follows a Hinglish consultation. Cost about $0.05.
- **Format fact:** the endpoint accepts only mono 16-bit PCM WAV at 16 or 24 kHz and says so in its error (HTTP 400). FLEURS files are 32-bit float WAV, so they are converted first. The in-app recorder already writes the accepted format.
- **English:** the first 20 clips of the FLEURS US English test split: about 8% word errors (5% character errors); telling the model the language made no difference. FLEURS references spell out numbers and punctuation differently from the model, so some of these errors are formatting, not mishearing. A plain-English scripted visit (V4) was also read by the live model three times: the chest-pain warning and the follow-up were found each time, and no medicine change was invented (3 of 3).
- **Hindi:** word error rate about 10% (character errors about 5%), with or without telling the model the language.
- **Marathi:** about 57% word errors (40% character errors) when the language is not given. Some output came back in the wrong script (Gujarati). With the documented `languageBias: ["Marathi"]` request field it fell to about 23% word errors (8% character errors). That is usable but still about one word in four wrong, so Marathi speech input is treated as experimental. The app now sends `languageBias` from the visit's language (chosen by the family) for Hindi, Marathi and English.
- **Doc facts (dev.meta.ai/docs/api-reference/voice/schemas):** request fields are `model`, `audioEncoding`, `mode`, `keywords` (bias toward terms), `languageBias` (language names), `partialMode`, `emitAudioProgress`. There is no `language` or `locale` field. Accepted language names beyond "English" and "French" are not listed on that page; "Hindi" and "Marathi" worked in practice.
- **Still not measured:** a real Hinglish doctor-visit conversation recorded by a person (needs the V1 script read aloud), and Marathi speech with medical vocabulary.

### Whole-product browser run against the live model (Oct 31, 2026)

- A scripted browser walked the demo video's path (26 checks: three photos, flags, label check, two-reader choice, care crew with approval, doctor window and reply, reply read into a follow-up, outcomes answer, visit, confirm, picture schedule, elder mode, Emergency Card revoke, Trust page). The first runs found two real defects, both fixed in D-57: a missed allergy conflict when the allergy card and a prescription were processed at the same time, and clumsy live wording of the allergy question that leaked an internal label. Three of the early failures were the test's own timing and letter-case checks, not product faults.

### A leg-and-back set, and a gap it exposed (Oct 31, 2026)

- New fictional set `data/synthetic/sunita/` (allergy card with an NSAID class allergy, orthopaedic prescription, MRI lumbar spine report, physiotherapy plan with written warning signs, a second doctor's Diclofenac with a second paracetamol brand, lab report). Read as photos by the live model: all six read; the NSAID class allergy was recorded; Diclofenac was flagged as a drug-family match by code; the two paracetamol brands raised the duplicate question; both written warning signs got their levels from the page's own words; follow-ups in 1, 2 and 4 weeks were found.
- **Gap found:** the MRI and lab report produced no plan items at all, because the reader prompt only asked for medicines, warnings, follow-ups and allergies, so those two documents were marked "needs review". The prompt now tells the reader to copy each measured value and each findings or impression line as a `result` item without interpreting it. Re-read: 4 imaging findings and 3 lab values, each with its source, and the lab values are shown as printed with their printed reference range, never as normal or abnormal.

### Remote-care rehearsal on the live model (Oct 31, 2026)

- Six fictional leg-and-back photos, the Diclofenac strip, a loose pill, a speakerphone visit (V5), Today and Tasks were run through the API in live mode. Findings fixed on the way: (1) a physiotherapy plan's emergency instruction was held for low confidence in one run and never reached the plan; held lines now become pending changes with their page line, so a person decides; (2) a strip printed "Diclofenac Sodium" did not match "Diclofenac", so trailing salt words are now dropped from names; (3) the live model labelled "keep taking it" lines in a visit as new medicines, so scripted visits now replay their recorded extraction (D-60) while real recordings still go to the model.

## Verified, unverified and open

| Item | Status | Next step |
| --- | --- | --- |
| Dates, tracks, judging criteria, eligibility | Verified on Meta's event page | None |
| Hindi in the validated language set | Verified | None |
| Marathi speech recognition | Unverified. Not named in the sources checked | Test real Marathi clips on the first day of API access |
| Hinglish code-switching quality | Unverified. Examples given are Mandarin-English | Test with the mock Hinglish visits |
| Diarization with overlapping speakers | Known limitation | Use clean mock visits; say so in the README |
| No text-to-speech from Meta | Verified | Choose an external TTS, D-08 |
| Hosted Spark 1.3 accepting images, PDFs, video | Unverified | Test on Day 1 with 3 documents |
| $150 participant credits | Unconfirmed. Only a third-party page reports it, and says terms will come later | Check the account dashboard and Official Rules |
| Spark 1.3 pricing ($1.25 and $4.25 per million tokens) | Unconfirmed. From a third-party listing | Check the pricing page |
| WhatsApp test-number limits and template rules | Not checked | Read Meta's WhatsApp Cloud API docs |
| Meta glasses toolkit (Wearables Device Access Toolkit 1.0, display-glasses web apps) | Researched Oct 26: extends a mobile app; availability limited to supported countries, India not confirmed | Dropped from scope (D-33). No action |
| Rules on AI coding assistants and ownership | Not in the pasted summary | Read the full Official Rules and update D-15 |
| Demo video length (3 minutes), public repo, new work only, banned project types, Nov 4 9:00 PM ET deadline | From the owner-pasted rules, Oct 26 | Confirm against the full Official Rules; ask the organizers about D-24 and D-25 |
| Insurance claim documents (generic list) and 30-day settlement period | Two consumer articles (general guidance, one dated 2021). Not insurer-specific | Treat as a checklist template only; the family enters policy deadlines (D-28) |

## Model and event updates (Meta Connect recap, Sept 2026)

- The Meta Model API is described as generally available globally, and the hackathon as a ten-day virtual event with free Model API credits (amount unconfirmed).
- Muse Code is out of beta on Windows. Muse Glimmer is a 30B open-weights model for a single GPU or Mac Mini (its input modalities are not checked).

## Sources

- Meta Global AI Developer Hackathon (Cerebral Valley): https://cerebralvalley.ai/e/meta-ai-developer-hackathon
- Meta event page: https://dev.meta.ai/events/global-hackathon
- Meta Model API overview: https://dev.meta.ai/docs/overview
- Introducing Muse Voice Transcribe: https://research.meta.ai/blog/introducing-muse-voice-transcribe
- Meet Muse Voice Transcribe (dev blog): https://dev.meta.ai/resources/blog/meet-muse-voice-transcribe-streaming-speech-to-text
- Participant credits report (third-party, unconfirmed): https://coursejoiner.com/hackathon/meta-global-hackathon-2026-1/
- Meta Connect 2026 recap: https://developers.meta.com/blog/meta-connect-recap/
- Meta Wearables Device Access Toolkit FAQ: https://developers.meta.com/wearables/faq
- Outlook Money, medical reimbursement documentation: https://www.outlookmoney.com/personal-finance/medical-reimbursement-claims-heres-how-to-document-everything-to-avoid-rejections
- SBI General, how to fill an insurance claim form: https://www.sbigeneral.in/blog/health-insurance/health-gi-simplified/how-to-fill-insurance-claim-form
