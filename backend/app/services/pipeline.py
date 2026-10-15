from sqlmodel import Session, select

from app.models import ParseRule
from app.services import rules
from app.services.parser import ParsedMedia, finalize, parse_path


def parse_file(session: Session, parts: list[str]) -> ParsedMedia:
    parsed = parse_path(parts)
    name = parts[-1]
    stem = name[: len(name) - len(parsed.ext)] if parsed.ext else name
    stmt = (
        select(ParseRule)
        .where(ParseRule.enabled)
        .order_by(ParseRule.priority, ParseRule.id)
    )
    parsed = rules.apply_rules(list(session.exec(stmt)), stem, parsed)
    finalize(parsed)
    return parsed
