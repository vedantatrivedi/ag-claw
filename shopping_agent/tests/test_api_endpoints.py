"""
Test suite for SerpAPI endpoints.

Run with: pytest shopping_agent/tests/test_api_endpoints.py -v
"""

import pytest
from unittest import mock
from fastapi.testclient import TestClient
from shopping_agent.server import app


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_ok(self):
        """Test that health endpoint returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPlanEndpoint:
    """Tests for /plan endpoint."""

    def test_plan_with_valid_request(self):
        """Test plan generation with valid request."""
        response = client.post(
            "/plan",
            json={"request": "wireless headphones under 5000"}
        )
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "items" in data
        assert "assumptions" in data
        assert "clarifications_needed" in data
        assert "metadata" in data

        # Check items have required fields
        assert len(data["items"]) > 0
        first_item = data["items"][0]
        assert "description" in first_item
        assert "quantity" in first_item
        assert "intent" in first_item
        assert "required" in first_item
        assert "search_hints" in first_item
        assert "constraints" in first_item

    def test_plan_with_postprocessing_disabled(self):
        """Test plan generation with postprocessing disabled."""
        response = client.post(
            "/plan",
            json={
                "request": "laptop for programming",
                "postprocess": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_plan_with_empty_request(self):
        """Test plan endpoint with empty request."""
        response = client.post(
            "/plan",
            json={"request": ""}
        )
        # Should fail validation
        assert response.status_code == 422

    def test_plan_with_missing_request(self):
        """Test plan endpoint with missing request field."""
        response = client.post("/plan", json={})
        # Should fail validation
        assert response.status_code == 422


class TestSerpSearchEndpoint:
    """Tests for /serp/search endpoint."""

    @pytest.fixture
    def sample_plan_items(self):
        """Fixture providing sample plan items for testing."""
        return [
            {
                "description": "Wireless earbuds with mic",
                "quantity": 1,
                "intent": "Listening to music",
                "required": True,
                "search_hints": ["wireless", "bluetooth"],
                "constraints": ["under 5000"],
                "search_query": "wireless earbuds with mic",
                "preferred_sites": ["amazon", "flipkart"]
            }
        ]

    def test_search_with_valid_items(self, sample_plan_items):
        """Test search with valid plan items."""
        response = client.post(
            "/serp/search",
            json={"items": sample_plan_items}
        )
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "count" in data
        assert "results" in data
        assert data["count"] == len(sample_plan_items)

        # Check first result
        first_result = data["results"][0]
        assert "item_description" in first_result
        assert "total_found" in first_result
        assert "results" in first_result

        # Check products
        if first_result["results"]:
            product = first_result["results"][0]
            assert "title" in product
            assert "url" in product
            assert "source" in product
            # Optional fields
            assert "price" in product
            assert "rating" in product
            assert "image_url" in product
            assert "final_score" in product

    def test_search_with_multiple_items(self):
        """Test search with multiple plan items."""
        items = [
            {
                "description": "Cricket bat",
                "quantity": 1,
                "intent": "Playing cricket",
                "required": True,
                "search_hints": ["cricket", "sports"],
                "constraints": [],
                "search_query": "cricket bat",
                "preferred_sites": ["amazon"]
            },
            {
                "description": "Cricket helmet",
                "quantity": 1,
                "intent": "Safety gear",
                "required": True,
                "search_hints": ["cricket", "helmet"],
                "constraints": [],
                "search_query": "cricket helmet",
                "preferred_sites": ["flipkart"]
            }
        ]

        response = client.post("/serp/search", json={"items": items})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_with_empty_items(self):
        """Test search with empty items list."""
        response = client.post("/serp/search", json={"items": []})
        # Should fail validation (min_length=1)
        assert response.status_code == 422

    def test_search_with_invalid_item_structure(self):
        """Test search with invalid item structure."""
        response = client.post(
            "/serp/search",
            json={"items": [{"invalid": "structure"}]}
        )
        # Should fail due to missing required fields
        assert response.status_code == 400
        assert "Invalid plan item" in response.json()["detail"]

    def test_search_with_missing_items_field(self):
        """Test search with missing items field."""
        response = client.post("/serp/search", json={})
        # Should fail validation
        assert response.status_code == 422


class TestEndToEndFlow:
    """Integration tests for complete plan -> search flow."""

    def test_complete_flow(self):
        """Test complete flow: plan generation -> product search."""
        # Step 1: Generate plan
        plan_response = client.post(
            "/plan",
            json={"request": "cricket helmet youth"}
        )
        assert plan_response.status_code == 200
        plan_data = plan_response.json()

        # Step 2: Search for products using the plan
        search_response = client.post(
            "/serp/search",
            json={"items": plan_data["items"]}
        )
        assert search_response.status_code == 200
        search_data = search_response.json()

        # Verify we got results for all items
        assert search_data["count"] == len(plan_data["items"])

        # Verify each result has products
        for result in search_data["results"]:
            assert result["total_found"] > 0
            assert len(result["results"]) > 0  # At least some products

    def test_flow_with_electronics(self):
        """Test flow with electronics category."""
        plan_response = client.post(
            "/plan",
            json={"request": "laptop under 50000"}
        )
        assert plan_response.status_code == 200
        plan_data = plan_response.json()

        # Check that electronics sites are suggested
        items = plan_data["items"]
        assert len(items) > 0
        # At least one item should suggest croma/flipkart/amazon
        has_electronics_sites = any(
            any(site in item.get("preferred_sites", [])
                for site in ["croma", "flipkart", "amazon"])
            for item in items
        )
        assert has_electronics_sites

    def test_flow_with_fashion(self):
        """Test flow with fashion category."""
        plan_response = client.post(
            "/plan",
            json={"request": "formal shirts for office"}
        )
        assert plan_response.status_code == 200
        plan_data = plan_response.json()

        # Check that fashion sites are suggested
        items = plan_data["items"]
        assert len(items) > 0
        # Should suggest myntra/ajio for fashion
        has_fashion_sites = any(
            any(site in item.get("preferred_sites", [])
                for site in ["myntra", "ajio", "flipkart"])
            for item in items
        )
        assert has_fashion_sites


class TestErrorHandling:
    """Tests for error handling in endpoints."""

    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        response = client.post(
            "/plan",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_content_type(self):
        """Test request without Content-Type header."""
        response = client.post(
            "/plan",
            data='{"request": "test"}'
        )
        # FastAPI may return 422 (validation) or 500 (parsing error)
        assert response.status_code in [200, 422, 500]


class TestGuidedPartyEndpoints:
    """Tests for the guided-party API flow."""

    def test_guided_party_questions_endpoint(self):
        with mock.patch(
            "shopping_agent.server.ShoppingOrchestrator.generate_guided_party_questions",
            return_value=[
                "What theme or characters does he like?",
                "Anything he dislikes or should we avoid?",
                "What is his favorite color?",
                "How many guests are expected?",
            ],
        ) as questions_mock:
            response = client.post(
                "/guided-party/questions",
                json={"request": "It's my son's birthday tomorrow, I want to plan a themed party"},
            )

        assert response.status_code == 200
        assert response.json()["questions"][0] == "What theme or characters does he like?"
        questions_mock.assert_called_once()

    def test_guided_party_preauth_endpoint(self):
        with mock.patch(
            "shopping_agent.server.ShoppingOrchestrator.create_guided_party_preauth",
            return_value={
                "success": True,
                "preauth": {
                    "order_id": "ord_123",
                    "status": "CREATED",
                    "redirect_url": "https://checkout.example.com/ord_123",
                    "budget_paisa": 1500000,
                },
            },
        ) as preauth_mock:
            response = client.post(
                "/guided-party/preauth",
                json={
                    "request": "It's my son's birthday tomorrow, I want to plan a themed party",
                    "preferences_answers": {
                        "What theme or characters does he like?": "Spider-Man",
                        "Anything he dislikes or should we avoid?": "No scary themes",
                    },
                    "budget_inr": 15000,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["preauth"]["order_id"] == "ord_123"
        assert data["preauth"]["redirect_url"] == "https://checkout.example.com/ord_123"
        preauth_mock.assert_called_once_with(
            preferences_answers={
                "What theme or characters does he like?": "Spider-Man",
                "Anything he dislikes or should we avoid?": "No scary themes",
            },
            budget_inr=15000,
        )

    def test_guided_party_complete_endpoint(self):
        with mock.patch(
            "shopping_agent.server.ShoppingOrchestrator.complete_guided_party_after_authorization",
            return_value={
                "success": True,
                "preferences_asked": [
                    "What theme or characters does he like?",
                    "What is his favorite color?",
                ],
                "preferences_answers": {
                    "What theme or characters does he like?": "Spider-Man",
                    "What is his favorite color?": "Blue",
                },
                "budget_inr": 15000.0,
                "preauth": {
                    "order_id": "ord_123",
                    "status": "CREATED",
                    "authorized_status": "AUTHORIZED",
                    "redirect_url": "https://checkout.example.com/ord_123",
                },
                "plan": {
                    "items": [
                        {
                            "description": "Spider-Man themed birthday banner",
                            "quantity": 1,
                            "intent": "Main party decoration",
                            "required": True,
                            "search_hints": ["Spider-Man", "banner"],
                            "constraints": [],
                            "search_query": "spider man birthday banner",
                            "preferred_sites": ["amazon", "flipkart"],
                        }
                    ],
                    "assumptions": ["Indoor party"],
                    "clarifications_needed": [],
                },
                "planner_metadata": {
                    "model": "test-model",
                    "tokens_used": 42,
                },
                "curation_mode": "serpapi",
                "listing_results": [
                    {
                        "task": {
                            "plan_item": {
                                "description": "Spider-Man themed birthday banner",
                                "quantity": 1,
                                "intent": "Main party decoration",
                                "required": True,
                                "search_hints": ["Spider-Man", "banner"],
                                "constraints": [],
                                "search_query": "spider man birthday banner",
                                "preferred_sites": ["amazon", "flipkart"],
                            },
                            "search_query": "spider man birthday banner",
                            "filters": {"placeholder": True},
                        },
                        "results": [
                            {
                                "title": "Placeholder match for Spider-Man themed birthday banner",
                                "url": "https://placeholder.local/products/spider-man-themed-birthday-banner",
                                "price": None,
                                "source": "placeholder",
                                "relevance_score": 0.5,
                                "rating": None,
                                "review_count": None,
                                "in_stock": True,
                            }
                        ],
                        "total_found": 1,
                    }
                ],
                "selected_product_urls": [
                    "https://placeholder.local/products/spider-man-themed-birthday-banner"
                ],
            },
        ) as complete_mock:
            response = client.post(
                "/guided-party/complete",
                json={
                    "request": "It's my son's birthday tomorrow, I want to plan a themed party",
                    "preferences_answers": {
                        "What theme or characters does he like?": "Spider-Man",
                        "What is his favorite color?": "Blue",
                    },
                    "budget_inr": 15000,
                    "preauth": {
                        "order_id": "ord_123",
                        "status": "CREATED",
                        "redirect_url": "https://checkout.example.com/ord_123",
                    },
                    "postprocess": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["preauth"]["authorized_status"] == "AUTHORIZED"
        assert data["curation_mode"] == "serpapi"
        assert data["plan"]["items"][0]["description"] == "Spider-Man themed birthday banner"
        assert data["listing_results"][0]["results"][0]["source"] == "placeholder"
        assert data["selected_product_urls"] == [
            "https://placeholder.local/products/spider-man-themed-birthday-banner"
        ]
        complete_mock.assert_called_once_with(
            user_request="It's my son's birthday tomorrow, I want to plan a themed party",
            preferences_answers={
                "What theme or characters does he like?": "Spider-Man",
                "What is his favorite color?": "Blue",
            },
            budget_inr=15000,
            preauth={
                "order_id": "ord_123",
                "status": "CREATED",
                "redirect_url": "https://checkout.example.com/ord_123",
            },
            apply_postprocessing=True,
        )

    def test_guided_party_cart_endpoint(self):
        listing_results = [
            {
                "task": {
                    "plan_item": {
                        "description": "Spider-Man themed birthday banner",
                        "quantity": 1,
                        "intent": "Main party decoration",
                        "required": True,
                        "search_hints": ["Spider-Man", "banner"],
                        "constraints": [],
                        "search_query": "spider man birthday banner",
                        "preferred_sites": ["amazon", "flipkart"],
                    },
                    "search_query": "spider man birthday banner",
                    "filters": {},
                },
                "results": [
                    {
                        "title": "Spider-Man Birthday Banner",
                        "url": "https://amazon.in/dp/TEST123456",
                        "price": 499.0,
                        "source": "Amazon",
                        "relevance_score": 0.9,
                        "rating": 4.5,
                        "review_count": 100,
                        "in_stock": True,
                        "image_url": "https://example.com/banner.jpg",
                        "final_score": 91.0,
                    }
                ],
                "total_found": 1,
            }
        ]

        with mock.patch(
            "shopping_agent.server.ShoppingOrchestrator.add_guided_party_items_to_cart",
            return_value={
                "success": True,
                "selected_product_urls": ["https://amazon.in/dp/TEST123456"],
                "cart": {
                    "items": [
                        {
                            "url": "https://amazon.in/dp/TEST123456",
                            "title": "Spider-Man Birthday Banner",
                            "image": "https://example.com/banner.jpg",
                            "success": True,
                            "message": "Added (cart: 1)",
                        }
                    ],
                    "cart_screenshot": "base64png",
                },
            },
        ) as cart_mock:
            response = client.post(
                "/guided-party/cart",
                json={
                    "listing_results": listing_results,
                    "selected_urls": ["https://amazon.in/dp/TEST123456"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["selected_product_urls"] == ["https://amazon.in/dp/TEST123456"]
        assert data["cart"]["items"][0]["success"] is True
        cart_mock.assert_called_once_with(
            listing_results=listing_results,
            selected_urls=["https://amazon.in/dp/TEST123456"],
        )


@pytest.mark.integration
class TestPerformance:
    """Performance tests for endpoints."""

    def test_plan_response_time(self):
        """Test that plan generation completes in reasonable time."""
        import time
        start = time.time()

        response = client.post(
            "/plan",
            json={"request": "birthday party supplies"}
        )

        elapsed = time.time() - start

        assert response.status_code == 200
        # Should complete in less than 60 seconds (first API call loads model)
        assert elapsed < 60.0

    def test_search_response_time(self):
        """Test that search completes in reasonable time."""
        import time

        items = [{
            "description": "Wireless mouse",
            "quantity": 1,
            "intent": "For computer",
            "required": True,
            "search_hints": ["wireless"],
            "constraints": [],
            "search_query": "wireless mouse",
            "preferred_sites": ["amazon"]
        }]

        start = time.time()
        response = client.post("/serp/search", json={"items": items})
        elapsed = time.time() - start

        assert response.status_code == 200
        # Single item search should complete in less than 5 seconds
        assert elapsed < 5.0
