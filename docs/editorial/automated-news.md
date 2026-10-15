# Automated news reports

The Daily news workflow uses the RSS feed only to discover recent stories. It fetches the full source page, extracts the article body while excluding navigation, advertising and related stories, and rejects pages that only provide a teaser.

A local **Qwen 2.5 7B** model creates a factual research sheet, then writes an independent English report from those facts. It does not reproduce the source article's prose, quotations or narrative structure. Original source bodies exist only in runner memory; editorial records retain the source URL, extraction metrics, fingerprint and independently worded research facts.

## Required output

- A distinct, accurate headline and a concise summary.
- Six to ten substantive paragraphs, accepted at 220–520 words; the writing target is 240–380 words.
- Two relevant section headings.
- An original 1600×900 Presence illustration used in the news card and article, with alternative text and an illustration credit.
- Correct byline, original publication date, reading time, metadata, RSS and sitemap entries.

Numeric checks normalize amounts and units, including million versus billion, payment counts versus currency values, and percentages versus percentage points. The system rejects unsupported tickers, copied extended phrases, truncated model output, source branding, links, promotional claims and incomplete articles.

A separate model call checks the draft against the original article and requires coverage of at least three quarters of the research facts. A rejected draft gets one correction attempt. A source that cannot support a complete, validated report is skipped in favor of another candidate. This automated review can still miss errors.

## Schedule and recovery

Runs start at **10:00 and 18:00 Europe/Moscow**, with catch-up attempts at **10:30 and 18:30**. GitHub may delay scheduled starts. The target is one new report during the morning slot and two total during the evening slot, with a hard maximum of two new automated publications per Moscow calendar day. Repeated runs cannot consume the evening slot in the morning.

Canonical source URLs prevent duplicate publication. Sources older than 48 hours and sponsored/press-release entries are excluded. Repairs to legacy teaser reports preserve their publication dates and URLs and do not consume new-publication slots.

If a due publication or repair cannot be completed, the workflow reports a failure with the reason. Independently validated work may still be committed and deployed, while rejected content is retained for a later repair attempt. A green run no longer means that only RSS access and HTML status codes were checked.

## Deployment verification

All site output is validated before committing. New illustrations are committed together with articles. The exported Pages artifact contains only public site files; editorial tooling, tests and records are excluded. The Jekyll configuration applies the same exclusions to the legacy build.

The deployment job checks out the exact commit used to build the artifact. On the public domain it verifies changed reports, news listing entries, complete body hashes, section headings, matching headlines and downloadable full-size illustrations. Private website paths must return HTTP 404. These exclusions do not conceal source in a public GitHub repository or remove Git history.

## Runtime

Ollama **0.11.10** is downloaded from its official GitHub release and checked against its SHA-256 checksum. GPU libraries are excluded. The quantized **qwen2.5:7b** model runs on the GitHub CPU runner through the fixed loopback address. Downloads are cached. No AI API key or paid AI subscription is required; GitHub Actions and cache usage follow the repository's allowance.

Local setup:

    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install -r scripts/requirements-news.txt
    python -m unittest discover -s tests
    python scripts/auto_news.py --check-feed

Run ollama serve in a separate terminal and ollama pull qwen2.5:7b before invoking python scripts/auto_news.py --repair-existing. Source pages and the initial model download require network access. TLS verification remains enabled.

An optional OpenAI-compatible adapter remains available with NEWS_AI_BACKEND=api, NEWS_AI_TOKEN, and optional NEWS_AI_ENDPOINT and NEWS_AI_MODEL. The scheduled workflow uses the local model and does not read those credentials.
