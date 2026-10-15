[![Presence](assets/img/presence-banner-82e5cd328f.png)](https://presence.news/)

# Presence

**Crypto, with context.**

Presence is an independent publication about crypto and the people, companies and ideas moving through it.

**[Read Presence →](https://presence.news/)**

## 📰 The publication

We publish founder essays, interviews, reporting and a selective news feed. Our coverage spans markets, protocols, technology and the people building companies around them.

We focus on stories that need context and room for a full argument, with attention to the incentives and decisions behind the headlines.

## 🌐 Find Presence

- **Website:** [presence.news](https://presence.news/)
- **About:** [Our publication](https://presence.news/about/)
- **Contact:** [Get in touch](https://presence.news/contact/)
- **Telegram:** [@presencemedia](https://t.me/presencemedia)
- **X:** [@PresenceWeb3](https://x.com/PresenceWeb3)

## This repository

Source files for the Presence website, built with HTML, CSS and JavaScript and published through GitHub Pages. The `scripts/` directory contains the catalog generator, metadata builder and site validation tools.

## Development and publishing

Create a Python environment from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements-news.txt
```

Then build, validate and serve:

```sh
python3 scripts/build_seo.py
python3 scripts/validate_site.py
python3 -m unittest discover -s tests
python3 -m http.server 8000
```

The catalog in `assets/js/news-data.js` uses `type: "NEWS"` for news reports. `/news/` lists only these reports. `/crypto/`, `/technology/` and `/companies/` list articles and interviews in each topic. The homepage archive and RSS include the complete collection. Old `/news/#crypto` links redirect to the corresponding topic page; news-topic filters use query parameters.

To add an editorial news manuscript:

```sh
python3 scripts/import_news.py --source /path/to/manuscript.txt --date YYYY-MM-DD --slug lowercase-slug --summary "Short catalog summary"
python3 scripts/validate_site.py
```

The importer keeps the manuscript's title, introduction and body, attributes the report to Presence Editorial, and rebuilds listings, RSS, sitemap, social metadata and legacy redirects. It refuses to overwrite existing articles. A trailing `Sources for editorial verification:` section is saved under `docs/editorial/` as editor notes, rather than published as article copy. Commit the generated output together with the catalog change; GitHub Pages serves these static files without running the Python scripts.

Use `--image /assets/img/articles/YYYY-MM-DD_slug/image.jpg --image-alt "Description"` to include a supplied local image in both the news card and the article. Standalone manuscript date lines appear in the byline rather than being repeated in the body; editor-source headings are recognized case-insensitively.

The [automated news workflow](docs/editorial/automated-news.md) researches complete source pages and produces original reports with sections and original illustrations using local Qwen 7B models in independent GitHub jobs. No AI API key is required. Morning and evening runs start at 10:05 and 18:05 Moscow, with retries at 10:35 and 18:35. Processing takes additional time. Failed research or quality checks are reported as failures. The public Pages export and legacy Jekyll build exclude editorial records, tests and tooling; source remains visible in this public GitHub repository.
