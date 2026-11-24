import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createPresenceServer } from "./server.mjs";

await createPresenceServer().connect(new StdioServerTransport());
