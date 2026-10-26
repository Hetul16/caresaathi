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
