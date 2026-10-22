"""LangChain StructuredTool wrappers bound to an authenticated ToolContext.

Used by the LLM tool-calling loop. The context (and so the customer identity) is
captured by closure, never passed by the model.
"""
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.core import TOOL_FUNCTIONS, ToolContext, ToolError, run_tool


class OrderIdInput(BaseModel):
    order_id: str = Field(description="Order number such as ORD-1001")


class OrdersInput(BaseModel):
    limit: int = Field(10, ge=1, le=50)


class ProductSearchInput(BaseModel):
    query: str = Field(description="What the customer is looking for")
    category: str | None = Field(None, description="Audio, Wearables, Home Office, Kitchen, Outdoor, Accessories, Gift Cards")
    max_price: float | None = Field(None, gt=0)
    limit: int = Field(5, ge=1, le=10)


class KBInput(BaseModel):
    query: str = Field(max_length=500)
    k: int = Field(5, ge=1, le=10)


class ReasonInput(BaseModel):
    order_id: str
    reason: str = Field(min_length=3, max_length=255)


class RefundStatusInput(BaseModel):
    order_id: str | None = None
    refund_id: str | None = None


SCHEMAS = {
    "get_order_status": (OrderIdInput, "Current shipping status and delivery estimate for one order."),
    "get_order_details": (OrderIdInput, "Items, totals, address and status for one order."),
    "get_customer_orders": (OrdersInput, "List the signed-in customer's recent orders."),
    "search_products": (ProductSearchInput, "Search the product catalog."),
    "search_knowledge_base": (KBInput, "Search company policy documents."),
    "check_return_eligibility": (OrderIdInput, "Check whether an order can be returned or refunded."),
    "create_return_request": (ReasonInput, "Create a return (RMA) for an eligible order."),
    "get_refund_status": (RefundStatusInput, "Look up refund requests and their status."),
    # create_refund_request is deliberately NOT exposed to the LLM: refunds go
    # through the Returns agent's human-approval subgraph only.
}


def build_tools(ctx: ToolContext, names: list[str]) -> list[StructuredTool]:
    tools = []
    for name in names:
        schema, desc = SCHEMAS[name]
        fn = TOOL_FUNCTIONS[name]

        def _call(_name=name, _fn=fn, **kwargs):
            try:
                return run_tool(ctx, _name, _fn, **kwargs)
            except ToolError as e:
                return {"error": str(e)}

        tools.append(StructuredTool.from_function(func=_call, name=name, description=desc, args_schema=schema))
    return tools
