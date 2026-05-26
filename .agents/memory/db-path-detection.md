---
name: DB path detection
description: How to correctly resolve bot/finance.db in both dev and production for the Express API server
---

The API server resolves the shared SQLite file differently depending on environment:

- **Dev**: `process.cwd()` = `/home/runner/workspace/artifacts/api-server` → use `path.resolve(cwd, "../../bot/finance.db")`
- **Production**: `process.cwd()` = `/home/runner/workspace` → use `path.resolve(cwd, "bot/finance.db")`

**Current implementation** (transactions.ts and telegram.ts):
```typescript
const WS_ROOT = process.cwd().includes("api-server")
  ? path.resolve(process.cwd(), "../..")
  : process.cwd();
const DB_PATH = path.resolve(WS_ROOT, "bot/finance.db");
```

**Why:** Production runs `node dist/index.mjs` from workspace root; dev runs `pnpm run dev` from the package directory. Using a hardcoded `../../` breaks in production.
