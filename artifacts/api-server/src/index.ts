import app from "./app";
import { logger } from "./lib/logger";
import { dbGetReminderUsers, MINIAPP_URL } from "./routes/telegram";

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error("PORT environment variable is required but was not provided.");
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const TOKEN = process.env["TELEGRAM_BOT_TOKEN"] || "";
const DOMAINS = process.env["REPLIT_DOMAINS"] || "";
const PRIMARY_DOMAIN = DOMAINS.split(",")[0] || "";
const IS_DEPLOYED = !!process.env["REPLIT_DEPLOYMENT"];

async function tgApi(method: string, body: object) {
  if (!TOKEN) return;
  try {
    await fetch(`https://api.telegram.org/bot${TOKEN}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (_) {}
}

async function setupWebhook() {
  if (!TOKEN || !PRIMARY_DOMAIN) return;
  const url = `https://${PRIMARY_DOMAIN}/api/telegram`;
  const res = await fetch(
    `https://api.telegram.org/bot${TOKEN}/setWebhook`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) }
  );
  const data = await res.json() as { ok: boolean; description?: string };
  logger.info({ url, ok: data.ok, desc: data.description }, "Telegram webhook registered");
}

async function sendReminders() {
  const now = new Date();
  const users = dbGetReminderUsers(now.getHours(), now.getMinutes());
  for (const u of users) {
    await tgApi("sendMessage", {
      chat_id: u.chat_id,
      text: "🔔 *Напоминание!*\n\nНе забудь записать расходы и доходы за сегодня.\nИспользуй /add или открой Mini App 📱",
      parse_mode: "Markdown",
      ...(MINIAPP_URL
        ? { reply_markup: { inline_keyboard: [[{ text: "📱 Открыть Mini App", web_app: { url: MINIAPP_URL } }]] } }
        : {}),
    });
  }
}

app.listen(port, async (err?: Error) => {
  if (err) {
    logger.error({ err }, "Error listening on port");
    process.exit(1);
  }
  logger.info({ port, deployed: IS_DEPLOYED }, "Server listening");

  if (IS_DEPLOYED) {
    await setupWebhook();
    setInterval(() => { sendReminders().catch(() => {}); }, 60_000);
    logger.info("Telegram webhook + reminder scheduler active");
  }
});
