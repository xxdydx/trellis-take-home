import asyncio
import random
from typing import Dict, Any
from sqlalchemy import select, update
from .database.connection import get_db_session
from .database.models import Order, Payment, Event


async def flaky_call() -> None:
    """Either raise an error or sleep long enough to trigger an activity timeout."""
    rand_num = random.random()
    if rand_num < 0.33:
        raise RuntimeError("Forced failure for testing")

    if rand_num < 0.67:
        await asyncio.sleep(
            300
        )  # Expect the activity layer to time out before this completes


async def order_received(
    order_id: str, items: list, address: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create a new order record in the database"""
    await flaky_call()

    async with get_db_session() as session:
        # Create new order
        new_order = Order(
            id=order_id, state="received", items_json=items, address_json=address
        )
        session.add(new_order)

        # Flush to ensure order is available for foreign key
        await session.flush()

        # Create event record
        event = Event(
            order_id=order_id,
            event_type="order_received",
            payload_json={"items": items, "address": address},
        )
        session.add(event)

        await session.commit()

        return {"order_id": order_id, "items": items, "state": "received"}


async def order_validated(order_id: str) -> bool:
    """Validate order and update status"""
    await flaky_call()

    async with get_db_session() as session:
        # Fetch order
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError(f"Order {order_id} not found")

        if not order.items_json:
            raise ValueError("No items to validate")

        # Update order state
        order.state = "validated"

        # Create event record
        event = Event(
            order_id=order_id,
            event_type="order_validated",
            payload_json={"previous_state": "received", "new_state": "validated"},
        )
        session.add(event)

        await session.commit()
        return True


async def payment_charged(order_id: str, payment_id: str) -> Dict[str, Any]:
    """Charge payment with idempotency logic"""
    await flaky_call()

    async with get_db_session() as session:
        # Check if payment already exists (idempotency)
        result = await session.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        existing_payment = result.scalar_one_or_none()

        if existing_payment:
            if existing_payment.status == "charged":
                print(
                    f"Payment {payment_id} already charged, returning existing result"
                )
                return {
                    "status": "charged",
                    "amount": float(existing_payment.amount),
                    "payment_id": payment_id,
                }
            else:
                print(
                    f"Payment {payment_id} exists but not charged, proceeding with charge"
                )

        # Fetch order to calculate amount
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError(f"Order {order_id} not found")

        # Calculate amount
        amount = sum(item.get("qty", 1) for item in order.items_json or [])

        # Create or update payment record
        if existing_payment:
            existing_payment.status = "charged"
            existing_payment.amount = amount
        else:
            payment = Payment(
                payment_id=payment_id,
                order_id=order_id,
                status="charged",
                amount=amount,
            )
            session.add(payment)

        # Update order state
        order.state = "paid"

        # Create event record
        event = Event(
            order_id=order_id,
            event_type="payment_charged",
            payload_json={
                "payment_id": payment_id,
                "amount": amount,
                "status": "charged",
            },
        )
        session.add(event)

        await session.commit()

        return {"status": "charged", "amount": amount, "payment_id": payment_id}


async def order_shipped(order_id: str) -> str:
    """Mark order as shipped"""
    await flaky_call()

    async with get_db_session() as session:
        # Update order state
        await session.execute(
            update(Order).where(Order.id == order_id).values(state="shipped")
        )

        # Create event record
        event = Event(
            order_id=order_id,
            event_type="order_shipped",
            payload_json={"previous_state": "paid", "new_state": "shipped"},
        )
        session.add(event)

        await session.commit()
        return "Shipped"


async def package_prepared(order_id: str) -> str:
    """Mark package as prepared"""
    await flaky_call()

    async with get_db_session() as session:
        # Create event record for package preparation
        event = Event(
            order_id=order_id,
            event_type="package_prepared",
            payload_json={"status": "ready"},
        )
        session.add(event)

        await session.commit()
        return "Package ready"


async def carrier_dispatched(order_id: str) -> str:
    """Mark carrier as dispatched"""
    await flaky_call()

    async with get_db_session() as session:
        # Create event record for carrier dispatch
        event = Event(
            order_id=order_id,
            event_type="carrier_dispatched",
            payload_json={"status": "dispatched"},
        )
        session.add(event)

        await session.commit()
        return "Dispatched"


async def update_address_activity(
    order_id: str, new_address: Dict[str, Any]
) -> Dict[str, Any]:
    """Update shipping address for an order"""
    async with get_db_session() as session:
        # Update order address
        await session.execute(
            update(Order).where(Order.id == order_id).values(address_json=new_address)
        )

        # Create event record
        event = Event(
            order_id=order_id,
            event_type="address_updated",
            payload_json={"new_address": new_address},
        )
        session.add(event)

        await session.commit()

        return {
            "order_id": order_id,
            "address_updated": True,
            "new_address": new_address,
        }
