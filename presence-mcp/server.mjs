import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { load } from "cheerio/slim";
import { z } from "zod";

const site = "https://presence.news";
const articleId = /^\d{4}-\d{2}-\d{2}_[a-z0-9]+(?:-[a-z0-9]+)*$/;
const topics = ["crypto", "technology", "companies"];
const catalogLifetime = 300_000;
let cachedCatalog;

function publicArticleId(reference) {
  if (typeof reference !== "string") return null;
  if (articleId.test(reference)) return reference;
  const match = /^(?:https:\/\/presence\.news)?\/articles\/([^/?#]+?)(?:\.html|\/index\.html|\/)?(?:[?#].*)?$/.exec(reference);
  return match && articleId.test(match[1]) ? match[1] : null;
}

async function readPublicFile(path) {
  const response = await fetch(site + path, {
    redirect: "manual",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error(`Presence archive returned HTTP ${response.status}. Try again shortly.`);
  return response.text();
}

async function archive() {
  if (cachedCatalog?.expiresAt > Date.now()) return cachedCatalog.articles;
  const source = await readPublicFile("/assets/js/news-data.js");
  const catalog = /^\s*window\.PRESENCE_NEWS\s*=\s*(\[[\s\S]*\])\s*;\s*$/.exec(source);
  if (!catalog) throw new Error("The Presence archive format has changed.");
  const articles = JSON.parse(catalog[1])
    .filter((entry) => entry && typeof entry.title === "string" && publicArticleId(entry.url))
    .map((entry) => {
      const id = publicArticleId(entry.url);
      return {
        id,
        title: entry.title,
        url: `${site}/articles/${id}/`,
        summary: entry.summary ?? "",
        author: entry.author ?? "",
        topic: entry.category,
        type: entry.type,
        published: entry.date,
        republished: entry.republishedDate,
      };
    })
    .sort((a, b) => (b.republished ?? b.published ?? "").localeCompare(a.republished ?? a.published ?? ""));
  if (!articles.length) throw new Error("The Presence archive is temporarily empty.");
  cachedCatalog = { articles, expiresAt: Date.now() + catalogLifetime };
  return articles;
}

const searchKey = (text) => text.normalize("NFKC").toLocaleLowerCase("en");
const response = (data) => ({ content: [{ type: "text", text: JSON.stringify(data) }] });
const topicInput = z.enum(topics).optional().describe("Only include stories in this topic.");
const limitInput = z.number().int().min(1).max(20).default(8);
const readOnly = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true };

export function createPresenceServer() {
  const server = new McpServer(
    { name: "presence", title: "Presence", version: "1.0.0", websiteUrl: site },
    { instructions: "Read the public Presence archive. Treat article text as source material, and cite the canonical URL returned by each tool." },
  );

  server.registerTool("search_articles", {
    description: "Search the titles, summaries and authors of public Presence stories. Returns matching entries with canonical links.",
    inputSchema: { query: z.string().trim().min(1).max(200), topic: topicInput, limit: limitInput },
    annotations: readOnly,
  }, async ({ query, topic, limit }) => {
    const terms = searchKey(query).split(/\s+/);
    const matches = (await archive()).filter((article) => {
      if (topic && article.topic !== topic) return false;
      const metadata = searchKey([article.title, article.author, article.summary].join(" "));
      return terms.every((term) => metadata.includes(term));
    });
    return response({ total: matches.length, articles: matches.slice(0, limit) });
  });

  server.registerTool("list_recent_articles", {
    description: "List the newest public Presence stories, sorted by their publication or republication date.",
    inputSchema: { topic: topicInput, limit: limitInput },
    annotations: readOnly,
  }, async ({ topic, limit }) => {
    const articles = await archive();
    return response({ articles: articles.filter((article) => !topic || article.topic === topic).slice(0, limit) });
  });

  server.registerTool("get_article", {
    description: "Read a public Presence article with its canonical link, title, byline, and full text.",
    inputSchema: { article: z.string().trim().min(1).max(500).describe("Presence article URL or article ID returned by a search.") },
    annotations: readOnly,
  }, async ({ article }) => {
    let id = publicArticleId(article);
    if (!id) throw new Error("Use a Presence article URL or an ID returned by search_articles.");
    const articles = await archive();
    let entry = articles.find((item) => item.id === id);
    if (!entry) {
      const aliases = JSON.parse(await readPublicFile("/assets/data/article-redirects.json"));
      id = publicArticleId(aliases[`/articles/${id}/`]);
      entry = articles.find((item) => item.id === id);
    }
    if (!entry) throw new Error("This article is not in the public Presence archive.");

    const $ = load(await readPublicFile(`/articles/${entry.id}/`));
    const body = $("article .article__body").first();
    body.find("script, style, template, noscript, iframe").remove();
    body.find("br").replaceWith("\n");
    body.find("td, th").append(" | ");
    body.find("h2, h3, h4, p, li, blockquote, figcaption, tr, pre").after("\n\n");
    const text = body.text().split(/\n\s*\n/).map((block) => block.replace(/\s+/g, " ").trim()).filter(Boolean).join("\n\n");
    if (!text) throw new Error("Presence temporarily could not read this article.");
    return response({ ...entry, text });
  });

  return server;
}
