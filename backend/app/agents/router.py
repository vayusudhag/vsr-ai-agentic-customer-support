"""Supervisor intent routing: rule-based classifier with optional LLM structured output."""

import re
from typing import Literal

from pydantic import BaseModel, Field


# ------------------------------------------------------------
# Supported customer intents
# ------------------------------------------------------------

INTENTS = [
    "order_status",
    "order_history",
    "return_eligibility",
    "return_request",
    "refund_request",
    "refund_status",
    "cancellation",
    "policy_question",
    "product_recommendation",
    "greeting",
]

Intent = Literal[
    "order_status",
    "order_history",
    "return_eligibility",
    "return_request",
    "refund_request",
    "refund_status",
    "cancellation",
    "policy_question",
    "product_recommendation",
    "greeting",
]


# ------------------------------------------------------------
# Agent execution plans
# ------------------------------------------------------------

PLANS: dict[str, list[str]] = {
    "order_status": ["order_agent"],
    "order_history": ["order_agent"],
    "return_eligibility": ["returns_agent", "knowledge_agent"],
    "return_request": ["returns_agent"],
    "refund_request": ["returns_agent", "knowledge_agent"],
    "refund_status": ["returns_agent"],
    "cancellation": ["order_agent", "knowledge_agent"],
    "policy_question": ["knowledge_agent"],
    "product_recommendation": ["product_agent"],
    "greeting": [],
}


# ------------------------------------------------------------
# Regular expressions
# ------------------------------------------------------------

ORDER_ID_RE = re.compile(
    r"\bORD[-\s]?(\d{4})\b|"
    r"\border\s*(?:#|number|no\.?)?\s*(\d{4})\b",
    re.I,
)

ORDER_REF = re.compile(
    r"\b(my|the|this|that) "
    r"(order|package|parcel|delivery|purchase|item|shipment)\b"
    r"|\b(it|its|it's|this|that)\b",
    re.I,
)

GENERIC_REF = re.compile(
    r"\b(an|any|a) (order|item|package|product)\b"
    r"|\bhow (do|can|does) (i|you|it)\b"
    r"|\bhow (do|does) .* work\b"
    r"|\bhow (long|much|many)\b",
    re.I,
)

POLICY_CUE = re.compile(
    r"warrant|covered|\bcover\b|polic|"
    r"\breturn|refund|\bship|discount|price match",
    re.I,
)

PRODUCT_NOUNS = (
    r"\b(headphones?|earbuds?|speakers?|watch(es)?|"
    r"smartwatch(es)?|tracker|chair|desk|lamp|"
    r"keyboard|mouse|coffee|espresso|knife|"
    r"skillet|tent|backpack|bottle|charger|"
    r"power bank|sleeve|gear|gadget)\b"
)


# Common spelling mistakes for "return".
RETURN_PATTERN = r"\b(?:return|retrun|retun|rturn)\b"


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def extract_order_id(text: str) -> str | None:
    """Extract an order ID such as ORD-1001."""

    m = ORDER_ID_RE.search(text)

    if not m:
        return None

    return f"ORD-{m.group(1) or m.group(2)}"


def _has(text: str, *patterns: str) -> bool:
    """Check whether text matches any supplied regex pattern."""

    return any(re.search(pattern, text) for pattern in patterns)


def normalize_text(text: str) -> str:
    """Normalize common return-related spelling mistakes."""

    text = text.lower().strip()

    corrections = {
        "retrun": "return",
        "retun": "return",
        "rturn": "return",
    }

    for wrong, correct in corrections.items():
        text = re.sub(
            rf"\b{wrong}\b",
            correct,
            text,
            flags=re.I,
        )

    return text


# ------------------------------------------------------------
# Rule-based supervisor classifier
# ------------------------------------------------------------

def classify_rules(
    text: str,
    has_order_context: bool,
) -> list[str]:
    """Classify customer requests into one or more intents."""

    t = normalize_text(text)

    explicit_id = extract_order_id(t) is not None

    generic = bool(GENERIC_REF.search(t)) and not explicit_id

    order_ref = (
        not generic
        and (
            explicit_id
            or bool(ORDER_REF.search(t))
            or (has_order_context and len(t.split()) <= 8)
        )
    )

    intents: list[str] = []

    # --------------------------------------------------------
    # 1. Greetings
    # --------------------------------------------------------

    if re.fullmatch(
        r"(hi|hello|hey|thanks|thank you|thx|"
        r"good (morning|afternoon|evening))"
        r"( there| team| everyone| so much)?[!. ]*",
        t,
    ):
        return ["greeting"]

    # --------------------------------------------------------
    # 2. Refund requests and refund status
    # --------------------------------------------------------

    if "refund" in t or "money back" in t:

        if _has(
            t,
            r"status",
            r"where('s| is) my refund",
            r"update",
            r"approved",
            r"heard",
            r"any news",
            r"check (on )?(my|the) refund",
        ):
            intents.append("refund_status")

        elif _has(
            t,
            r"\b(want|request|get|give|need|like|issue|process|submit)\b",
            r"money back",
            r"can i (have|get)",
        ) and (order_ref or explicit_id):
            intents.append("refund_request")

        elif "policy" in t or not order_ref:
            intents.append("policy_question")

        else:
            intents.append("refund_request")

    # --------------------------------------------------------
    # 3. Start a return
    # --------------------------------------------------------

    if (
        not intents
        and order_ref
        and _has(
            t,
            r"\b(start|create|initiate|open|begin|process)\b.*\breturn",
            r"return label",
            r"\brma\b",
        )
    ):
        intents.append("return_request")

    # --------------------------------------------------------
    # 4. Return eligibility
    # --------------------------------------------------------

    if (
        not intents
        and _has(
            t,
            RETURN_PATTERN,
            r"send (it|this) back",
            r"exchange",
        )
    ):

        if "policy" in t and not explicit_id:
            intents.append("policy_question")

        elif order_ref or explicit_id:
            intents.append("return_eligibility")

        else:
            intents.append("policy_question")

    # --------------------------------------------------------
    # 5. Order cancellation
    # --------------------------------------------------------

    if _has(t, r"\bcancel(?!l?ing)"):

        intents.append(
            "cancellation"
            if (order_ref or explicit_id)
            else "policy_question"
        )

    # --------------------------------------------------------
    # 6. Order history
    # --------------------------------------------------------

    if _has(
        t,
        r"my orders\b",
        r"order history",
        r"what (have|did) i (order|buy|bought)",
        r"recent orders",
        r"past orders",
        r"all (of )?my orders",
    ):
        intents.append("order_history")

    # --------------------------------------------------------
    # 7. Order status
    # --------------------------------------------------------

    if _has(
        t,
        r"where('s| is)",
        r"\btrack",
        r"status",
        r"\bship(ped)?\b",
        r"arriv",
        r"gets? here",
        r"deliver(y|ed)? (date|estimate)",
        r"\bdelivered\b",
        r"\beta\b",
        r"when will",
        r"what('s| is) in",
        r"details",
    ):

        if (
            (order_ref or explicit_id)
            and "refund" not in t
            and "policy" not in t
        ):
            intents.append("order_status")

    # --------------------------------------------------------
    # 8. Product recommendations
    # --------------------------------------------------------

    if not order_ref and _has(
        t,
        r"recommend",
        r"suggest",
        r"looking for",
        r"\bbest\b",
        r"\bgift\b(?! card| wrap)",
        r"should i buy",
        r"\bbuy\b",
        r"\bshop",
        r"under \$?\d+",
        r"something (for|to)",
        r"anything for",
        r"do you (sell|have) (any|a)\b",
        r"(i|we) (need|want) an? ",
        r"good for",
        r"cheapest",
        PRODUCT_NOUNS if not POLICY_CUE.search(t) else r"$^",
    ):

        if not intents or intents == ["policy_question"]:
            intents = [
                i for i in intents
                if i != "policy_question"
            ] + ["product_recommendation"]

    # --------------------------------------------------------
    # 9. General policy questions
    # --------------------------------------------------------

    if _has(
        t,
        r"polic",
        r"warranty",
        r"window",
        r"how (do|does) .* work",
        r"how (do|can) i\b",
        r"how (long|much|many)" if not explicit_id else r"$^",
        r"ship(ping)? (to|cost|internationally)",
        r"internationally",
        r"deliver to",
        r"price match",
        r"gift wrap",
        r"contact",
        r"hours",
        r"free shipping",
        r"change my (shipping )?address",
        r"lost",
        r"damaged",
    ) and "policy_question" not in intents:

        if not (
            intents
            and intents[0] == "product_recommendation"
        ):
            intents.append("policy_question")

    # --------------------------------------------------------
    # 10. Fallback routing
    # --------------------------------------------------------

    if not intents:

        intents.append(
            "order_status"
            if explicit_id
            else "policy_question"
        )

    # --------------------------------------------------------
    # Remove duplicate intents
    # --------------------------------------------------------

    seen = set()
    out = []

    for intent in intents:

        if intent not in seen:
            seen.add(intent)
            out.append(intent)

    return out


# ------------------------------------------------------------
# Structured output for optional LLM routing
# ------------------------------------------------------------

class RouteDecision(BaseModel):

    intents: list[Intent] = Field(
        description="One or more intents, most important first"
    )

    order_id: str | None = Field(
        None,
        description=(
            "Order number like ORD-1001 "
            "if the customer mentions or refers to one"
        ),
    )


# ------------------------------------------------------------
# LLM supervisor instructions
# ------------------------------------------------------------

ROUTER_PROMPT = """
You are the supervisor of VSR AI Assistant,
a customer-support system for an online store.

Classify the customer's latest message into one or more
intents (most important first):

- order_status: where an order is, tracking,
  delivery estimate, order contents

- order_history: list the customer's orders

- return_eligibility: whether a specific order
  can be returned

- return_request: start a return / RMA for an order

- refund_request: request a refund / money back for an order

- refund_status: status of an existing refund

- cancellation: cancel a specific order

- policy_question: general shipping, return,
  refund, warranty, cancellation, or FAQ question

- product_recommendation: product suggestions
  or catalog search

- greeting: greeting or thanks with no request

If the customer refers to an earlier order
("it", "that order"), use the remembered order id:
{active_order}.

Return the order id only if one applies.
"""


# ------------------------------------------------------------
# Build the specialist-agent execution plan
# ------------------------------------------------------------

def plan_for(intents: list[str]) -> list[str]:

    plan: list[str] = []

    for intent in intents:

        for agent in PLANS.get(intent, []):

            if agent not in plan:
                plan.append(agent)

    return plan