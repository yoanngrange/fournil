# Fournyl — operations

Everything runs on GitHub (Pages + Actions). Emails go through Resend from `fournyl-reports@yoanngrange.com`,
like the other sites (simplekatorza, vraieforet, yoanngrange.com).

## What runs when

| Workflow | When | What | Emails |
|---|---|---|---|
| `deploy.yml` | push to `main`, the 3rd and the 8th of each month 05:00 UTC, by hand | downloads sources, builds data, tests, assembles and deploys the site | on failure only |
| `monitor.yml` | daily ~08:17 Paris | home, département, commune, Infos légales, sources, `sw.js` answer; data younger than 40 days; 96 départements | on problems only |
| `weekly-traffic-recap.yml` | Monday 08:00 Paris | Cloudflare Web Analytics: page views, week over week, top pages, plus data build date and source publication dates | every week |

The 8th-of-the-month run exists because Insee published the November 2026 Sirene stock on the 5th: the run of
the 3rd failed ("No resource matching … on data.gouv.fr"). A failed build never breaks the site: Pages keeps
serving the previous deploy.

The public page `/infos-legales/#donnees` shows the last build, the next one, and each source's vintage,
publication and download dates (from `data/meta.json`). It warns visitors when the data is older than 40 days.

## Settings (GitHub > fournyl > Settings > Secrets and variables > Actions)

| Name | Kind | Value | Used by |
|---|---|---|---|
| `RESEND_API_KEY` | secret | same Resend key as the other sites | all three workflows |
| `CF_API_TOKEN` | secret | Cloudflare API token with *Account Analytics: Read* (same as the other sites) | weekly recap |
| `CF_BEACON_TOKEN` | variable | beacon token of the fournyl.com site in Cloudflare Web Analytics | deploy (analytics tag) |
| `CF_SITE_TAG` | variable | site tag of the same site (in the URL of its Web Analytics page) | weekly recap |
| `SITE_URL` | variable | `https://fournyl.com/` once the domain works (default: the github.io address) | monitor, recap |

Without them everything still works: no analytics tag, no recap (a warning in the run), monitor prints only.

From a terminal: `gh secret set RESEND_API_KEY`, `gh variable set CF_SITE_TAG --body …`.

## Custom domain fournyl.com

1. DNS at OVH: paste `docs/dns/fournyl.com.zone` (instructions inside). Optional but recommended: verify the
   domain in your GitHub account settings (TXT record, see the zone file).
2. Wait until `dig +short fournyl.com` returns the four `185.199.10x.153` addresses.
3. Merge the "domaine fournyl.com" PR: it sets `SITE_URL` in `pipeline/config.py` (canonical URLs, sitemap,
   404 page) and adds `public/CNAME`.
4. GitHub > fournyl > Settings > Pages > Custom domain: `fournyl.com`, then tick *Enforce HTTPS* once the
   certificate is issued (a few minutes to an hour). Set the `SITE_URL` variable to `https://fournyl.com/`.
5. `https://yoanngrange.github.io/fournyl/…` then redirects to `https://fournyl.com/…` (old links keep working).

## Cloudflare Web Analytics

Cloudflare dashboard > Analytics & Logs > Web Analytics > Add a site > `fournyl.com` > copy the JS snippet's
`token` into the `CF_BEACON_TOKEN` variable, and the site tag into `CF_SITE_TAG`. DNS stays at OVH: the beacon
is a script, no proxy needed. Cookieless, so no consent banner (see Infos légales > Confidentialité).

## When something breaks

- **Build failed email:** open the run link. A source renamed or late on data.gouv.fr → adjust its
  `title_startswith` in `pipeline/config.py`, or wait for the retry on the 8th. A data test failed → read the
  assertion; never deploy around it.
- **Monitor email, pages 404:** check the last `deploy.yml` run and Settings > Pages.
- **Monitor email, data stale:** both monthly runs failed; run `deploy.yml` by hand after fixing.
