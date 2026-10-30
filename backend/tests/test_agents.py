import pytest

from app.agents.router import classify_rules, plan_for
from tests.conftest import chat


@pytest.mark.parametrize("text,ctx,intent", [
    ("Where is my order ORD-1001?", False, "order_status"),
    ("Can I return it?", True, "return_eligibility"),
    ("What is your return policy?", False, "policy_question"),
    ("I want a refund for ORD-1002", False, "refund_request"),
    ("What's the status of my refund?", False, "refund_status"),
    ("Recommend noise-cancelling headphones under $300", False, "product_recommendation"),
    ("Show me my order history", False, "order_history"),
    ("Please start a return for ORD-1002", False, "return_request"),
    ("Can I cancel ORD-1004?", False, "cancellation"),
    ("hello", False, "greeting"),
])
def test_rule_router(text, ctx, intent):
    assert classify_rules(text, has_order_context=ctx)[0] == intent


def test_return_question_plans_two_agents():
    assert plan_for(["return_eligibility"]) == [
        "returns_agent",
        "knowledge_agent",
    ]


def test_graph_routes_and_calls_tools(client, pardha):
    m = chat(
        client,
        pardha,
        "Where is my order ORD-1001?"
    )["message"]["meta"]

    assert m["agent_path"] == ["supervisor", "order_agent"]
    assert [t["tool"] for t in m["tools"]] == ["get_order_status"]


def test_multi_agent_coordination(client, pardha):
    m = chat(
        client,
        pardha,
        "Can I return ORD-1002?"
    )["message"]["meta"]

    assert m["agent_path"] == [
        "supervisor",
        "returns_agent",
        "knowledge_agent",
    ]

    assert {
        "check_return_eligibility",
        "search_knowledge_base",
    } <= {t["tool"] for t in m["tools"]}

    assert m["citations"]


def test_graph_structure_is_real_langgraph():
    from app.agents.graph import get_refund_graph, get_support_graph

    nodes = set(get_support_graph().get_graph().nodes)

    assert {
        "intake",
        "supervisor",
        "order_agent",
        "knowledge_agent",
        "returns_agent",
        "product_agent",
        "respond",
    } <= nodes

    assert "human_approval" in set(
        get_refund_graph().get_graph().nodes
    )


def test_product_recommendations(client, pardha):
    r = chat(
        client,
        pardha,
        "Recommend a fitness watch under $250"
    )

    assert "Pulse Active Smartwatch" in r["message"]["content"]

    assert "Pulse Trail Ultra Watch" not in r["message"]["content"]


def test_refund_citations_scoped_to_refund_policy(
    client,
    pardha,
    fresh_db
):
    m = chat(
        client,
        pardha,
        "I want a refund for ORD-1002"
    )["message"]["meta"]

    assert m["citations"]

    assert all(
        c["doc_title"] == "Refund Policy"
        for c in m["citations"]
    )


# ------------------------------------------------------------
# Multi-Intent Agent Coordination Test
# ------------------------------------------------------------

def test_multi_intent_order_cancellation_and_return_policy(
    client,
    pardha
):
    question = (
        "Can you tell me where ORD-1001 is, whether I can cancel it, "
        "and what the return policy is if it arrives?"
    )

    response = chat(client, pardha, question)["message"]

    content = response["content"].lower()
    meta = response["meta"]

    # --------------------------------------------------------
    # Debugging information
    # --------------------------------------------------------

    print("\n=== MULTI-INTENT DEBUG ===")

    print("Intents:", meta.get("intents"))

    print("Agent path:", meta.get("agent_path"))

    print(
        "Citations:",
        [
            c["doc_title"]
            for c in meta.get("citations", [])
        ]
    )

    print("Response:", response["content"])

    print("==========================\n")

    # --------------------------------------------------------
    # Test 1: Orders Agent
    # --------------------------------------------------------

    assert "order_agent" in meta["agent_path"]

    assert "get_order_status" in [
        t["tool"]
        for t in meta["tools"]
    ]

    # --------------------------------------------------------
    # Test 2: Knowledge Agent
    # --------------------------------------------------------

    assert "knowledge_agent" in meta["agent_path"]

    assert "search_knowledge_base" in [
        t["tool"]
        for t in meta["tools"]
    ]

    # --------------------------------------------------------
    # Test 3: Cancellation and return topics
    # --------------------------------------------------------

    assert "cancel" in content

    assert "return" in content

    # --------------------------------------------------------
    # Test 4: Policy citations
    # --------------------------------------------------------

    assert meta["citations"], "Expected policy citations"

    # --------------------------------------------------------
    # Test 5: No contradictory fallback message
    # --------------------------------------------------------

    assert (
        "i couldn't find that in vsr store's policy documents"
        not in content
    )