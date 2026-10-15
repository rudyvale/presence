# Automated news reports

The Daily news workflow uses the RSS feed only to discover recent stories. It fetches the full source page, extracts the article body while excluding navigation, advertising and related stories, and rejects pages that only provide a teaser.

A local **Qwen 2.5 7B** model selects 8–12 private evidence passage IDs, then writes an independent English report from that evidence. The software retrieves the exact passage text from those IDs; the model cannot transcribe or paraphrase the source evidence. The published article uses original prose and no direct quotations. Source bodies and intermediate evidence remain in runner memory. Editorial records retain source URLs, extraction metrics, numerical data, source fingerprints and fact hashes rather than republishing research-note prose. Originality checks apply to the final article.

Long sources use a bounded selection of complete passages, up to 1,200 words, including the opening and relevant passages from each quarter of the original article. This prevents CPU inference timeouts without cutting sentences or using an RSS excerpt. Numerical and originality checks still use the entire extracted source. This selection does not guarantee coverage of every detail in a long source.

## Required output

- A distinct, accurate headline and a concise summary.
- Six to ten substantive paragraphs, accepted at 220–520 words; the writing target is 240–380 words.
- Two relevant section headings.
- An original 1600×900 Presence illustration used in the news card and article, with alternative text and an illustration credit.
- Correct byline, original publication date, reading time, metadata, RSS and sitemap entries.

Numeric checks normalize amounts and units, including million versus billion, payment counts versus currency values, and percentages versus percentage points. The system rejects unsupported tickers, copied extended phrases, truncated model output, source branding, links, promotional claims and incomplete articles.

Every paragraph identifies its private evidence indices. Its quantities must occur in that evidence, and the draft must cover at least three quarters of the selected excerpts. A separate model call checks the draft against those verbatim excerpts, including attribution of figures to the correct company and comparisons across different periods. The review rejects unrelated recommendations, promotional conclusions and unsupported advice. A rejected draft gets one correction attempt with the previous draft and specific review issues. A source that cannot support a complete, validated report is skipped in favor of another candidate. This automated review can still miss errors.

## Schedule and recovery

Runs start at **10:05 and 18:05 Europe/Moscow**, with catch-up attempts at **10:35 and 18:35**. Starts avoid the busiest minute at the top of the hour. GitHub may still delay them, and research takes additional time. The target is one new report during the morning slot and two total during the evening slot, with a hard maximum of two new automated publications per Moscow calendar day. Repeated runs cannot consume the evening slot in the morning.

Each due report and legacy repair has an independent worker, with up to four workers running in parallel. A worker has a 15-minute editorial budget and saves an integrity-checked report artifact immediately after validation. The publisher merges completed artifacts, rechecks publication limits and commits the result. A failed worker cannot discard another worker's finished report. Incomplete jobs produce a red workflow result and remain eligible for retry. Installed models are cached even when editorial validation fails.

Workers check out the same editorial code revision as the planner. Artifacts identify their validation version, and the publisher rejects artifacts from an incompatible version.

Normal runs wait for active editorial work. A manual workflow run can enable `restart`, or a maintainer can push a commit containing `[restart-news]`, to cancel an obsolete run after a processing fix. Reports not yet committed are researched again; only published records consume the daily quota.

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
