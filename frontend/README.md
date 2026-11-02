# CareSaathi — the website

Next.js (App Router) front end for CareSaathi. Mobile first, and served over HTTPS in production because the
microphone needs it. The project README, one level up, explains what the product is and why.

```
npm install
npm run dev          # http://localhost:3000, expects the API on http://127.0.0.1:8000
npm run build        # what Vercel runs
npx tsc --noEmit     # types
npm run lint         # clean: keep it that way
```

## How it talks to the API

The browser never calls the API host directly. `next.config.ts` rewrites `/api/*` to `BACKEND_URL`, so every request
is same-origin: the HttpOnly refresh cookie stays first-party, and there is no CORS and no `SameSite=None`.

`src/middleware.ts` adds the `x-site-gate` header to those proxied requests while `SITE_GATE_TOKEN` is set. That is
what keeps the deployment private before submission day; clearing the variable in both Render and Vercel is what
makes it public (`PUBLIC_LAUNCH.md`).

Two server-side environment variables, and neither is ever `NEXT_PUBLIC_*`:

```
BACKEND_URL=https://caresaathi-api.onrender.com
SITE_GATE_TOKEN=<the same value as on the API>
```

## Layout

| Path | What is there |
| --- | --- |
| `src/app/app/` | Family mode, signed in. `app/elder/` is Elder mode for the patient's own sign-in (D-66). |
| `src/app/e/[token]/`, `src/app/d/[token]/` | Emergency Card and doctor link: no account, opened from a random token |
| `src/app/trust/` | The public evidence page, including what failed |
| `src/app/demo/` | The same dashboard on a fixed mock plan, with no backend behind it |
| `src/components/family/` | One panel per tab. Each is given `patientId` and loads its own data. |
| `src/lib/live.ts` | The hooks that hold the care plan and the list of relatives |
| `src/lib/defer.ts` | `afterCommit`: how a panel starts its first load without setting state inside the effect |
| `src/lib/i18n.tsx` | Only the words CareSaathi says to the patient. Family mode is English, on purpose. |

`AGENTS.md` is written by `next dev` itself; committing it is what keeps the working tree clean.

## Four things to know before changing it

**An answer is stored with the thing it is about.** `useCarePlan` keeps `{ id, plan }` together and returns the plan
only while its id still matches the selection; `useVisit` does the same. Switching relative starts a new request
while the old one is in flight, and without that pairing the slower answer wins -- one relative's medicines drawn
under another relative's name. `src/app/app/page.tsx` also renders `<Dashboard key={selected} …>`, so a change of
relative remounts every panel rather than leaving each one to guard the race itself.

**Panels start their first load with `afterCommit`, not by calling it in the effect.** `useEffect(() => { load(); })`
sets state during the effect, which cascades renders; `afterCommit(load)` hands it to a microtask so everything that
follows lands in a later, batched pass. `npm run lint` is clean with the React rules at full strength -- if a change
turns `react-hooks/set-state-in-effect` red again, fix the effect rather than the rule.

**Family mode is written in English.** The language buttons choose what CareSaathi *speaks and writes to the person
being cared for*: Elder mode, the spoken explanations, the chat reply, the printed sheets. Translating ten words of
the family's own dashboard and leaving the other few hundred in English read as broken, so `src/lib/i18n.tsx` holds
only the patient-facing words. Adding a `t(...)` call to anything under `src/components/family/` undoes that.

**Nothing on screen may read as medical advice.** Wording that describes a medicine, a flag or a gap comes from the
API, which has already passed it through the output guard. Do not write such sentences in the components.
