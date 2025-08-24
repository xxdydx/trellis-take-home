import asyncio
from datetime import timedelta
from typing import Dict, Any
from temporalio import activity

from .functions import (
    order_received,
    order_validated,
    payment_charged,
    order_shipped,
    package_prepared,
    carrier_dispatched,
    update_address_activity,
)


@activity.defn
async def receive_order_activity(
    order_id: str, items: list, address: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Receive and process a new order"""
    print(f"Receiving order: {order_id}")

    try:
        # Call the function with database operations
        order_data = await order_received(order_id, items, address)

        print(f"Order received successfully: {order_id}")
        return order_data

    except Exception as e:
        print(f"Failed to receive order: {order_id}, error: {str(e)}")
        raise


@activity.defn
async def validate_order_activity(order_id: str) -> bool:
    """Validate an order"""
    print(f"Validating order: {order_id}")

    try:
        # Call the function with database operations
        is_valid = await order_validated(order_id)

        print(f"Order validation completed: {order_id}, valid: {is_valid}")
        return is_valid

    except Exception as e:
        print(f"Failed to validate order: {order_id}, error: {str(e)}")
        raise


@activity.defn
async def charge_payment_activity(order_id: str, payment_id: str) -> Dict[str, Any]:
    """Charge payment for an order with idempotency"""
    print(f"Charging payment: {order_id}, {payment_id}")

    try:
        # Call the function with database operations
        payment_result = await payment_charged(order_id, payment_id)

        print(f"Payment charged successfully: {order_id}, {payment_id}")
        return payment_result

    except Exception as e:
        print(f"Failed to charge payment: {order_id}, {payment_id}, error: {str(e)}")
        raise


@activity.defn
async def prepare_package_activity(order_id: str) -> str:
    """Prepare package for shipping"""
    print(f"Preparing package: {order_id}")

    try:
        # Call the function with database operations
        package_result = await package_prepared(order_id)

        print(f"Package prepared successfully: {order_id}")
        return package_result

    except Exception as e:
        print(f"Failed to prepare package: {order_id}, error: {str(e)}")
        raise


@activity.defn
async def dispatch_carrier_activity(order_id: str) -> str:
    """Dispatch carrier for shipping"""
    print(f"Dispatching carrier: {order_id}")

    try:
        # Call the function with database operations
        dispatch_result = await carrier_dispatched(order_id)

        print(f"Carrier dispatched successfully: {order_id}")
        return dispatch_result

    except Exception as e:
        print(f"Failed to dispatch carrier: {order_id}, error: {str(e)}")
        raise


@activity.defn
async def ship_order_activity(order_id: str) -> str:
    """Ship the order"""
    print(f"Shipping order: {order_id}")

    try:
        # Call the function with database operations
        ship_result = await order_shipped(order_id)

        print(f"Order shipped successfully: {order_id}")
        return ship_result

    except Exception as e:
        print(f"Failed to ship order: {order_id}, error: {str(e)}")
        raise


@activity.defn
async def update_address_activity_wrapper(
    order_id: str, new_address: Dict[str, Any]
) -> Dict[str, Any]:
    """Update shipping address"""
    print(f"Updating address: {order_id}, {new_address}")

    try:
        # Call the function with database operations
        result = await update_address_activity(order_id, new_address)

        print(f"Address updated successfully: {order_id}")
        return result

    except Exception as e:
        print(f"Failed to update address: {order_id}, error: {str(e)}")
        raise
