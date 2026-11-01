# Going public on submission day

The deployment is live and unreachable at the same time until you do this (D-69). Three switches, and **the order matters**: turn the
API's gate off first, because if the website becomes public while the gate is still on, every page loads and nothing in it works.

Takes about ten minutes, most of it waiting for a redeploy.

## 1. Open the API (Render)

- Dashboard &rarr; `caresaathi-api` &rarr; **Environment** &rarr; delete `SITE_GATE_TOKEN` &rarr; **Save**. Render redeploys; wait for "Live".
- Check it answers a stranger: `curl -s -o /dev/null -w "%{http_code}" https://caresaathi-api.onrender.com/api/v1/trust/live` &rarr; `200`.
  While the gate was on this was `404`.

## 2. Open the website (Vercel)

- Project &rarr; **Settings** &rarr; **Environment Variables** &rarr; delete `SITE_GATE_TOKEN`.
- Project &rarr; **Settings** &rarr; **Deployment Protection** &rarr; scope **None**.
- **Redeploy** (deleting the variable does not change the running build).

## 3. Open the repository (GitHub)

Before flipping it, from a clean clone:

```
git ls-files | grep -iE "\.env$|\.env\.(production|render|local)$"      # must print nothing
git log --all --oneline -- .env .env.production .env.render             # must print nothing
git grep -niE "meta_api_key *= *[a-z0-9]" -- . ':!*.example' ':!docs'   # must print nothing
```

Then GitHub &rarr; **Settings** &rarr; **General** &rarr; **Change visibility** &rarr; Public. Making it public now does not change any commit
date, so the baseline commit and the post-kickoff commits still say exactly what they said (docs/18-rules-and-compliance.md).

## 4. Check it the way a judge will

```
python backend/scripts/launch_check.py https://caresaathi.vercel.app
```

It checks the things that have actually gone wrong: the gate is off on both sides, the host's own protection is off, the address is
https, the landing page still says the data is synthetic, the evidence page opens with no account, an invented Emergency Card link shows
nothing, and the security headers are there. Then do these two by hand, because no script can:

- Open the site on your phone, on mobile data, and sign up. The microphone prompt must appear.
- Open the public repository link in a private window.

## What to say in the submission

- The link is the **Vercel** address, not the Render one.
- All patient data is fictional (the "Synthetic patient" marker is on the screen already).
- The API sleeps after 15 minutes without traffic on Render's free plan and takes about a minute to wake. Keep it warm during judging:
  a free scheduler pinging `https://caresaathi-api.onrender.com/healthz` every 10 minutes costs 744 hours a month, inside the 750 the
  free plan allows for one service. If a judge still meets a cold start, the first page simply takes a minute.

## Putting the gate back

Set `SITE_GATE_TOKEN` to the same value in both places and redeploy both. Nothing else changes; no data is touched.
