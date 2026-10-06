"""Mock tools for customer support agent."""

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)


# In-memory mock data
mock_customers = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-0101",
        "signup_date": "2024-01-15",
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "phone": "+1-555-0102",
        "signup_date": "2024-03-22",
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Alice Johnson",
        "email": "alice.j@example.com",
        "phone": "+1-555-0103",
        "signup_date": "2024-05-10",
    },
}

mock_orders = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_id": "CUST-001",
        "items": [
            {"product_id": "P001", "name": "Wireless Mouse", "quantity": 1, "price": 29.99},
            {"product_id": "P002", "name": "Keyboard", "quantity": 1, "price": 59.99},
        ],
        "status": "shipped",
        "shipping_address": "123 Main St, Anytown, USA 12345",
        "shipping_date": "2026-09-25",
        "estimated_delivery": "2026-09-28",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_id": "CUST-002",
        "items": [
            {"product_id": "P003", "name": "Monitor 27\"", "quantity": 1, "price": 299.99},
        ],
        "status": "processing",
        "shipping_address": "456 Oak Ave, Somecity, USA 45678",
        "shipping_date": None,
        "estimated_delivery": "2026-10-02",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_id": "CUST-003",
        "items": [
            {"product_id": "P004", "name": "Webcam", "quantity": 1, "price": 79.99},
            {"product_id": "P005", "name": "Headset", "quantity": 1, "price": 129.99},
        ],
        "status": "delivered",
        "shipping_address": "789 Pine Rd, Anycity, USA 78901",
        "shipping_date": "2026-09-20",
        "estimated_delivery": "2026-09-23",
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_id": "CUST-001",
        "items": [
            {"product_id": "P006", "name": "USB-C Hub", "quantity": 2, "price": 39.99},
        ],
        "status": "delivered",
        "shipping_address": "123 Main St, Anytown, USA 12345",
        "shipping_date": "2026-09-15",
        "estimated_delivery": "2026-09-18",
    },
}

mock_payments = {
    "ORD-1001": {"payment_status": "paid", "paid_at": "2026-09-24", "method": "Credit Card"},
    "ORD-1002": {"payment_status": "pending", "paid_at": None, "method": "Credit Card"},
    "ORD-1003": {"payment_status": "paid", "paid_at": "2026-09-19", "method": "PayPal"},
    "ORD-1004": {"payment_status": "paid", "paid_at": "2026-09-14", "method": "Credit Card"},
}

mock_tickets = {
    "TICKET-2026-001": {
        "ticket_id": "TICKET-2026-001",
        "customer_id": "CUST-003",
        "issue": "Order not delivered",
        "status": "pending",
        "created_at": "2026-09-26",
    },
    "TICKET-2026-002": {
        "ticket_id": "TICKET-2026-002",
        "customer_id": "CUST-001",
        "issue": "Wrong item received",
        "status": "in_progress",
        "created_at": "2026-09-25",
    },
}


def get_customer(customer_id: str) -> dict[str, Any] | None:
    """Get customer information.

    Args:
        customer_id: Customer ID (e.g., "CUST-001").

    Returns:
        Customer data dict or None if not found.

    Raises:
        ValueError: If customer_id format is invalid.
    """
    logger.info(f"Tool called: get_customer(customer_id={customer_id})")

    if not customer_id or not isinstance(customer_id, str):
        raise ValueError(f"Invalid customer_id: {customer_id}")

    customer = mock_customers.get(customer_id)

    logger.info(
        f"Tool result: get_customer returned customer="
        f"{customer['customer_id'] if customer else None}"
    )

    return customer


def get_order(order_id: str) -> dict[str, Any] | None:
    """Get order information.

    Args:
        order_id: Order ID (e.g., "ORD-1001").

    Returns:
        Order data dict or None if not found.

    Raises:
        ValueError: If order_id format is invalid.
    """
    logger.info(f"Tool called: get_order(order_id={order_id})")

    if not order_id or not isinstance(order_id, str):
        raise ValueError(f"Invalid order_id: {order_id}")

    order = mock_orders.get(order_id)

    if order:
        logger.info(f"Tool result: get_order returned order={order['order_id']}")
    else:
        logger.warning(f"Tool result: get_order returned None for order_id={order_id}")

    return order


def check_payment(order_id: str) -> dict[str, Any] | None:
    """Get payment status for an order.

    Args:
        order_id: Order ID (e.g., "ORD-1001").

    Returns:
        Payment status dict or None if not found.

    Raises:
        ValueError: If order_id format is invalid.
    """
    logger.info(f"Tool called: check_payment(order_id={order_id})")

    if not order_id or not isinstance(order_id, str):
        raise ValueError(f"Invalid order_id: {order_id}")

    payment = mock_payments.get(order_id)

    if payment:
        logger.info(
            f"Tool result: check_payment returned payment_status={payment['payment_status']}"
        )
    else:
        logger.warning(f"Tool result: check_payment returned None for order_id={order_id}")

    return payment


def create_support_ticket(customer_id: str, issue: str) -> dict[str, Any] | None:
    """Create a support ticket.

    Args:
        customer_id: Customer ID (e.g., "CUST-001").
        issue: Description of the issue.

    Returns:
        Ticket data dict or None if creation failed.

    Raises:
        ValueError: If customer_id or issue format is invalid.
    """
    logger.info(f"Tool called: create_support_ticket(customer_id={customer_id}, issue={issue})")

    if not customer_id or not isinstance(customer_id, str):
        raise ValueError(f"Invalid customer_id: {customer_id}")

    if not issue or not isinstance(issue, str) or len(issue.strip()) == 0:
        raise ValueError(f"Invalid issue: {issue}")

    # Generate ticket ID
    import uuid
    from datetime import datetime

    ticket_id = f"TICKET-2026-{uuid.uuid4().hex[:3].upper()}"

    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "issue": issue,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    mock_tickets[ticket_id] = ticket

    logger.info(f"Tool result: created ticket {ticket_id}")

    return ticket