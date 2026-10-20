import asyncio
import html
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from sqlmodel import Session

from app.services import settings_store

TIMEOUT = 15

STATUS_TEXT = {
    "done": "已整理",
    "pending_review": "待確認",
    "failed": "失敗",
    "skipped": "已略過",
    "planned": "待執行",
    "synced": "已同步",
}


class MailError(Exception):
    pass


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    security: str
    sender: str
    to: str


def load_config(session: Session) -> SmtpConfig:
    get = lambda key: settings_store.get_value(session, key)  # noqa: E731
    host, to = get("smtp_host"), get("notify_to")
    sender = get("smtp_from") or get("smtp_user")
    if not host or not to or "@" not in sender:
        raise MailError("SMTP 主機、寄件人或收件人尚未設定")
    try:
        port = int(get("smtp_port"))
    except ValueError:
        port = 587
    return SmtpConfig(
        host, port, get("smtp_user"), get("smtp_password"),
        get("smtp_security"), sender, to,
    )


def line(item: dict) -> str:
    name = item.get("source", "")
    detail = item.get("target") or item.get("error") or item.get("reason") or ""
    return f"{name} -> {detail}" if detail else name


def build_digest(results: list[dict], cfg: SmtpConfig) -> EmailMessage:
    groups: dict[str, list[dict]] = {}
    for item in results:
        groups.setdefault(item["status"], []).append(item)
    parts = [
        f"{STATUS_TEXT.get(k, k)} {len(v)} 項"
        for k, v in groups.items()
    ]
    msg = EmailMessage()
    msg["Subject"] = "[Pinakes] " + "、".join(parts)
    msg["From"] = cfg.sender
    msg["To"] = cfg.to

    text, rows = [], []
    for status, items in groups.items():
        label = STATUS_TEXT.get(status, status)
        text.append(f"{label}（{len(items)}）")
        text.extend(f"  {line(i)}" for i in items)
        text.append("")
        rows.append(f"<h3>{html.escape(label)}（{len(items)}）</h3><ul>")
        rows.extend(f"<li>{html.escape(line(i))}</li>" for i in items)
        rows.append("</ul>")
    if "pending_review" in groups:
        text.append("待確認的項目需要到 Pinakes 手動選擇。")
        rows.append("<p>待確認的項目需要到 Pinakes 手動選擇。</p>")
    msg.set_content("\n".join(text))
    msg.add_alternative("<html><body>" + "".join(rows) + "</body></html>", subtype="html")
    return msg


def send(cfg: SmtpConfig, msg: EmailMessage) -> None:
    try:
        if cfg.security == "ssl":
            server = smtplib.SMTP_SSL(
                cfg.host, cfg.port, timeout=TIMEOUT,
                context=ssl.create_default_context(),
            )
        else:
            server = smtplib.SMTP(cfg.host, cfg.port, timeout=TIMEOUT)
        with server:
            if cfg.security == "starttls":
                server.starttls(context=ssl.create_default_context())
            if cfg.user:
                server.login(cfg.user, cfg.password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError("SMTP 帳號或密碼錯誤") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError(f"寄信失敗：{exc.__class__.__name__}") from exc


async def send_test(session: Session) -> tuple[bool, str]:
    try:
        cfg = load_config(session)
        msg = EmailMessage()
        msg["Subject"] = "[Pinakes] 測試信"
        msg["From"] = cfg.sender
        msg["To"] = cfg.to
        msg.set_content("這是 Pinakes 的測試信，收到代表 SMTP 設定正確。")
        await asyncio.to_thread(send, cfg, msg)
    except MailError as exc:
        return False, str(exc)
    return True, "測試信已寄出"


async def notify(session: Session, results: list[dict]) -> None:
    if settings_store.get_value(session, "notify_enabled") != "true" or not results:
        return
    cfg = load_config(session)
    await asyncio.to_thread(send, cfg, build_digest(results, cfg))
