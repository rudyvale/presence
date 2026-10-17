# Automated news reports

The Daily news workflow discovers recent stories through RSS, fetches the complete source page and writes an independent English report from factual evidence. RSS descriptions cannot replace the source article. Published copy uses an original narrative and wording, without reproducing the source's sentences, headings or paragraph sequence.

## Preserving length and factual detail

New reports use length policy 2. Their paragraph text contains at least as many words as the complete extracted source, with a 220-word minimum for short news. The upper bound is 115% of the source length, or 40 words above the minimum for very short sources. For a 904-word source, the accepted range is 904–1,040 words. Headings do not count toward the report's minimum.

The pipeline selects news sources of 180–1,800 words. Longer features are skipped in favor of another candidate instead of being reduced to a short summary. Source extraction excludes navigation, advertising, standalone related links and unrelated widgets. It refuses teaser-only pages.

All complete evidence passages are retained for eligible sources. The previous fixed selection of twelve facts and 1,200-word research sample no longer limits new reports. Research must preserve at least 80% of the extracted words after removing very short headings and fragments. Private evidence remains in memory; public editorial records store source URLs, extraction metrics, fingerprints, numerical data and fact hashes rather than source text.

The model first creates an independent outline and assigns evidence IDs to each paragraph, covering at least 90% of the evidence. Paragraph count and word ranges are calculated from the source length. It then writes groups of at most two paragraphs. Each group receives only its assigned evidence and a short continuity context. Plain JSON string fields avoid complex word-count grammars; software counts the returned words and requests focused corrections without reducing the required range.

Every group passes numerical, originality and factual checks before the next group is written. The claim reviewer checks the actor, metric, unit, comparison period, attribution and conditions against cited evidence. A yield cannot become retail-sales growth merely because both statements contain the same number. Failed groups receive a focused correction; verified earlier groups remain intact within the attempt. The final headline, summary and headings have a separate factual review.

The complete article must still cover at least 90% of the evidence, meet the source-dependent word range and contain complete, distinct paragraphs. Repetition and generic advice cannot satisfy the length requirement. The publisher independently checks the word range, artifact integrity and editorial restrictions before applying a worker's output.

## Required publication output

- A distinct headline, concise summary and two relevant section headings.
- An original report preserving source length and factual substance, with accurate attribution and uncertainty.
- An original 1600×900 Presence illustration in the news card and article, with alternative text and an illustration credit.
- Presence Editorial byline, correct publication date and reading time, metadata, RSS and sitemap entries.

Numeric checks distinguish currency from transaction counts, million from billion, percentages from percentage points and conventional bond-maturity labels. Extended copied source phrases, duplicate paragraphs, truncated model output, source branding, links, unsupported tickers, promotion and trading advice are rejected. When a specific phrase fails, the editor receives that phrase and its location. Headlines and summaries can be corrected without regenerating the body.

Earlier reviewed reports retain their recorded policy until an expansion is explicitly requested. Set `requested_length_policy` to `2` on a selected history record to request a full-length edition. Optional `requested_editorial_instructions` supplies constraints for that revision. Repairs preserve the original date and URL and do not consume new-publication slots. The publisher will not overwrite an article edited after its repair was planned.

## Schedule and recovery

Runs start at **10:05 and 18:05 Europe/Moscow**, with retries at **10:35 and 18:35**. GitHub may delay starts; CPU research and verification take additional time. The target is one new morning report and two total after the evening slot, with a hard maximum of two automated publications per Moscow day.

Each due report or requested revision runs in its own worker, with up to four workers in parallel. Full-length writing and paragraph verification have a 60-minute processing budget and a 70-minute job timeout. This allows longer factual reports without dropping verification to meet the former short-brief budget.

Validated artifacts are saved immediately. The publisher checks out the latest main revision, applies complete artifacts independently, rechecks deduplication and daily limits, and commits the result. Rejected or missing work produces a failed workflow result and remains eligible for retry. It cannot discard another worker's validated report or create a placeholder article.

Workers use the planner's exact code revision. Artifacts identify their validation and length policies. Normal runs wait for active work; manual `restart` or a commit containing `[restart-news]` cancels obsolete jobs. Sponsored and press-release entries, duplicate URLs and sources older than 48 hours are excluded.

## Deployment verification

The public Pages export and legacy Jekyll build exclude scripts, tests and editorial records. These website exclusions do not hide source in this public GitHub repository.

The deployment checker verifies exact published body hashes, headlines, section headings, full-size illustrations and matching news cards. All four listing pages must omit the removed category-counter panels, and private site paths must return HTTP 404.

The independent Editorial source checks workflow fetches fresh complete source pages for the latest eight automated reports, checking final quantities, prose originality, length policy and audit hashes. Check older reports with `python scripts/check_news_sources.py --article /articles/DATE_SLUG/`.

Hosting health runs every six hours and after relevant changes. It verifies public DNS, a trusted certificate matching presence.news, actual page content and all complete report hashes and assets. It runs independently of unfinished model jobs.

## Runtime

Ollama **0.11.10** comes from its official GitHub release and is checked against its pinned SHA-256 checksum. The cached **qwen2.5:7b** model runs on a CPU runner at the fixed loopback endpoint. Model blobs are verified before reuse. TLS verification remains enabled. No AI API key or paid AI subscription is required; Actions and cache usage follow the repository's allowance.

Local setup:

    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install -r scripts/requirements-news.txt
    python -m unittest discover -s tests
    python scripts/auto_news.py --check-feed

For local generation, start `ollama serve`, install `qwen2.5:7b`, then run `python scripts/auto_news.py --repair-existing`. Full source access is required. The optional OpenAI-compatible adapter remains available; the scheduled workflow uses the local model.
