# Automated news reports

The Daily news workflow uses the RSS feed only to discover recent stories. It fetches the full source page, extracts the article body while excluding navigation, advertising and related stories, and rejects pages that only provide a teaser.

A local **Qwen 2.5 7B** model selects 8–12 private evidence passage IDs, then writes an independent English report from that evidence. The software retrieves the exact passage text from those IDs; the model cannot transcribe or paraphrase the source evidence. The published article uses original prose and no direct quotations. Source bodies and intermediate evidence remain in runner memory. Editorial records retain source URLs, extraction metrics, numerical data, source fingerprints and fact hashes rather than republishing research-note prose. Originality checks apply to the final article.

Long sources use a bounded selection of complete passages, up to 1,200 words, including the opening and relevant passages from each quarter of the original article. This prevents CPU inference timeouts without cutting sentences or using an RSS excerpt. Numerical and originality checks still use the entire extracted source. This selection does not guarantee coverage of every detail in a long source.

## Required output

- A distinct, accurate headline and a concise summary.
- Source-dependent length: 8 paragraphs (280–400 words) for sources under 450 words, 10 (350–500) for 450–749 words, and 12 (420–600) for sources of 750 words or more. New reports cannot fall below the corresponding minimum. Earlier reviewed copy retains its original policy until a specific expansion is requested.
- Two relevant section headings.
- An original 1600×900 Presence illustration used in the news card and article, with alternative text and an illustration credit.
- Correct byline, original publication date, reading time, metadata, RSS and sitemap entries.

Numeric checks normalize amounts and units, including million versus billion, payment counts versus currency values, and percentages versus percentage points. The system rejects unsupported tickers, copied extended phrases, truncated model output, source branding, links, promotional claims and incomplete articles.

Originality checks compare source prose paragraphs individually. Table cells, chart labels and captions remain factual evidence but are not joined into artificial prose sentences for the copy check.

Every paragraph identifies its private evidence indices. Its quantities must occur in that evidence, and the draft must cover at least three quarters of the selected excerpts. A separate model call checks the draft against those verbatim excerpts, including attribution of figures to the correct company and comparisons across different periods. The review rejects unrelated recommendations, promotional conclusions and unsupported advice. A rejected draft gets one correction attempt with the previous draft and specific review issues. A source that cannot support a complete, validated report is skipped in favor of another candidate. This automated review can still miss errors.

All three model stages use JSON schemas passed to the generator. The writer schema requires the source-dependent number of paragraph objects, two headings and evidence indices inside each paragraph. The software separates private evidence indices from the final article copy before importing it.

Repeated headlines, copied prose and source-branding errors receive a targeted edit of only the affected fields. The complete report then goes through the same numeric, evidence, originality and grounding checks again. Each hosted worker warms up the model with a short structured readiness response before researching a source; article format and content are checked on the actual report.

Facts have explicit numeric IDs. A paragraph with an unsupported figure receives a focused correction of its text and citations before validation resumes. Numeric checks normalize conventional bond-maturity labels such as US10Y and percentage abbreviations. Promotion, trading advice and generic monitoring conclusions receive focused corrections, including in titles and summaries, with the exact offending text identified. The publisher independently rejects those phrases, repeated paragraphs and undersized expanded reports even if a worker approved them. Formatting cleanup retains attribution as “the source publication” and removes optional URL-only parentheses; other URLs remain validation errors.

## Schedule and recovery

Runs start at **10:05 and 18:05 Europe/Moscow**, with catch-up attempts at **10:35 and 18:35**. Starts avoid the busiest minute at the top of the hour. GitHub may still delay them, and research takes additional time. The target is one new report during the morning slot and two total during the evening slot, with a hard maximum of two new automated publications per Moscow calendar day. Repeated runs cannot consume the evening slot in the morning.

Each due report and legacy repair has an independent worker, with up to four workers running in parallel. A worker has a 22-minute editorial budget, allowing a full correction and review, and saves an integrity-checked report artifact immediately after validation. The publisher merges completed artifacts, rechecks publication limits and commits the result. A failed worker cannot discard another worker's finished report. Incomplete jobs produce a red workflow result and remain eligible for retry. Installed models are cached even when editorial validation fails.

Workers check out the same editorial code revision as the planner. Artifacts identify their validation version, and the publisher rejects artifacts from an incompatible version.

Normal runs wait for active editorial work. A manual workflow run can enable `restart`, or a maintainer can push a commit containing `[restart-news]`, to cancel an obsolete run after a processing fix. Reports not yet committed are researched again; only published records consume the daily quota.

Canonical source URLs prevent duplicate publication. Sources older than 48 hours and sponsored/press-release entries are excluded. Repairs and explicitly requested expansions preserve their publication dates and URLs and do not consume new-publication slots. Set requested_length_policy to 1 on a selected editorial record to request expansion; the publisher records the completed length_policy and skips a repair if the article changed after planning.

If a due publication or repair cannot be completed, the workflow reports a failure with the reason. Independently validated work may still be committed and deployed, while rejected content is retained for a later repair attempt. A green run no longer means that only RSS access and HTML status codes were checked.

## Deployment verification

All site output is validated before committing. New illustrations are committed together with articles. The exported Pages artifact contains only public site files; editorial tooling, tests and records are excluded. The Jekyll configuration applies the same exclusions to the legacy build.

The deployment job checks out the exact commit used to build the artifact. On the public domain it verifies changed reports, news listing entries, complete body hashes, section headings, matching headlines and downloadable full-size illustrations. Private website paths must return HTTP 404. These exclusions do not conceal source in a public GitHub repository or remove Git history.

The separate Editorial source checks workflow re-fetches full source pages for the latest eight complete reports after editorial changes. It checks final headlines, quantities, prose originality and audit hashes, including manual edits. Older reports can be checked explicitly with `python scripts/check_news_sources.py --article /articles/DATE_SLUG/`. These checks complement the model's factual review. The Hosting health workflow separately checks public DNS, the trusted TLS certificate and real page content every six hours. It also verifies all complete automated reports against their exact body hashes, illustrations and listing cards, checks that the separate category counter panels stay removed, and confirms private site paths return HTTP 404. This verification runs independently of unfinished model jobs.

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
