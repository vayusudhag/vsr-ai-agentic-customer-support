# VSR AI — Demo guide

All five required scenarios, plus four extras, are reproducible on a freshly seeded database (`python -m app.seed`). Order dates are generated relative to seeding time, so delivery estimates and return windows stay realistic whenever you seed. The scripted version of this walkthrough is `scripts/browser_e2e.py`, which produced the screenshots in `docs/screenshots/`.

## Seeded scenarios

| Order | Customer | Situation | Expected eligibility |
|---|---|---|---|
| ORD-1001 | Alex | Shipped, arriving in ~4 days | Not returnable (not delivered) |
| ORD-1002 | Alex | Delivered 10 days ago (watch + charger, $238) | Returnable, 20 days left |
| ORD-1003 | Alex | Delivered 45 days ago | Outside the 30-day window |
| ORD-1004 | Alex | Processing | Not returnable; can be cancelled |
| ORD-1005 | Alex | Delivered gift card | Final sale |
| ORD-1006 | Priya | Delivered chair | Invisible to Alex |
| ORD-1007 | Priya | In transit | — |
| ORD-1008 | Priya | Cancelled | — |
| ORD-1009 onward | 8 customers | Mixed statuses (44 orders total) | Varies |

## Demo 1 — Order status

1. Sign in as **Alex Morgan (customer)** and open **Support chat**.
2. Ask: `Where is my order ORD-1001?`

**Expected:** "Your order **ORD-1001** has shipped with FedEx (tracking …) and is expected to arrive on **‹date›**." The route strip shows Supervisor › Orders with `get_order_status()`.

## Demo 2 — Return policy question (RAG with citations)

1. Ask: `How many days do I have to return something?`

**Expected:** Sentences from the Return Policy with `[1]` markers. Click **policy sources** to see the section, similarity score and excerpt. Route: Supervisor › Knowledge.

Variation: ask `Do you offer student discounts?`. VSR AI says the information isn't in the policy documents and offers a human agent. It does not invent a policy.

## Demo 3 — Refund with human approval

1. As Alex, ask: `Can I return ORD-1002?`. It is eligible, with 20 days left; the route is Returns › Knowledge.
2. Ask: `I'd like a refund for it, the strap broke`.
   - **Expected:** refund **RF-XXXX** for **$238.00**. The fee is waived because "broke" signals a defect; without a defect the amount is $230.05 after the $7.95 return-shipping deduction.
   - An amber card shows the refund is waiting for admin approval.
   - Tools called: `check_return_eligibility()`, `create_refund_request()`, `search_knowledge_base()`.
   - The approval workflow is now paused at its `interrupt()`.
3. Optional: ask the same refund again. VSR AI refuses, because a refund is already pending.
4. Sign out and sign in as **Jordan Lee (admin)**. The **VSR AI Dashboard** shows *Pending approvals: 1* and the request in the amber queue.
5. Add a note, then click **Approve** (or **Reject**). The decision appears under *Recent decisions* with the approver, timestamp and a `SIM-TXN-…` id.
6. Sign back in as Alex and open the conversation.
   - **Expected:** a new message tagged *Decision from VSR support team* (route: Human approval › Returns & Refunds).
   - The earlier amber card now reads "was approved by the support team".
   - **Returns & refunds** shows the status as approved.

Security checks you can try:
- As Alex, a `POST /api/admin/refunds/{id}/decision` returns **403**.
- Approving the same refund twice returns **409**.

## Demo 4 — Product recommendations

1. Ask: `Recommend noise-cancelling headphones under $300`.

**Expected:** Halden Aria Pro Headphones ($249) and Halden Aria Wireless Earbuds ($89), each with a rating and a reason ("matches headphones, noise-cancelling, within your $300.00 budget"). Nothing over $300 appears. Route: Supervisor › Products with `search_products()`.

## Demo 5 — Follow-up using conversation memory

1. Start a **New conversation** and ask `Where is my order ORD-1001?`.
2. Ask: `Can I return it?`.

**Expected:** "(Using ORD-1001 from earlier in our conversation.) **ORD-1001** isn't eligible for a return right now. The order is currently 'shipped'…", followed by Return Policy citations.

Then:
- Ask `Can I return it?` in a *new* conversation. VSR AI asks which order you mean and lists your recent orders, which shows memory is per conversation.
- Reload the page and reopen the first conversation from **History**. The thread is restored, and follow-ups still resolve "it", because the LangGraph checkpoint persists.

## Extra scenarios

- **Cross-customer protection:** as Alex, ask `Where is ORD-1006?`. The reply is "I couldn't find order ORD-1006 on your account." Priya sees it normally.
- **Multi-agent cancellation:** ask `Can I cancel ORD-1004?`. The route is Orders › Knowledge, combining live order status with the Cancellation Policy.
- **Ineligible returns:** ask `Can I return ORD-1003?` (outside the window) and `Can I return ORD-1005?` (final-sale gift card).
- **Evaluation:** open **AI evaluation** to see the latest run, the deterministic-vs-LLM split, run history, and known failures.
