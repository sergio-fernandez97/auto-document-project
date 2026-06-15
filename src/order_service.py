"""order_service.py – example undocumented script."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """Enumeration of the possible lifecycle states for a customer order.

        Attributes:
            PENDING: Order has been placed but not yet confirmed by the system.
            CONFIRMED: Order has been reviewed and accepted for fulfilment.
            SHIPPED: Order has been dispatched and is in transit to the customer.
            DELIVERED: Order has been successfully received by the customer.
            CANCELLED: Order was terminated before or during fulfilment.
    """
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    """Represents a single line item within a customer order.

        Attributes:
            product_id: Unique numeric identifier of the ordered product.
            quantity: Number of units requested for this line item.
            unit_price: Price of a single unit in the order's currency.

        def subtotal(self) -> float:
            """Calculate the total cost for this line item.

            Returns:
                The product of *quantity* and *unit_price*.
    """
    product_id: int
    quantity: int
    unit_price: float

    def subtotal(self) -> float:
        """Calculate the line-item subtotal for this order entry.

        Returns:
            The product of ``quantity`` and ``unit_price`` as a float.
        """
        return self.quantity * self.unit_price


@dataclass
class Order:
    """Represents a customer order containing one or more line items.

        Attributes:
            order_id: Unique numeric identifier assigned to this order.
            customer_id: Identifier of the customer who placed the order.
            items: List of :class:`OrderItem` instances belonging to this order.
            status: Current lifecycle status of the order (default: ``PENDING``).
            created_at: UTC timestamp of when the order was created.

        def total(self) -> float:
            """Calculate the total monetary value of the order.

            Returns:
                Sum of :pymeth:`OrderItem.subtotal` for every item in the order.
            """

        def add_item(self, item: OrderItem) -> None:
            """Append a line item to this order.

            Args:
                item: The :class:`OrderItem` instance to add.

            Raises:
                ValueError: If the order status is not ``PENDING``.
            """

        def cancel(self) -> bool:
            """Attempt to cancel the order.

            Orders that have already been shipped or delivered cannot be
            cancelled.

            Returns:
                True if the order was successfully cancelled, False if it is
                in a ``SHIPPED`` or ``DELIVERED`` state and cannot be cancelled.
    """
    order_id: int
    customer_id: int
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    def total(self) -> float:
        """Calculate the total cost of all items in the order.

        Returns:
            The sum of every line-item subtotal as a float.
        """
        return sum(item.subtotal() for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        """Add a line item to this order.

        Args:
            item: The :class:`OrderItem` instance to append to the order.

        Raises:
            ValueError: If the order status is not :attr:`OrderStatus.PENDING`.
        """
        if self.status != OrderStatus.PENDING:
            raise ValueError("Cannot modify a non-pending order.")
        self.items.append(item)

    def cancel(self) -> bool:
        """Cancel the order if it has not yet been shipped or delivered.

        Args:
            None

        Returns:
            True if the order was successfully cancelled, False if the order
            has already been shipped or delivered and cannot be cancelled.
        """
        if self.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            return False
        self.status = OrderStatus.CANCELLED
        return True


def calculate_discount(order: Order, coupon_rate: float) -> float:
    """Apply a coupon discount to an order and return the monetary savings.

    Args:
        order: The :class:`Order` instance whose total is used as the base amount.
        coupon_rate: Fractional discount to apply, expressed as a value between
            ``0.0`` (no discount) and ``1.0`` (100 % off).

    Returns:
        The discount amount as a float (i.e. the value to subtract from the
        order total).

    Raises:
        ValueError: If *coupon_rate* is outside the range ``[0.0, 1.0]``.
    """
    if not 0.0 <= coupon_rate <= 1.0:
        raise ValueError("coupon_rate must be between 0 and 1.")
    return order.total() * coupon_rate


def apply_tax(amount: float, tax_rate: float) -> float:
    """Apply a tax rate to a monetary amount and return the total.

    Args:
        amount: The pre-tax monetary value to which the rate is applied.
        tax_rate: The fractional tax rate (e.g. ``0.2`` for 20 %).

    Returns:
        The total amount inclusive of tax (``amount * (1 + tax_rate)``).
    """
    return amount * (1 + tax_rate)