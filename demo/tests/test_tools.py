"""Test mock tools functionality."""

import pytest

from demo.agent.tools import (
    check_payment,
    create_support_ticket,
    get_customer,
    get_order,
    mock_customers,
    mock_orders,
)


class TestGetCustomer:
    """Tests for get_customer tool."""

    def test_get_existing_customer(self):
        """Get existing customer by ID."""
        result = get_customer("CUST-001")

        assert result is not None
        assert result["customer_id"] == "CUST-001"
        assert result["name"] == "John Doe"
        assert "email" in result

    def test_get_customer_invalid_id(self):
        """Try to get non-existent customer."""
        result = get_customer("CUST-999")

        assert result is None

    def test_get_customer_invalid_format(self):
        """Try to get customer with invalid ID."""
        with pytest.raises(ValueError, match="Invalid customer_id"):
            get_customer("")

        with pytest.raises(ValueError, match="Invalid customer_id"):
            get_customer(None)


class TestGetOrder:
    """Tests for get_order tool."""

    def test_get_existing_order(self):
        """Get existing order by ID."""
        result = get_order("ORD-1001")

        assert result is not None
        assert result["order_id"] == "ORD-1001"
        assert result["status"] == "shipped"
        assert len(result["items"]) > 0

    def test_get_order_invalid_id(self):
        """Try to get non-existent order."""
        result = get_order("ORD-999")

        assert result is None

    def test_get_order_invalid_format(self):
        """Try to get order with invalid ID."""
        with pytest.raises(ValueError, match="Invalid order_id"):
            get_order("")

        with pytest.raises(ValueError, match="Invalid order_id"):
            get_order(None)


class TestCheckPayment:
    """Tests for check_payment tool."""

    def test_get_existing_payment(self):
        """Get payment status for existing order."""
        result = check_payment("ORD-1001")

        assert result is not None
        assert result["payment_status"] == "paid"
        assert result["method"] == "Credit Card"

    def test_get_payment_invalid_order(self):
        """Try to get payment for non-existent order."""
        result = check_payment("ORD-999")

        assert result is None

    def test_get_payment_pending(self):
        """Get pending payment status."""
        result = check_payment("ORD-1002")

        assert result is not None
        assert result["payment_status"] == "pending"
        assert result["paid_at"] is None


class TestCreateSupportTicket:
    """Tests for create_support_ticket tool."""

    def test_create_ticket(self):
        """Create a support ticket."""
        result = create_support_ticket("CUST-001", "Missing order")

        assert result is not None
        assert "ticket_id" in result
        assert "customer_id" in result
        assert result["customer_id"] == "CUST-001"
        assert result["status"] == "pending"

    def test_create_ticket_valid_issue(self):
        """Create ticket with valid issue description."""
        result = create_support_ticket("CUST-002", "Wrong item received")

        assert result is not None
        assert result["issue"] == "Wrong item received"

    def test_create_ticket_invalid_customer(self):
        """Try to create ticket with invalid customer."""
        with pytest.raises(ValueError, match="Invalid customer_id"):
            create_support_ticket("", "Some issue")

    def test_create_ticket_invalid_issue(self):
        """Try to create ticket with invalid issue."""
        with pytest.raises(ValueError, match="Invalid issue"):
            create_support_ticket("CUST-001", "")

        with pytest.raises(ValueError, match="Invalid issue"):
            create_support_ticket("CUST-001", None)

    def test_multiple_tickets_unique_ids(self):
        """Ensure each new ticket gets unique ID."""
        ticket1 = create_support_ticket("CUST-001", "Issue 1")
        ticket2 = create_support_ticket("CUST-001", "Issue 2")

        assert ticket1["ticket_id"] != ticket2["ticket_id"]


class TestMockDataConsistency:
    """Tests for mock data integrity."""

    def test_orders_have_customer_ids(self):
        """All mock orders should have valid customer IDs."""
        for order_id, order in mock_orders.items():
            assert order["customer_id"] in mock_customers

    def test_mock_data_are_complete(self):
        """Mock data should have all expected fields."""
        customer = mock_customers["CUST-001"]
        assert "customer_id" in customer
        assert "name" in customer
        assert "email" in customer

        order = mock_orders["ORD-1001"]
        assert "order_id" in order
        assert "customer_id" in order
        assert "status" in order
        assert "items" in order