import re

import httpx
from sqlmodel import Session

from app.services import mailer, settings_store

TIMEOUT = 15
TELEGRAM_LIMIT = 4096
DISCORD_LIMIT = 2000
WEBHOOK = re.compile(
    r"^https://(discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$"
)


class ChatError(Exception):
    pass


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT)


def build_text(results: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for item in results:
        groups.setdefault(item["status"], []).append(item)
    lines = ["[Pinakes] 整理完成"]
    for status, items in groups.items():
        label = mailer.STATUS_TEXT.get(status, status)
        lines.append(f"{label}（{len(items)}）")
        lines.extend(f"  {mailer.line(i)}" for i in items)
    if "pending_review" in groups:
        lines.append("待確認的項目需要到 Pinakes 手動選擇。")
    return "\n".join(lines)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def send_telegram(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        raise ChatError("Telegram 機器人金鑰或聊天室 ID 尚未設定")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {"chat_id": chat_id, "text": _clip(text, TELEGRAM_LIMIT)}
    async with make_client() as client:
        try:
            res = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise ChatError(f"Telegram 連線失敗：{exc.__class__.__name__}") from exc
    if res.status_code != 200:
        raise ChatError(f"Telegram 發送失敗（HTTP {res.status_code}）")


async def send_discord(webhook: str, text: str) -> None:
    if not webhook:
        raise ChatError("Discord Webhook 網址尚未設定")
    if not WEBHOOK.match(webhook):
        raise ChatError("Discord Webhook 網址格式錯誤")
    body = {"content": _clip(text, DISCORD_LIMIT)}
    async with make_client() as client:
        try:
            res = await client.post(webhook, json=body)
        except httpx.HTTPError as exc:
            raise ChatError(f"Discord 連線失敗：{exc.__class__.__name__}") from exc
    if res.status_code not in (200, 204):
        raise ChatError(f"Discord 發送失敗（HTTP {res.status_code}）")


async def _send(session: Session, target: str, text: str) -> None:
    get = lambda key: settings_store.get_value(session, key)  # noqa: E731
    if target == "telegram":
        await send_telegram(get("telegram_token"), get("telegram_chat_id"), text)
    else:
        await send_discord(get("discord_webhook"), text)


async def send_test(session: Session, target: str) -> tuple[bool, str]:
    try:
        await _send(session, target, "[Pinakes] 測試訊息，收到代表設定正確。")
    except ChatError as exc:
        return False, str(exc)
    return True, "測試訊息已送出"


async def notify(session: Session, results: list[dict]) -> list[str]:
    if not results:
        return []
    text = build_text(results)
    errors = []
    for target in ("telegram", "discord"):
        if settings_store.get_value(session, f"{target}_enabled") != "true":
            continue
        try:
            await _send(session, target, text)
        except ChatError as exc:
            errors.append(str(exc))
    return errors
