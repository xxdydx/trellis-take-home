import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

from .activities import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
    prepare_package_activity,
    dispatch_carrier_activity,
    ship_order_activity,
    update_address_activity_wrapper,
)

# Retry policy for activities with flaky_call()
FLAKY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=5,
    backoff_coefficient=2.0,
)


@workflow.defn
class OrderWorkflow:
    """Main order processing workflow"""

    def __init__(self) -> None:
        self._cancelled = False
        self._manual_approval_received = False
        self._address_updates: list = []
        self._current_state = "initialized"

    @workflow.run
    async def run(
        self,
        order_id: str,
        payment_id: str,
        items: list = None,
        address: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute the order workflow"""
        print(f"Starting order workflow: {order_id}")

        try:
            self._current_state = "receiving"

            # Step 1: Receive Order
            order_data = await workflow.execute_activity(
                receive_order_activity,
                args=[order_id, items or [{"sku": "DEFAULT", "qty": 1}], address],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=FLAKY_RETRY_POLICY,
            )

            if self._cancelled:
                print(f"Order cancelled during receive: {order_id}")
                return {"status": "cancelled", "step": "receive"}

            self._current_state = "validating"

            # Step 2: Validate Order
            is_valid = await workflow.execute_activity(
                validate_order_activity,
                args=[order_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=FLAKY_RETRY_POLICY,
            )

            if not is_valid:
                print(f"Order validation failed: {order_id}")
                return {
                    "status": "failed",
                    "step": "validation",
                    "reason": "Invalid order",
                }

            if self._cancelled:
                print(f"Order cancelled during validation: {order_id}")
                return {"status": "cancelled", "step": "validation"}

            self._current_state = "awaiting_approval"

            # Step 3: Manual Review Timer (wait for approval signal)
            print(f"Waiting for manual approval: {order_id}")

            try:
                await workflow.wait_condition(
                    lambda: self._manual_approval_received or self._cancelled,
                    timeout=timedelta(
                        seconds=10
                    ),  # 10 second timeout for manual approval
                )
            except asyncio.TimeoutError:
                print(f"Manual approval timeout: {order_id}")
                return {
                    "status": "failed",
                    "step": "manual_approval",
                    "reason": "Approval timeout",
                }

            if self._cancelled:
                print(f"Order cancelled during manual approval: {order_id}")
                return {"status": "cancelled", "step": "manual_approval"}

            self._current_state = "charging_payment"

            # Step 4: Charge Payment
            payment_result = await workflow.execute_activity(
                charge_payment_activity,
                args=[order_id, payment_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=FLAKY_RETRY_POLICY,
            )

            if self._cancelled:
                print(f"Order cancelled after payment, need to refund: {order_id}")
                # In a real system, we'd trigger a compensation workflow here
                return {
                    "status": "cancelled",
                    "step": "post_payment",
                    "needs_refund": True,
                }

            self._current_state = "shipping"

            # Step 5: Start Shipping Workflow (Child Workflow)
            shipping_result = await workflow.execute_child_workflow(
                ShippingWorkflow.run,
                args=[order_id],
                id=f"shipping-{order_id}",
                task_queue="shipping-tq",  # Separate task queue for shipping
            )

            self._current_state = "completed"

            print(f"Order workflow completed successfully: {order_id}")
            return {
                "status": "completed",
                "order_data": order_data,
                "payment": payment_result,
                "shipping": shipping_result,
            }

        except Exception as e:
            print(f"Order workflow failed: {order_id}, error: {str(e)}")
            return {"status": "failed", "error": str(e), "step": self._current_state}

    @workflow.signal
    async def cancel_order(self) -> None:
        """Cancel the order"""
        print("Received cancel order signal")
        self._cancelled = True

    @workflow.signal
    async def approve_order(self) -> None:
        """Approve the order for payment processing"""
        print("Received order approval signal")
        self._manual_approval_received = True

    @workflow.signal(unfinished_policy=workflow.HandlerUnfinishedPolicy.ABANDON)
    async def update_address(self, new_address: Dict[str, Any]) -> None:
        """Update shipping address"""
        print(f"Received address update signal: {new_address}")
        self._address_updates.append(new_address)

        # Execute address update activity
        await workflow.execute_activity(
            update_address_activity_wrapper,
            args=[
                workflow.info().workflow_id.split("-")[
                    -1
                ],  # Extract order_id from workflow_id
                new_address,
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

    @workflow.signal
    async def dispatch_failed(self, failure_info: Dict[str, Any]) -> None:
        """Handle dispatch failure from shipping child workflow"""
        print(f"Received dispatch failed signal from shipping: {failure_info}")
        # In a real system, could trigger compensation or retry logic

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status"""
        return {
            "state": self._current_state,
            "cancelled": self._cancelled,
            "approval_received": self._manual_approval_received,
            "address_updates": len(self._address_updates),
        }


@workflow.defn
class ShippingWorkflow:
    """Child workflow for shipping operations"""

    def __init__(self) -> None:
        self._current_state = "initialized"
        self._dispatch_failed = False

    @workflow.run
    async def run(self, order_id: str) -> Dict[str, Any]:
        """Execute the shipping workflow"""
        print(f"Starting shipping workflow: {order_id}")

        try:
            self._current_state = "preparing_package"

            # Step 1: Prepare Package
            package_result = await workflow.execute_activity(
                prepare_package_activity,
                args=[order_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=FLAKY_RETRY_POLICY,
            )

            self._current_state = "dispatching_carrier"

            # Step 2: Dispatch Carrier
            try:
                dispatch_result = await workflow.execute_activity(
                    dispatch_carrier_activity,
                    args=[order_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=FLAKY_RETRY_POLICY,
                )
            except Exception as e:
                print(f"Carrier dispatch failed: {order_id}, error: {str(e)}")
                self._dispatch_failed = True

                # Signal parent workflow about dispatch failure
                parent_workflow_id = f"order-{order_id}"
                try:
                    parent_handle = workflow.get_external_workflow_handle(
                        parent_workflow_id
                    )
                    await parent_handle.signal("dispatch_failed", {"reason": str(e)})
                except Exception as signal_error:
                    print(f"Failed to signal parent workflow: {str(signal_error)}")

                # Return failure result
                return {
                    "status": "failed",
                    "step": "dispatch",
                    "package": package_result,
                    "error": str(e),
                }

            self._current_state = "shipped"

            # Step 3: Mark as shipped
            ship_result = await workflow.execute_activity(
                ship_order_activity,
                args=[order_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=FLAKY_RETRY_POLICY,
            )

            self._current_state = "completed"

            print(f"Shipping workflow completed successfully: {order_id}")
            return {
                "status": "completed",
                "package": package_result,
                "dispatch": dispatch_result,
                "shipped": ship_result,
            }

        except Exception as e:
            print(f"Shipping workflow failed: {order_id}, error: {str(e)}")
            return {"status": "failed", "error": str(e), "step": self._current_state}

    @workflow.signal
    async def dispatch_failed(self, failure_info: Dict[str, Any]) -> None:
        """Handle dispatch failure signal from parent"""
        print(f"Received dispatch failed signal: {failure_info}")
        self._dispatch_failed = True

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current shipping workflow status"""
        return {
            "state": self._current_state,
            "dispatch_failed": self._dispatch_failed,
        }
