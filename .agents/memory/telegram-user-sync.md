---
name: Telegram user sync
description: How the Mini App identifies the Telegram user reliably across contexts
---

`window.Telegram.WebApp.initDataUnsafe?.user?.id` can be undefined even when opened from Telegram. Use layered fallback:

1. `initDataUnsafe.user.id` (direct)
2. Parse raw `initData` string: `new URLSearchParams(initData).get("user")` → JSON.parse
3. URL param `?uid=<id>` (set by bot inline buttons)
4. Fallback `1234567` (browser testing only)

**Bot side**: All inline keyboard buttons append `?uid={user_id}` to the Mini App URL. Reply keyboard WebApp buttons rely on Telegram's `initData`.

**Why:** Without the URL param fallback, Mini App and bot use different user_ids → different data rows in SQLite. The `?uid=` param guarantees correct identity even when `initData` is unavailable.

**Import endpoint**: `POST /api/import-data { to_user_id, from_user_id }` merges all transactions/limits from one userId to another (used to recover test data from userId 1234567).
