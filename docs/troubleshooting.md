# Troubleshooting

[Español](troubleshooting.es.md)

## Search does not start

Confirm the résumé and configure DeepSeek in **Settings**. Configure TheirStack
for primary search coverage too. A `401/403` means a rejected key; `402` usually
means insufficient credits, and `429` is a temporary rate limit.

## No jobs appear

Try a broader role. Results exclude unknown dates, postings older than 30 days,
closed jobs, and jobs outside Costa Rica. Confirm that TheirStack is configured
and funded. When it fails, fallback sources remain available and the UI labels
the coverage as limited.

## A portal is not integrated

LinkedIn, Indeed, Glassdoor, and Computrabajo open manually. Copy the date, URL,
and description through **Import a job you found**.

## Animation or WebGL fails

Update the graphics driver and confirm `ame-terrarium.glb` and
`ame-terrarium-poster.svg` exist in `frontend/public/models`. The app switches to
the static fallback automatically when WebGL fails. Reduced motion keeps a stable
pose.

Run `./scripts/diagnose.ps1` and `./scripts/test.ps1` for local diagnostics.
