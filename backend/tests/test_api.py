"""
Integration tests for the API endpoints.
These tests run against the actual backend service.
"""
import pytest
import httpx
from datetime import datetime, timezone, timedelta

# Base URL for the running backend
BASE_URL = "http://localhost:8000"


class TestHealthEndpoint:
    """Test the /api/health endpoint."""
    
    def test_health_check_success(self):
        """Test health check returns success."""
        response = httpx.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] in ['healthy', 'degraded']
        assert 'services' in data
        assert 'timestamp' in data


class TestPostsEndpoint:
    """Test the /api/posts endpoint."""
    
    def test_get_posts_default_params(self):
        """Test getting posts with default parameters."""
        response = httpx.get(f"{BASE_URL}/api/posts", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert 'posts' in data
        assert 'total' in data
        assert 'limit' in data
        assert 'offset' in data
        assert data['limit'] == 50  # API default
        assert data['offset'] == 0
    
    def test_get_posts_with_filters(self):
        """Test getting posts with custom limit and offset."""
        response = httpx.get(
            f"{BASE_URL}/api/posts",
            params={'limit': 20, 'offset': 10},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['limit'] == 20
        assert data['offset'] == 10
    
    def test_get_posts_with_date_range(self):
        """Test getting posts with date range filter."""
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        end_date = datetime.now(timezone.utc).isoformat()
        
        response = httpx.get(
            f"{BASE_URL}/api/posts",
            params={'start_date': start_date, 'end_date': end_date},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'posts' in data
        assert 'total' in data
    
    def test_get_posts_with_sentiment_filter(self):
        """Test getting posts filtered by sentiment."""
        response = httpx.get(
            f"{BASE_URL}/api/posts",
            params={'sentiment': 'positive'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'posts' in data
    
    def test_get_posts_invalid_limit(self):
        """Test validation error for invalid limit parameter."""
        response = httpx.get(
            f"{BASE_URL}/api/posts",
            params={'limit': -1},
            timeout=10
        )
        assert response.status_code == 422
    
    def test_get_posts_invalid_offset(self):
        """Test validation error for invalid offset parameter."""
        response = httpx.get(
            f"{BASE_URL}/api/posts",
            params={'offset': -1},
            timeout=10
        )
        assert response.status_code == 422


class TestSentimentAggregateEndpoint:
    """Test the /api/sentiment/aggregate endpoint."""
    
    def test_aggregate_with_hour_period(self):
        """Test aggregate with hour period."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/aggregate",
            params={'period': 'hour'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'period' in data
        assert data['period'] == 'hour'
        assert 'data' in data
    
    def test_aggregate_with_day_period(self):
        """Test aggregate with day period."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/aggregate",
            params={'period': 'day'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['period'] == 'day'
    
    def test_aggregate_with_minute_period(self):
        """Test aggregate with minute period."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/aggregate",
            params={'period': 'minute'},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['period'] == 'minute'
    
    def test_aggregate_missing_period(self):
        """Test validation error for missing required period."""
        response = httpx.get(f"{BASE_URL}/api/sentiment/aggregate", timeout=10)
        assert response.status_code == 422
    
    def test_aggregate_invalid_period(self):
        """Test validation error for invalid period."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/aggregate",
            params={'period': 'invalid'},
            timeout=10
        )
        assert response.status_code == 422


class TestSentimentDistributionEndpoint:
    """Test the /api/sentiment/distribution endpoint."""
    
    def test_distribution_default_params(self):
        """Test distribution with default parameters."""
        response = httpx.get(f"{BASE_URL}/api/sentiment/distribution", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert 'distribution' in data or 'total' in data
    
    def test_distribution_custom_hours(self):
        """Test distribution with custom time window."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/distribution",
            params={'hours': 48},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        # Verify response has expected keys
        assert 'distribution' in data or 'total' in data or 'timeframe_hours' in data
    
    def test_distribution_invalid_hours(self):
        """Test validation error for invalid hours parameter."""
        response = httpx.get(
            f"{BASE_URL}/api/sentiment/distribution",
            params={'hours': -1},
            timeout=10
        )
        assert response.status_code == 422


class TestCORSHeaders:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in response."""
        response = httpx.options(
            f"{BASE_URL}/api/health",
            headers={
                'Origin': 'http://localhost:3000',
                'Access-Control-Request-Method': 'GET'
            },
            timeout=10
        )
        
        # CORS headers should be present
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert 'access-control-allow-origin' in headers_lower


class TestErrorHandling:
    """Test API error handling."""
    
    def test_404_for_invalid_endpoint(self):
        """Test 404 response for non-existent endpoint."""
        response = httpx.get(f"{BASE_URL}/api/nonexistent", timeout=10)
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test 405 response for incorrect HTTP method."""
        response = httpx.post(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 405
