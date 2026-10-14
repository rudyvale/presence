# Automated news briefs

The `Daily news` workflow selects one recent item per run from the RSS feed and runs Qwen 2.5 3B locally on the GitHub Actions runner. It writes an original English brief from the headline and limited factual summary. No AI API key, paid AI subscription or external inference service is required. GitHub runner and cache usage follows the repository's Actions allowance.

It does not download or republish full source articles or third-party photographs. Sources stay in editorial records; article copy has no source-publication branding or links. GregMeta can supply images for individual reports afterward.

## Schedule and limits

- Runs at **10:00 and 18:00 Europe/Moscow** (`07:00` and `15:00` UTC), on pushes to `main`, and through **Run workflow**. GitHub may delay scheduled starts.
- At most one publication per run and two automated publications per Moscow calendar day.
- Canonical source URLs are recorded to prevent duplicate publication.
- Items older than 48 hours and sponsored/press-release content are skipped.
- Insufficient facts, unsupported numeric claims, links/source branding and extended repeated source phrases cause rejection, not a placeholder article.
- All site output is validated before committing to `main`.
- The workflow uploads/deploys the public Pages artifact after its bot commit: pushes with `GITHUB_TOKEN` do not trigger a separate Pages build.

## Execution

Ollama **0.11.10** is downloaded from its official GitHub release and checked against the release's SHA-256 checksum. GPU libraries are excluded. The **`qwen2.5:3b`** quantized model runs on CPU, through the fixed loopback address `127.0.0.1:11434`. Binary and model downloads are cached between runs. Ollama verifies downloaded model blobs. Neither source content nor credentials are sent to an AI provider.

The model is started only when a source is eligible and the daily publication limit permits another brief. Invalid output is discarded. The Actions run reports whether a real brief was prepared; model startup alone does not establish successful publication.

After drafting, a second local model call checks whether the supplied headline and summary support every concrete claim. Unconfirmed drafts are discarded. The source snapshot is retained in the editorial ledger for review. This automated check can still miss errors and does not replace editorial judgment.

## Site files and source visibility

`scripts/export_site.py` exports only public pages and assets. Python code, workflow files, tests and editorial records are excluded. `_config.yml` also excludes these files from the legacy GitHub Pages Jekyll build. The root does not contain `.nojekyll`, because it would bypass those exclusions; the curated deployment artifact creates its own `.nojekyll`.

After deployment, `scripts/check_deployment.py` checks the homepage, news listing and new article on the public domain and requires HTTP 404 for automation code, tests, editorial documentation and repository README paths.

These exclusions prevent serving automation code through the website. They do not hide source in a public GitHub repository or remove it from Git history. Full source privacy requires a private repository and a supported Pages plan or a separate private automation repository. No obfuscation or client-side secret storage is used.

## Local checks

```sh
python3 -m unittest discover -s tests
python3 scripts/auto_news.py --check-feed
ollama serve
ollama pull qwen2.5:3b
python3 scripts/auto_news.py
python3 scripts/validate_site.py
```

Run `ollama serve` in a separate terminal before inference. RSS access and the initial model download require network access. TLS verification stays enabled. Only the fixed local model service is accessed without the external HTTP proxy.

The optional API adapter is still available for local use with `NEWS_AI_BACKEND=api`, `NEWS_AI_TOKEN`, and optional `NEWS_AI_ENDPOINT` and `NEWS_AI_MODEL`. The scheduled GitHub workflow uses the local backend and does not read that secret.
