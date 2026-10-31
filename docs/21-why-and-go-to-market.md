# 21. Why we built CareSaathi, who it is for, and how it reaches them

Date: Oct 31, 2026. Status: a working hackathon build with fictional data only. Everything marked **hypothesis** is untested with real families and must be validated before it is relied on. Numbers from outside sources are listed with their limits in section 13.

## 1. Summary

When an older person leaves a hospital or a clinic, the facts that keep them safe are spread across papers, a conversation, and the memories of family members in different cities. Medicines go missing between two papers, an allergy sits on a card in a drawer, and the doctor's spoken instructions are half forgotten.

CareSaathi (saathi means companion) turns those papers and that conversation into **one living care plan where every line shows its source**, finds mix-ups between documents **in code**, and sends each one to the doctor or pharmacist **as a question**. It keeps the question open until a named person writes down the answer. It explains the plan aloud in the patient's language. It never gives medical advice.

The first customer is the adult child who manages a parent's care from a distance. The product is used at forced moments (a discharge, a visit, a new prescription, a refill, a follow-up), not every day.

## 2. Why we built it

**The problem, in one family.** Ramesh is 72, home in Nashik after a hospital stay, with four papers: an allergy card, a clinic prescription, a discharge summary, and a second doctor's prescription. His daughter Priya lives in Pune. The papers are in English; Ramesh reads Hindi. One document leaves out a medicine the earlier one listed. A new prescription contains a drug in the same family as an allergy written on a card nobody looked at. Nobody has done anything wrong; the information is just in too many places.

**What the evidence says, and its limits.**
- In one hospital study of 339 older adults after an ICU stay, 64% had an unintentional medication discrepancy at some care transition, and 96% of those discrepancies were omissions. Patients with a discrepancy had about twice the risk of an emergency visit within a month (hazard ratio 2.13). It is a single-hospital retrospective study; the abstract and results give slightly different percentages (68% and 64%). It supports the problem, not our solution. We do not claim CareSaathi prevents emergency visits; that has not been measured. (Source in section 13.)
- Studies of patient-generated data suggest possible gains in awareness and communication with clinicians, but the evidence is thin and integration into care is rare. We treat usefulness as a hypothesis to test.

**Why a care-coordination tool and not an advice tool.** A model that answers "is this safe?" can be confidently wrong in a way that hurts someone. The harm in this situation is mostly lost information, not missing intelligence. So the product's job is to keep information together, show where each fact came from, notice gaps between documents, and route every judgement to the person qualified to make it. That choice is also what makes it defensible: it stays out of diagnosis and treatment decisions, and every claim can be checked against a source.

**Why now.**
- Models can now read a tilted phone photo of a prescription and hear a Hindi or Marathi conversation, which were the blockers for a family-facing tool in India.
- Meta's open-weights model Muse Glimmer (Apache 2.0, runs on a single 24 to 32 GB GPU) makes a future private, self-hosted version realistic. (Section 9.)
- Populations are ageing fast and many families are spread across cities and countries.

## 3. Who it is for

| Person | Role | What they need |
| --- | --- | --- |
| **Priya, adult child, often in another city or country** | First user and first payer | One place that is true, with sources; to know what the doctor said; to know what is missing; a way to ask the doctor without a long phone call |
| **Ramesh, the older patient** | Uses voice and the picture schedule | One big button, his own language, large print |
| **Dr. Joshi, the doctor, or a pharmacist** | Free read-only side (the doctor link) | The plan as the papers say it, the family's questions, a way to answer in their own words |
| **A stranger in an emergency** | Reads the Emergency Card | Allergies first, only confirmed facts, when it was last updated |
| **A hospital, home-care agency or insurer** | Later paying customers (hypothesis) | A cleaner discharge handoff, fewer repeat calls, evidence that questions were answered |

**Jobs to be done (Priya's words, paraphrased).** "Tell me what changed." "Tell me what is missing." "Tell me where that came from." "Let me ask the doctor, and make sure someone answers." "Read it to Papa in Hindi."

## 4. What the product is, and is not

**Principles, all enforced in code or in the database and tested** (details: `CLAUDE.md`, `docs/09-decisions.md`):
1. Every plan line has a source: a page and line, or the doctor's exact words.
2. The model reads and drafts; code decides. Allergy matches, missing-medicine checks, dates and refills are computed by code, with their inputs shown.
3. Nothing is called safe. Every flag ends with a question for the doctor or pharmacist.
4. Anything that changes the plan or reaches another person waits for a named person.
5. Unknown is not safe: an unresolved ingredient shows as "could not check".
6. Consent before any recording; links can be revoked; synthetic data only during the hackathon.

**Feature map to the jobs**

| Job | Feature |
| --- | --- |
| What does the paper say? | Photos and PDFs to a sourced care plan; two-reader check when a page is unclear |
| What changed? | What-changed diff; the doctor visit listener with consent |
| What is missing or conflicting? | Allergy match against a drug-family list; omission catch; duplicate-ingredient detector |
| Is this the same medicine? | Label check: reads printed text on a strip or box and compares it with the papers; refuses loose pills |
| Ask the doctor | Doctor link; care crew that prepares a brief and drafts the questions; approval step |
| Did anyone answer? | Outcomes board: each flag is a question until an answer is recorded |
| Tell Papa | Elder mode with spoken explanations; large-print picture schedule; fridge sheet |
| Emergencies | Emergency Card with random-token links and revocation |
| Can we trust it? | Public Trust page with live measurements and failures |

## 5. Why Meta's models, and what we measured

| Model | What it does here | Measured result (fictional data; details and failures at `/trust`) |
| --- | --- | --- |
| Muse Spark | Reads documents and labels from photos; reads visit transcripts; plans the care crew's steps; words the questions; second-pass wording judge | Documents 14 of 14 (earlier run 12 of 14); allergy card recorded 2 of 2; packaging 5 of 5; Hindi visit 3 of 3; English visit 3 of 3; judge caught 40 of 40 unsafe sentences and left 7 of 8 plain ones alone (8 of 8 in an earlier run) |
| Muse Voice Transcribe | Hears the visit, with speaker labels; Hindi, Marathi, English | Word errors on real recordings (public FLEURS test set, read speech, not a consultation): English about 8%, Hindi about 10%, Marathi about 57% falling to 23% once the app tells the model the language |

Two things we learned the hard way, which are part of why the measurements can be trusted: a smoke test that checked only medicines passed while an allergy card was being lost, and forcing the model into a strict output format made it give up. Both are fixed and recorded in `docs/10-hackathon-facts.md`.

## 6. How it differs from what families use today

(Category-level comparison; we have not benchmarked named products.)
- **A notes app or a photo folder:** stores papers, does not connect them, does not notice gaps.
- **A general chatbot:** answers questions, sometimes confidently and wrongly; has no source discipline and no approval step.
- **A hospital patient portal:** shows that hospital's records only, usually in one language, and does not compare them with another doctor's paper.
- **A pill reminder app:** reminds, but does not check the plan against the papers.

CareSaathi's difference is the combination: sources on every line, checks in code, questions that stay open until answered, and Hindi and Marathi voice.

## 7. Positioning

**One sentence.** CareSaathi finds the mix-up between two papers early, asks the doctor, and keeps the question open until someone writes down the answer.

**Statement.** For adult children who manage a parent's medicines from afar, CareSaathi is the care companion that turns every paper and every visit into one plan where each line shows its source. Unlike a chatbot that gives advice, it never judges a medicine: it finds the gap and asks the person who should answer.

**What we say, and what we do not.**
- Say: sourced, asked-not-told, a person approves, built for how families actually share papers, in your language.
- Do not say: safe, prevents emergency visits, replaces a doctor or pharmacist, or that Marathi speech is solved.

## 8. Go to market (hypotheses to validate)

**Wedge: the discharge.** The most forced and highest-stakes moment is the day a patient leaves a hospital. A family that is handed four papers and a prescription is ready to try something that makes sense of them. Start there.

**Channels, in the order I would test them.**
1. **Direct to families** through communities of people whose parents live far away (migrants within a country and abroad), and through word of mouth after the first discharge. Free for one patient.
2. **Doctors and pharmacies as a hand-off:** a printed QR on a discharge summary or a pharmacy bag that opens the app. The doctor link also works as a free pull-through: a doctor who answers one family's question sees the product.
3. **Home-care and nursing agencies:** they manage many patients and share notes between shifts; they have the clearest budget.
4. **Insurers and claim administrators (later):** organized documents and follow-ups matter at claim time; the claim file would be the feature, and it is not built.
5. **WhatsApp:** in India the paper trail already moves on WhatsApp. A WhatsApp entry point is likely the best long-term acquisition channel and is not built.

**Pricing (hypothesis, to test in interviews).** Free for one patient; a family plan for several relatives and a longer history; a per-patient monthly fee for agencies and clinics. Do not set prices before 10 or more conversations with real caregivers.

**Cost to serve (estimate, assumptions stated).** At Meta's published standard prices (input $1.25 and output $4.25 per million tokens; voice $0.18 per hour), reading one document photo takes about 4,000 input and 2,300 output tokens, so roughly 1.5 cents. A 10-minute visit transcript costs about 3 cents. A family that adds five documents and two visits a month would cost roughly 15 to 25 cents in model fees. Our measurements used the cheaper contributor tier, in which Meta may train on prompts; it is for fictional data only and must not be used for real patients. The figures above assume the standard tier. Hosting and support costs are not estimated here.

**Metrics that matter** (and ones that do not).
- Matters: share of flags that get an answer recorded; days to an answer; follow-ups completed; families who return at their next trigger moment (a second discharge, a refill).
- Does not matter: daily active users. The product is used at moments, by design (D-53).

**First 90 days, if this continued after the hackathon.**
1. 10 to 15 interviews with adult-child caregivers; watch three of them use the product with their own (consented) papers under a clinic's or university's ethical guidance.
2. A pharmacist reviews the allergy and drug-family list; a native speaker reviews Hindi and Marathi wording.
3. One pilot with a small clinic or home-care agency, with a written agreement on data handling.
4. Build a WhatsApp entry point and measure speech on a real recorded consultation.

## 9. Going global

**The opportunity (rough, secondary sources).** The population aged 65 and over was about 703 million in 2019 and is projected to reach about 1.5 billion by 2050. India's population aged 60 and over is projected to grow from about 149 million to about 347 million by 2050. One estimate puts India's untrained family caregivers at about 10% of the population; that is an assumption, not a count.

**What has to change in each market.**
1. **Drug data.** Our allergy and drug-family list is a starter list that a pharmacist has not reviewed. Every country needs its own medicine names, brands and codes, reviewed by a pharmacist.
2. **Languages.** Meta documents 25 evaluated languages with code-switching for Voice Transcribe. We measured three. Each new language needs its own measurement before we claim it.
3. **Privacy and consent law.** India, the EU, the US and others differ. We have consent, scoped links, revocation and an audit trail; legal review is needed before real data.
4. **Medical-device rules.** Staying a document-and-questions tool avoids diagnosis and treatment advice. The FDA's 2026 clinical decision support guidance covers clinician-facing tools only and leaves consumer tools uncertain, so this needs legal advice per market.
5. **Document formats and handwriting.** Handwritten prescriptions are common in some markets. Reading them is a good fit for the two-reader check, and is untested.

**Order of expansion (hypothesis).** India in Hindi, Marathi and English; other Indian languages; families abroad with parents in India; English-speaking markets; then further languages as each is measured.

**Privacy-first option.** Muse Glimmer (open weights, Apache 2.0, about 30B parameters, runs on a single 24 to 32 GB GPU per its announcement) makes a self-hosted deployment for a clinic or a country with strict data rules plausible. It is a roadmap item; we have not tested it.

## 10. Roadmap

| When | What |
| --- | --- |
| Hackathon (by Nov 4) | Public link, demo video, final checks. No new features |
| Next 30 days | Pharmacist review of the drug list; native-speaker review of Hindi and Marathi; a real recorded Hinglish consultation measured; WhatsApp entry point; a better read-aloud voice |
| Next 90 days | Pilot with one clinic or agency; handwritten prescription reading, tested and measured; live captions during a visit; "ask across all documents" with exact quotes only; claim file (organizer only, never a prediction) |
| Later | Private self-hosted mode on open-weights models; more Indian languages, each measured first; insurer and hospital integrations |

## 11. Risks and how we handle them

| Risk | What we do |
| --- | --- |
| A wrong answer harms someone | The product gives no medical advice; checks are in code; each flag becomes a question for a professional; a second-pass wording judge fails closed |
| The model misreads a paper | Sources on every line; two-reader check on unclear pages; quote must exist on the page or the line is dropped; we publish misses |
| Over-trust ("the app said it was fine") | It never says fine or safe; the Trust page shows its own failures |
| Privacy of health data | Consent, revocable and expiring links, an audit log, random tokens; synthetic data only now; no real data without legal review |
| Regulation | Stay a documentation and coordination tool; legal review per market before launch |
| Marathi accuracy | Measured and disclosed; labelled experimental |
| Adoption (families may not change habits) | Wedge on a forced moment (discharge); free for one patient; doctor link pulls clinicians in |
| Model cost and supplier dependency | Measured cost per family is small at standard prices; interfaces keep the model replaceable; open-weights option exists |
| Unreviewed drug list | A pharmacist reviews it before any real use; the app shows a banner until then |

## 12. What is not proven

- No real family or clinician has used it. Usefulness, willingness to pay and retention are all unknown.
- No real recorded consultation has been measured; the speech tests are read sentences.
- No real phone photos of packaging or handwriting have been measured.
- The drug-family list is unreviewed by a pharmacist.
- Hindi and Marathi wording is unreviewed by a native speaker.
- Pricing, channels and expansion order are hypotheses.

## 13. Sources and limits

- Medication discrepancies at care transitions (339 older adults, single hospital, retrospective; omissions 96%; hazard ratio 2.13 for an emergency visit within a month): PMC11654400, as recorded in `docs/12-product-requirements.md`.
- Patient-generated health data reviews: https://pmc.ncbi.nlm.nih.gov/articles/PMC7671621 and https://pmc.ncbi.nlm.nih.gov/articles/PMC6438188 (promising, thin evidence, integration limited).
- Ageing and caregiver figures (secondary sources, treat as rough): https://carersworldwide.org/blog/unpaid-carers-in-an-ageing-population and https://organiser.org/2026/09/22/382107/bharat/indian-care-workforce-the-worlds-next-employment-opportunity/
- FDA clinical decision support guidance, 2026 (summary): https://www.cov.com/en/news-and-insights/insights/2026/01/5-key-takeaways-from-fdas-revised-clinical-decision-support-cds-software-guidance
- Muse Glimmer (open weights, Apache 2.0): https://aiweekly.co/alerts/meta-open-sources-muse-glimmer-a-30b-on-device-agent-model
- Meta model facts and prices: https://dev.meta.ai/docs (recorded in `docs/10-hackathon-facts.md`).
- Our own measurements: `data/live_results/latest.json` and the Trust page; method notes in `docs/10-hackathon-facts.md`.
