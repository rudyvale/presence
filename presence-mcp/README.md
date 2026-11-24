# Presence MCP

Search the public archive, list recent stories, and read articles with links to their original pages.

Connect to the public server over Streamable HTTP without an API key.

```sh
codex mcp add presence --url https://presence-mcp.private-companion-bot.workers.dev/mcp
```

In other remote MCP clients, use `https://presence-mcp.private-companion-bot.workers.dev/mcp` as the server URL.

## Local setup

From the repository root with Node.js 22 or later, install the locked dependencies and register the local connector.

```sh
npm ci --prefix presence-mcp
codex mcp add presence -- node "$PWD/presence-mcp/stdio.mjs"
```

For other stdio clients, use `node` as the command and the absolute path to `presence-mcp/stdio.mjs` as its argument.

## Remote deployment

The same tools work over Streamable HTTP on Cloudflare Workers. From `presence-mcp/`, run `npx wrangler dev` to test locally. Run `npx wrangler deploy` with an authenticated Cloudflare account to publish. Add `/mcp` to the Worker URL printed by Wrangler and enter that URL in the MCP client.
