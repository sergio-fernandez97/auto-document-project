"""order_service.py – example undocumented script."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product_id: int
    quantity: int
    unit_price: float

    def subtotal(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    order_id: int
    customer_id: int
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    def total(self) -> float:
        return sum(item.subtotal() for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError("Cannot modify a non-pending order.")
        self.items.append(item)

    def cancel(self) -> bool:
        if self.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            return False
        self.status = OrderStatus.CANCELLED
        return True


def calculate_discount(order: Order, coupon_rate: float) -> float:
    if not 0.0 <= coupon_rate <= 1.0:
        raise ValueError("coupon_rate must be between 0 and 1.")
    return order.total() * coupon_rate


def apply_tax(amount: float, tax_rate: float) -> float:
    return amount * (1 + tax_rate)