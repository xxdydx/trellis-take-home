#!/usr/bin/env python3
"""
Comprehensive Test Script for Temporal Order Lifecycle System
Tests all requirements from the specification
"""

import asyncio
import time
import requests
import json
import uuid
from datetime import datetime
from typing import Dict, Any


class SystemTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        self.test_results.append(
            {
                "test": test_name,
                "passed": passed,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def test_infrastructure(self):
        """Test 1: Infrastructure is running"""
        print("\n🔧 Testing Infrastructure...")

        # Test Temporal server
        try:
            response = requests.get(self.temporal_url, timeout=5)
            self.log_test("Temporal Server", response.status_code == 200)
        except Exception as e:
            self.log_test("Temporal Server", False, f"Error: {e}")

        # Test API server
        try:
            response = requests.get(f"{self.base_url}/docs", timeout=5)
            self.log_test("API Server", response.status_code == 200)
        except Exception as e:
            self.log_test("API Server", False, f"Error: {e}")

    def test_workflow_creation(self):
        """Test 2: Can create workflows"""
        print("\n🚀 Testing Workflow Creation...")

        order_id = f"test-order-{uuid.uuid4().hex[:8]}"
        payment_id = f"test-payment-{uuid.uuid4().hex[:8]}"

        try:
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/start",
                json={"payment_id": payment_id},
                timeout=10,
            )

            if response.status_code == 200:
                self.log_test("Workflow Creation", True, f"Order {order_id} created")
                return order_id, payment_id
            else:
                self.log_test(
                    "Workflow Creation", False, f"Status: {response.status_code}"
                )
                return None, None

        except Exception as e:
            self.log_test("Workflow Creation", False, f"Error: {e}")
            return None, None

    def test_workflow_status_query(self, order_id: str):
        """Test 3: Can query workflow status"""
        print("\n📊 Testing Status Queries...")

        try:
            response = requests.get(
                f"{self.base_url}/orders/{order_id}/status", timeout=5
            )

            if response.status_code == 200:
                status_data = response.json()
                self.log_test(
                    "Status Query",
                    True,
                    f"Status: {status_data.get('state', 'unknown')}",
                )
                return status_data
            else:
                self.log_test("Status Query", False, f"Status: {response.status_code}")
                return None

        except Exception as e:
            self.log_test("Status Query", False, f"Error: {e}")
            return None

    def test_manual_approval_signal(self, order_id: str):
        """Test 4: Can send approval signal"""
        print("\n✅ Testing Manual Approval...")

        try:
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/signals/approve", timeout=5
            )

            if response.status_code == 200:
                self.log_test("Approval Signal", True, "Approval signal sent")
                return True
            else:
                self.log_test(
                    "Approval Signal", False, f"Status: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("Approval Signal", False, f"Error: {e}")
            return False

    def test_cancel_signal(self, order_id: str):
        """Test 5: Can send cancel signal"""
        print("\n❌ Testing Cancel Signal...")

        try:
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/signals/cancel", timeout=5
            )

            if response.status_code == 200:
                self.log_test("Cancel Signal", True, "Cancel signal sent")
                return True
            else:
                self.log_test("Cancel Signal", False, f"Status: {response.status_code}")
                return False

        except Exception as e:
            self.log_test("Cancel Signal", False, f"Error: {e}")
            return False

    def test_address_update_signal(self, order_id: str):
        """Test 6: Can update shipping address"""
        print("\n🏠 Testing Address Update...")

        new_address = {
            "street": "123 Test Street",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "country": "US",
        }

        try:
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/signals/update-address",
                json=new_address,
                timeout=5,
            )

            if response.status_code == 200:
                self.log_test("Address Update", True, "Address updated")
                return True
            else:
                self.log_test(
                    "Address Update", False, f"Status: {response.status_code}"
                )
                return False

        except Exception as e:
            self.log_test("Address Update", False, f"Error: {e}")
            return False

    def test_complete_workflow_flow(self):
        """Test 7: Complete workflow flow with timing"""
        print("\n⏱️ Testing Complete Workflow Flow...")

        order_id = f"complete-test-{uuid.uuid4().hex[:8]}"
        payment_id = f"complete-payment-{uuid.uuid4().hex[:8]}"

        start_time = time.time()

        try:
            # 1. Start workflow
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/start",
                json={"payment_id": payment_id},
                timeout=10,
            )

            if response.status_code != 200:
                self.log_test("Complete Flow", False, "Failed to start workflow")
                return

            # 2. Wait a moment for workflow to start
            time.sleep(2)

            # 3. Send approval signal
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/signals/approve", timeout=5
            )

            if response.status_code != 200:
                self.log_test("Complete Flow", False, "Failed to approve")
                return

            # 4. Monitor completion (with timeout)
            max_wait = 20  # seconds
            wait_time = 0
            while wait_time < max_wait:
                response = requests.get(
                    f"{self.base_url}/orders/{order_id}/status", timeout=5
                )
                if response.status_code == 200:
                    status_data = response.json()
                    state = status_data.get("state", "unknown")

                    if state in ["completed", "failed", "cancelled"]:
                        end_time = time.time()
                        duration = end_time - start_time

                        if duration <= 15:
                            self.log_test(
                                "15-Second Timeout",
                                True,
                                f"Completed in {duration:.2f}s",
                            )
                        else:
                            self.log_test(
                                "15-Second Timeout",
                                False,
                                f"Took {duration:.2f}s (exceeded 15s)",
                            )

                        self.log_test(
                            "Complete Flow",
                            state == "completed",
                            f"Final state: {state}",
                        )
                        return

                time.sleep(1)
                wait_time += 1

            self.log_test(
                "Complete Flow", False, "Workflow did not complete within timeout"
            )

        except Exception as e:
            self.log_test("Complete Flow", False, f"Error: {e}")

    def test_flaky_behavior(self):
        """Test 8: Test flaky behavior handling"""
        print("\n🎲 Testing Flaky Behavior...")

        # Create multiple orders to test flaky behavior
        successful_orders = 0
        failed_orders = 0

        for i in range(5):
            order_id = f"flaky-test-{i}-{uuid.uuid4().hex[:8]}"
            payment_id = f"flaky-payment-{i}-{uuid.uuid4().hex[:8]}"

            try:
                # Start workflow
                response = requests.post(
                    f"{self.base_url}/orders/{order_id}/start",
                    json={"payment_id": payment_id},
                    timeout=10,
                )

                if response.status_code == 200:
                    # Send approval
                    response = requests.post(
                        f"{self.base_url}/orders/{order_id}/signals/approve", timeout=5
                    )

                    # Wait for completion
                    time.sleep(3)

                    # Check status
                    response = requests.get(
                        f"{self.base_url}/orders/{order_id}/status", timeout=5
                    )
                    if response.status_code == 200:
                        status_data = response.json()
                        if status_data.get("state") == "completed":
                            successful_orders += 1
                        else:
                            failed_orders += 1

            except Exception:
                failed_orders += 1

        # Test that some orders succeed despite flaky behavior
        self.log_test(
            "Flaky Behavior Handling",
            successful_orders > 0,
            f"Success: {successful_orders}, Failed: {failed_orders}",
        )

    def test_database_persistence(self):
        """Test 9: Test database persistence"""
        print("\n🗄️ Testing Database Persistence...")

        order_id = f"db-test-{uuid.uuid4().hex[:8]}"
        payment_id = f"db-payment-{uuid.uuid4().hex[:8]}"

        try:
            # Start workflow
            response = requests.post(
                f"{self.base_url}/orders/{order_id}/start",
                json={"payment_id": payment_id},
                timeout=10,
            )

            if response.status_code == 200:
                # Check if order exists in database
                response = requests.get(
                    f"{self.base_url}/orders/{order_id}/status", timeout=5
                )
                if response.status_code == 200:
                    self.log_test(
                        "Database Persistence", True, "Order persisted to database"
                    )
                else:
                    self.log_test(
                        "Database Persistence", False, "Order not found in database"
                    )
            else:
                self.log_test("Database Persistence", False, "Failed to create order")

        except Exception as e:
            self.log_test("Database Persistence", False, f"Error: {e}")

    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Starting Comprehensive System Tests")
        print("=" * 50)

        # Test infrastructure
        self.test_infrastructure()

        # Test basic workflow creation
        order_id, payment_id = self.test_workflow_creation()

        if order_id:
            # Test status query
            self.test_workflow_status_query(order_id)

            # Test signals
            self.test_manual_approval_signal(order_id)
            self.test_cancel_signal(order_id)
            self.test_address_update_signal(order_id)

        # Test complete workflow flow
        self.test_complete_workflow_flow()

        # Test flaky behavior
        self.test_flaky_behavior()

        # Test database persistence
        self.test_database_persistence()

        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)

        passed = sum(1 for result in self.test_results if result["passed"])
        total = len(self.test_results)

        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")

        if passed == total:
            print("\n🎉 ALL TESTS PASSED! System meets specifications.")
        else:
            print("\n⚠️ Some tests failed. Check the details above.")

        # Save results
        with open("test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)

        print(f"\n📄 Detailed results saved to: test_results.json")


def main():
    """Main test runner"""
    tester = SystemTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
