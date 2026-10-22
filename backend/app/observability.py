"""Structured logging with sensitive-data redaction."""
import logging
import re
from typing import Any

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE = re.compile(r"\+?\d{1,2}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._-]+)")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        v = SECRET.sub("[REDACTED_SECRET]", value)
        v = CARD.sub("[REDACTED_NUMBER]", v)
        v = EMAIL.sub("[REDACTED_EMAIL]", v)
        return PHONE.sub("[REDACTED_PHONE]", v)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in {"password", "token", "api_key", "authorization"} else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(a) for a in record.args) if isinstance(record.args, tuple) else redact(record.args)
        return True


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("vsr_ai")
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        h.addFilter(RedactingFilter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
