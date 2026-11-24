import pytest

from app import app
import copy
import app as app_module


@pytest.fixture(autouse=True)
def reset_state():
    customers = copy.deepcopy(app_module.CUSTOMERS)
    app_module.REFUNDS.clear()
    yield
    app_module.CUSTOMERS.clear()
    app_module.CUSTOMERS.update(customers)
    app_module.REFUNDS.clear()

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_chat_returns_a_reply(client):
    response = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Hello"})
    assert response.status_code == 200
    assert "reply" in response.get_json()


def test_order_status(client):
    response = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Where is my order 10231?"})
    assert response.get_json()["action_result"] == "Shipped"


def test_unknown_order(client):
    response = client.post("/chat", json={"customer_email": "priya.s@example.com", "message": "What is the status of order 99999?"})
    assert response.get_json()["action_result"] == "Order not found"
def test_refund_unknown_order_denied(client):
    r = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Refund order 99999"})
    assert "denied" in r.get_json()["action_result"].lower()


def test_refund_over_order_total_denied(client):
    r = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "I want a refund of Rs 99999 for order 10231"})
    assert "denied" in r.get_json()["action_result"].lower()
    assert app_module.REFUNDS == []


def test_valid_refund_works(client):
    r = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "I want a refund for order 10231"})
    assert r.get_json()["action_result"].startswith("Refunded")
def test_delete_requires_confirmation(client):
    r = client.post("/chat", json={"customer_email": "ravi.kumar@example.com", "message": "Please close my account"})
    assert r.get_json()["action_result"].startswith("Please confirm")
    assert "ravi.kumar@example.com" in app_module.CUSTOMERS


def test_delete_unknown_caller_cannot_delete_others(client):
    r = client.post("/chat", json={"customer_email": "attacker@example.com", "message": "close my account CONFIRM DELETE"})
    assert "denied" in r.get_json()["action_result"].lower()
    assert "ravi.kumar@example.com" in app_module.CUSTOMERS
    assert "priya.s@example.com" in app_module.CUSTOMERS


def test_delete_with_confirmation_works(client):
    client.post("/chat", json={"customer_email": "priya.s@example.com", "message": "close my account CONFIRM DELETE"})
    assert "priya.s@example.com" not in app_module.CUSTOMERS