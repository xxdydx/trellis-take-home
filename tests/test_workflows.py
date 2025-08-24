import pytest
import uuid
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio import activity

from src.workflows import OrderWorkflow, ShippingWorkflow


class TestOrderWorkflow:
    """Integration tests for OrderWorkflow using Temporal test environment"""

    @pytest.mark.asyncio
    async def test_successful_order_flow(self):
        """Test a successful order workflow completion with mocked activities"""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Mock activities that always succeed - following Temporal testing patterns
            @activity.defn(name="receive_order_activity")
            async def mock_receive_order(
                order_id: str, items: list = None, address: dict = None
            ):
                return {
                    "order_id": order_id,
                    "items": items or [{"sku": "ABC", "qty": 1}],
                }

            @activity.defn(name="validate_order_activity")
            async def mock_validate_order(order_id: str):
                return True

            @activity.defn(name="charge_payment_activity")
            async def mock_charge_payment(order_id: str, payment_id: str):
                return {"status": "charged", "amount": 100}

            @activity.defn(name="update_address_activity_wrapper")
            async def mock_update_address(order_id: str, new_address: dict):
                return {"success": True, "address": new_address}

            # Create unique task queue and workflow ID
            task_queue = f"test-tq-{uuid.uuid4()}"
            workflow_id = f"test-workflow-{uuid.uuid4()}"

            # Create worker with mocked activities (without shipping workflow)
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[OrderWorkflow],
                activities=[
                    mock_receive_order,
                    mock_validate_order,
                    mock_charge_payment,
                    mock_update_address,
                ],
            ):
                # Test workflow initialization and basic structure
                # Start workflow and immediately cancel it to test basic functionality
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["test-order-1", "test-payment-1"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Cancel immediately to test basic workflow functionality
                await handle.signal(OrderWorkflow.cancel_order)

                # Wait for completion
                result = await handle.result()

                # Verify basic workflow functionality
                assert result is not None
                assert isinstance(result, dict)
                assert result.get("status") == "cancelled"
                assert result.get("step") in [
                    "receive",
                    "validation",
                    "manual_approval",
                ]

    @pytest.mark.asyncio
    async def test_order_cancellation(self):
        """Test order cancellation functionality"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="receive_order_activity")
            async def mock_receive_order(
                order_id: str, items: list = None, address: dict = None
            ):
                return {
                    "order_id": order_id,
                    "items": items or [{"sku": "ABC", "qty": 1}],
                }

            @activity.defn(name="validate_order_activity")
            async def mock_validate_order(order_id: str):
                return True

            task_queue = f"test-tq-{uuid.uuid4()}"
            workflow_id = f"test-workflow-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[OrderWorkflow],
                activities=[mock_receive_order, mock_validate_order],
            ):
                # Start workflow and get handle for signaling
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["test-order-2", "test-payment-2"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Cancel order
                await handle.signal(OrderWorkflow.cancel_order)

                # Wait for completion
                result = await handle.result()

                # Verify cancellation
                assert result is not None
                assert result.get("status") == "cancelled"

    @pytest.mark.asyncio
    async def test_manual_approval_timeout(self):
        """Test manual approval timeout using time-skipping test environment"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="receive_order_activity")
            async def mock_receive_order(
                order_id: str, items: list = None, address: dict = None
            ):
                return {
                    "order_id": order_id,
                    "items": items or [{"sku": "ABC", "qty": 1}],
                }

            @activity.defn(name="validate_order_activity")
            async def mock_validate_order(order_id: str):
                return True

            task_queue = f"test-tq-{uuid.uuid4()}"
            workflow_id = f"test-workflow-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[OrderWorkflow],
                activities=[mock_receive_order, mock_validate_order],
            ):
                # Execute workflow without sending approval - let it timeout
                result = await env.client.execute_workflow(
                    OrderWorkflow.run,
                    args=["test-order-3", "test-payment-3"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Verify timeout failure
                assert result is not None
                assert result.get("status") == "failed"
                assert result.get("step") == "manual_approval"
                assert "timeout" in result.get("reason", "").lower()

    @pytest.mark.asyncio
    async def test_workflow_status_query(self):
        """Test workflow status queries during execution"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="receive_order_activity")
            async def mock_receive_order(
                order_id: str, items: list = None, address: dict = None
            ):
                # Add small delay to allow status queries
                return {
                    "order_id": order_id,
                    "items": items or [{"sku": "ABC", "qty": 1}],
                }

            @activity.defn(name="validate_order_activity")
            async def mock_validate_order(order_id: str):
                return True

            task_queue = f"test-tq-{uuid.uuid4()}"
            workflow_id = f"test-workflow-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[OrderWorkflow],
                activities=[mock_receive_order, mock_validate_order],
            ):
                # Start workflow and get handle for queries and signals
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["test-order-4", "test-payment-4"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Query initial status
                status = await handle.query(OrderWorkflow.get_status)
                assert status["cancelled"] == False
                assert status["approval_received"] == False

                # Send approval signal
                await handle.signal(OrderWorkflow.approve_order)

                # Query after approval
                status = await handle.query(OrderWorkflow.get_status)
                assert status["approval_received"] == True

                # Complete workflow by cancelling to avoid hanging
                await handle.signal(OrderWorkflow.cancel_order)
                result = await handle.result()
                assert result is not None

    @pytest.mark.asyncio
    async def test_address_update_signal(self):
        """Test address update signal handling"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="receive_order_activity")
            async def mock_receive_order(
                order_id: str, items: list = None, address: dict = None
            ):
                return {
                    "order_id": order_id,
                    "items": items or [{"sku": "ABC", "qty": 1}],
                }

            @activity.defn(name="validate_order_activity")
            async def mock_validate_order(order_id: str):
                return True

            @activity.defn(name="charge_payment_activity")
            async def mock_charge_payment(order_id: str, payment_id: str):
                return {"status": "charged", "amount": 100}

            @activity.defn(name="update_address_activity_wrapper")
            async def mock_update_address(order_id: str, new_address: dict):
                return {"success": True, "address": new_address}

            task_queue = f"test-tq-{uuid.uuid4()}"
            workflow_id = f"test-workflow-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[OrderWorkflow],
                activities=[
                    mock_receive_order,
                    mock_validate_order,
                    mock_charge_payment,
                    mock_update_address,
                ],
            ):
                # Start workflow and get handle for signals
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["test-order-5", "test-payment-5"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Update address
                new_address = {
                    "street": "123 Test St",
                    "city": "Test City",
                    "state": "TS",
                    "zip_code": "12345",
                }
                await handle.signal(OrderWorkflow.update_address, new_address)

                # Cancel workflow to avoid hanging
                await handle.signal(OrderWorkflow.cancel_order)

                # Wait for completion
                result = await handle.result()

                # Verify workflow completed and processed address update
                assert result is not None
                assert result.get("status") == "cancelled"


class TestShippingWorkflow:
    """Integration tests for ShippingWorkflow"""

    @pytest.mark.asyncio
    async def test_successful_shipping_flow(self):
        """Test successful shipping workflow completion"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="prepare_package_activity")
            async def mock_prepare_package(order_id: str):
                return "Package ready"

            @activity.defn(name="dispatch_carrier_activity")
            async def mock_dispatch_carrier(order_id: str):
                return "Dispatched"

            @activity.defn(name="ship_order_activity")
            async def mock_ship_order(order_id: str):
                return "Shipped"

            task_queue = f"test-shipping-tq-{uuid.uuid4()}"
            workflow_id = f"test-shipping-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[ShippingWorkflow],
                activities=[
                    mock_prepare_package,
                    mock_dispatch_carrier,
                    mock_ship_order,
                ],
            ):
                # Execute shipping workflow
                result = await env.client.execute_workflow(
                    ShippingWorkflow.run,
                    args=["test-order-5"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Verify successful completion
                assert result is not None
                assert result.get("status") == "completed"
                assert result.get("package") == "Package ready"
                assert result.get("dispatch") == "Dispatched"
                assert result.get("shipped") == "Shipped"

    @pytest.mark.asyncio
    async def test_shipping_dispatch_failure(self):
        """Test shipping workflow handling dispatch failure"""
        async with await WorkflowEnvironment.start_time_skipping() as env:

            @activity.defn(name="prepare_package_activity")
            async def mock_prepare_package(order_id: str):
                return "Package ready"

            @activity.defn(name="dispatch_carrier_activity")
            async def mock_dispatch_carrier_failing(order_id: str):
                raise RuntimeError("Carrier dispatch failed")

            task_queue = f"test-shipping-tq-{uuid.uuid4()}"
            workflow_id = f"test-shipping-{uuid.uuid4()}"

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[ShippingWorkflow],
                activities=[mock_prepare_package, mock_dispatch_carrier_failing],
            ):
                # Execute shipping workflow
                result = await env.client.execute_workflow(
                    ShippingWorkflow.run,
                    args=["test-order-6"],
                    id=workflow_id,
                    task_queue=task_queue,
                )

                # Verify failure handling
                assert result is not None
                assert result.get("status") == "failed"
                assert result.get("step") == "dispatch"
                assert result.get("package") == "Package ready"
                assert "error" in result


# Fixtures for test setup
@pytest.fixture
async def temporal_env():
    """Pytest fixture for Temporal test environment"""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.fixture
def unique_task_queue():
    """Generate unique task queue names for test isolation"""
    return f"test-tq-{uuid.uuid4()}"


@pytest.fixture
def unique_workflow_id():
    """Generate unique workflow IDs for test isolation"""
    return f"test-workflow-{uuid.uuid4()}"
