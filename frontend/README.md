# CareSaathi — the website

Next.js (App Router) front end for CareSaathi. Mobile first, and served over HTTPS in production because the
microphone needs it. The project README, one level up, explains what the product is and why.

```
npm install
npm run dev          # http://localhost:3000, expects the API on http://127.0.0.1:8000
npm run build        # what Vercel runs
npx tsc --noEmit     # types
npm run lint
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

`AGENTS.md` is written by `next dev` itself; committing it is what keeps the working tree clean.

## Two things to know before changing it

**Panels are keyed on the selected relative.** `src/app/app/page.tsx` renders `<Dashboard key={selected} …>` so that
changing relative remounts every panel. Without it a panel's in-flight request can answer after the switch and draw
one relative's data under another's name. `useCarePlan` guards the same race with a request counter.

**Nothing on screen may read as medical advice.** Wording that describes a medicine, a flag or a gap comes from the
API, which has already passed it through the output guard. Do not write such sentences in the components.
