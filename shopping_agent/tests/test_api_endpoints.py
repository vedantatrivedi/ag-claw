"""
Test suite for SerpAPI endpoints.

Run with: pytest shopping_agent/tests/test_api_endpoints.py -v
"""

import pytest
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
        # FastAPI should still handle it
        assert response.status_code in [200, 422]


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
        # Should complete in less than 10 seconds
        assert elapsed < 10.0

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
