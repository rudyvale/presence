# Automated news briefs

The `Daily news` workflow selects one recent item per run from the configured RSS feed and asks an AI API to write a short, original 80–180-word brief from its headline and limited factual summary. It does not download or republish full source articles or third-party photographs. Sources stay in editorial records; article copy has no source-publication branding or links. GregMeta can supply images for individual reports afterward.

## Schedule and limits

- Runs at **10:00 and 18:00 Europe/Moscow** (`07:00` and `15:00` UTC). GitHub may delay scheduled starts.
- At most one publication per run and two automated publications per Moscow calendar day.
- Canonical source URLs are recorded to prevent duplicate publication.
- Items older than 48 hours and sponsored/press-release content are skipped.
- Insufficient facts, unsupported numeric claims, links/source branding and extended repeated source phrases cause rejection, not a placeholder article.
- The workflow validates all site output before committing to `main`.
- The workflow explicitly uploads/deploys the public Pages artifact after its bot commit: pushes with `GITHUB_TOKEN` do not trigger a separate Pages build.

## Required AI setup

Add an API key as the repository Actions secret **`NEWS_AI_TOKEN`**:

`https://github.com/rudyvale/presence/settings/secrets/actions`

Do not send the key in chat, commit it or place it in public site files.

Defaults are OpenAI's `https://api.openai.com/v1/chat/completions` endpoint and `gpt-4.1-mini`. For another OpenAI-compatible provider, set repository Actions variables **`NEWS_AI_ENDPOINT`** and **`NEWS_AI_MODEL`**. OpenRouter uses `https://openrouter.ai/api/v1/chat/completions` and the desired supported model identifier.

GitHub Models is unavailable: GitHub's current documentation states that it was retired on July 30, 2026. A repository `GITHUB_TOKEN` cannot replace an AI-provider API key. ChatGPT subscriptions and API billing are separate.

Without `NEWS_AI_TOKEN`, the workflow checks feed access and the site but reports AI publishing as inactive. Once the secret is added, the next scheduled or manually dispatched run can publish. Actual AI inference and publication must be verified with a credential-backed run; offline tests are not evidence of API readiness.

## Local checks

```sh
python3 -m unittest discover -s tests
python3 scripts/auto_news.py --check-feed
python3 scripts/auto_news.py
python3 scripts/validate_site.py
```

The final two commands require a usable AI binding/network route for the provider and RSS source. No TLS verification is disabled. API errors stop publishing, credentials and provider response bodies are not logged, and credentials are not forwarded to redirected model endpoints.

Publication rights and content review remain editorial responsibilities. The workflow produces concise independent briefs rather than close rewrites of full third-party articles.
