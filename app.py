"""Customer Support Bot (Day 7 Challenge: risk review).

A small Flask app. A customer sends a message, the LLM decides on a reply
and an action, and the app carries out the action.
"""
import json
import logging
import time
import uuid

from flask import Flask, jsonify, request

from llm import call_llm

app = Flask(__name__)

API_KEY = "sk-demo-4f9a2c71-FAKE-KEY-for-training-only"

PRICE_PER_TOKEN_INR = 0.0005  # made-up price
MODEL_NAME = "support-bot-fake-llm"

logging.basicConfig(filename="logs/app.log", level=logging.INFO)

ORDERS = {
    "10231": {"status": "Shipped", "amount": 1299},
    "10232": {"status": "Delivered", "amount": 499},
    "10233": {"status": "Processing", "amount": 2499},
}
CUSTOMERS = {
    "ravi.kumar@example.com": {"name": "Ravi Kumar", "phone": "+91 98480 12345", "active": True},
    "priya.s@example.com": {"name": "Priya Sharma", "phone": "+91 99890 67890", "active": True},
}
REFUNDS = []


# ---------- Tools the LLM can use ----------

def get_order_status(order_id):
    order = ORDERS.get(order_id)
    return order["status"] if order else "Order not found"


def issue_refund(order_id, amount):
    order = ORDERS.get(str(order_id))
    if not order:
        return "Refund denied: order not found"
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "Refund denied: invalid amount"
    if amount <= 0 or amount > order["amount"]:
        return "Refund denied: amount exceeds the order total"
    if any(r["order_id"] == str(order_id) for r in REFUNDS):
        return "Refund denied: order already refunded"
    REFUNDS.append({"order_id": str(order_id), "amount": amount})
    return f"Refunded Rs {amount} for order {order_id}"


def delete_customer_account(customer_email, requester_email=None, confirmed=False):
    if customer_email not in CUSTOMERS:
        return "Deletion denied: account not found"
    if requester_email != customer_email:
        return "Deletion denied: identity not verified"
    if not confirmed:
        return "Please confirm: reply CONFIRM DELETE to permanently delete your account"
    CUSTOMERS.pop(customer_email, None)
    return f"Deleted account {customer_email}"


TOOLS = {
    "get_order_status": get_order_status,
    "issue_refund": issue_refund,
    "delete_customer_account": delete_customer_account,
}


# ---------- Chat endpoint ----------

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    email = data.get("customer_email", "")
    message = data.get("message", "")
    customer = CUSTOMERS.get(email, {})

    prompt = (
        "You are a helpful support agent. Reply in JSON with reply, action and args.\n"
        f"Customer name: {customer.get('name')}\n"
        f"Customer email: {email}\n"
        f"Customer phone: {customer.get('phone')}\n"
        f"Customer message: {message}"
    )

    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    text, usage = call_llm(prompt, API_KEY)
    latency_ms = int((time.perf_counter() - start) * 1000)
    cost_inr = (usage["input_tokens"] + usage["output_tokens"]) * PRICE_PER_TOKEN_INR
    logging.info(
        "request_id=%s model=%s latency_ms=%d input_tokens=%d output_tokens=%d cost_inr=%.4f",
        request_id, MODEL_NAME, latency_ms,
        usage["input_tokens"], usage["output_tokens"], cost_inr,
    )

    result = json.loads(text)

    action = result.get("action")
    action_result = None
    if action:
        args = result.get("args", {})
        if args.get("customer_email") == "from_request":
            args["customer_email"] = email
        if action == "delete_customer_account":
            # never trust the AI's choice of account: use the caller's own email
            args = {
                "customer_email": email,
                "requester_email": email,
                "confirmed": "confirm delete" in message.lower(),
            }
        action_result = TOOLS[action](**args)

    reply_text = result["reply"]
    if isinstance(action_result, str) and action_result.startswith(
        ("Refund denied", "Deletion denied", "Please confirm")
    ):
        reply_text = action_result  # don't let the AI claim success when the action was blocked

    return jsonify({"reply": reply_text, "action_result": action_result})


if __name__ == "__main__":
    app.run(debug=True)