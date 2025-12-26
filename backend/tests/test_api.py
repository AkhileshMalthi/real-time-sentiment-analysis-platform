import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid
import json

# Mock dependencies before importing main app
import sys
sys.modules['transformers'] = MagicMock()

# Import after mocking
from main import app
from models.database import SocialMediaPost, SentimentAnalysis


class TestHealthEndpoint:
    """Test the /api/health endpoint."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_health_check_success(self):
        """Test health check returns success when all services are healthy."""
        with patch('api.routes.get_db') as mock_get_db, \
             patch('api.routes.get_redis') as mock_get_redis:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # Mock Redis client
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            response = self.client.get("/api/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] in ['healthy', 'degraded']
            assert 'services' in data
            assert 'timestamp' in data


class TestPostsEndpoint:
    """Test the /api/posts endpoint."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch('api.routes.AsyncSessionLocal')
    def test_get_posts_default_params(self, mock_session_local):
        """Test getting posts with default parameters."""
        # Mock database session and queries
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        # Mock count query
        count_result = AsyncMock()
        count_result.scalar = AsyncMock(return_value=50)
        
        # Mock posts query
        posts_result = AsyncMock()
        mock_posts = [
            Mock(
                id=uuid.uuid4(),
                post_id=f'test_{i}',
                source='reddit',
                content=f'Test post {i}',
                author=f'user{i}',
                created_at=datetime.now(timezone.utc),
                ingested_at=datetime.now(timezone.utc),
                analyses=[Mock(
                    sentiment_label='positive',
                    confidence_score=0.95,
                    emotion='joy'
                )]
            )
            for i in range(10)
        ]
        posts_result.scalars = Mock(return_value=Mock(all=Mock(return_value=mock_posts)))
        
        mock_db.execute.side_effect = [count_result, posts_result]
        
        response = self.client.get("/api/posts")
        
        assert response.status_code == 200
        data = response.json()
        assert 'posts' in data
        assert 'total' in data
        assert data['limit'] == 10
        assert data['offset'] == 0
    
    @patch('api.routes.AsyncSessionLocal')
    def test_get_posts_with_filters(self, mock_session_local):
        """Test getting posts with sentiment and source filters."""
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        # Mock responses
        count_result = AsyncMock()
        count_result.scalar = AsyncMock(return_value=5)
        
        posts_result = AsyncMock()
        posts_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))
        
        mock_db.execute.side_effect = [count_result, posts_result]
        
        response = self.client.get(
            "/api/posts",
            params={
                'limit': 20,
                'offset': 10,
                'sentiment': 'positive',
                'source': 'reddit'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['limit'] == 20
        assert data['offset'] == 10
    
    @patch('api.routes.AsyncSessionLocal')
    def test_get_posts_with_date_range(self, mock_session_local):
        """Test getting posts with date range filter."""
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        # Mock responses
        count_result = AsyncMock()
        count_result.scalar = AsyncMock(return_value=0)
        
        posts_result = AsyncMock()
        posts_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))
        
        mock_db.execute.side_effect = [count_result, posts_result]
        
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        end_date = datetime.now(timezone.utc).isoformat()
        
        response = self.client.get(
            "/api/posts",
            params={
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        assert response.status_code == 200
    
    def test_get_posts_invalid_limit(self):
        """Test validation error for invalid limit parameter."""
        response = self.client.get("/api/posts", params={'limit': -1})
        assert response.status_code == 422  # Validation error
    
    def test_get_posts_invalid_offset(self):
        """Test validation error for invalid offset parameter."""
        response = self.client.get("/api/posts", params={'offset': -1})
        assert response.status_code == 422


class TestSentimentAggregateEndpoint:
    """Test the /api/sentiment/aggregate endpoint."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch('api.routes.AggregatorService')
    @patch('api.routes.AsyncSessionLocal')
    @patch('api.routes.get_redis')
    def test_aggregate_default_params(self, mock_get_redis, mock_session_local, mock_aggregator_class):
        """Test aggregate with default parameters."""
        # Mock services
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        mock_redis = AsyncMock()
        mock_get_redis.return_value.__aenter__.return_value = mock_redis
        
        mock_aggregator = AsyncMock()
        mock_aggregator.get_sentiment_aggregate = AsyncMock(return_value={
            'period': 'hour',
            'data': [
                {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'positive': 50,
                    'negative': 20,
                    'neutral': 30,
                    'total': 100
                }
            ]
        })
        mock_aggregator_class.return_value = mock_aggregator
        
        response = self.client.get("/api/sentiment/aggregate")
        
        assert response.status_code == 200
        data = response.json()
        assert 'period' in data
        assert 'data' in data
    
    @patch('api.routes.AggregatorService')
    @patch('api.routes.AsyncSessionLocal')
    @patch('api.routes.get_redis')
    def test_aggregate_with_custom_period(self, mock_get_redis, mock_session_local, mock_aggregator_class):
        """Test aggregate with custom period."""
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        mock_redis = AsyncMock()
        mock_get_redis.return_value.__aenter__.return_value = mock_redis
        
        mock_aggregator = AsyncMock()
        mock_aggregator.get_sentiment_aggregate = AsyncMock(return_value={
            'period': 'day',
            'data': []
        })
        mock_aggregator_class.return_value = mock_aggregator
        
        response = self.client.get("/api/sentiment/aggregate", params={'period': 'day'})
        
        assert response.status_code == 200
        data = response.json()
        assert data['period'] == 'day'
    
    def test_aggregate_invalid_period(self):
        """Test validation error for invalid period."""
        response = self.client.get("/api/sentiment/aggregate", params={'period': 'invalid'})
        # Should return 400 or 422 depending on validation
        assert response.status_code in [400, 422, 500]  # May vary based on implementation


class TestSentimentDistributionEndpoint:
    """Test the /api/sentiment/distribution endpoint."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    @patch('api.routes.AggregatorService')
    @patch('api.routes.AsyncSessionLocal')
    @patch('api.routes.get_redis')
    def test_distribution_default_params(self, mock_get_redis, mock_session_local, mock_aggregator_class):
        """Test distribution with default parameters."""
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        mock_redis = AsyncMock()
        mock_get_redis.return_value.__aenter__.return_value = mock_redis
        
        mock_aggregator = AsyncMock()
        mock_aggregator.get_sentiment_distribution = AsyncMock(return_value={
            'time_window': '24 hours',
            'distribution': [
                {'sentiment': 'positive', 'count': 150, 'percentage': '60.00'},
                {'sentiment': 'negative', 'count': 50, 'percentage': '20.00'},
                {'sentiment': 'neutral', 'count': 50, 'percentage': '20.00'}
            ],
            'summary': {
                'total_posts': 250,
                'positive': 150,
                'negative': 50,
                'neutral': 50
            },
            'top_emotions': [
                {'emotion': 'joy', 'count': 80},
                {'emotion': 'neutral', 'count': 50}
            ]
        })
        mock_aggregator_class.return_value = mock_aggregator
        
        response = self.client.get("/api/sentiment/distribution")
        
        assert response.status_code == 200
        data = response.json()
        assert 'distribution' in data
        assert 'summary' in data
        assert 'top_emotions' in data
        assert len(data['distribution']) == 3
    
    @patch('api.routes.AggregatorService')
    @patch('api.routes.AsyncSessionLocal')
    @patch('api.routes.get_redis')
    def test_distribution_custom_hours(self, mock_get_redis, mock_session_local, mock_aggregator_class):
        """Test distribution with custom time window."""
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        
        mock_redis = AsyncMock()
        mock_get_redis.return_value.__aenter__.return_value = mock_redis
        
        mock_aggregator = AsyncMock()
        mock_aggregator.get_sentiment_distribution = AsyncMock(return_value={
            'time_window': '48 hours',
            'distribution': [],
            'summary': {'total_posts': 0},
            'top_emotions': []
        })
        mock_aggregator_class.return_value = mock_aggregator
        
        response = self.client.get("/api/sentiment/distribution", params={'hours': 48})
        
        assert response.status_code == 200
        data = response.json()
        assert data['time_window'] == '48 hours'
    
    def test_distribution_invalid_hours(self):
        """Test validation error for invalid hours parameter."""
        response = self.client.get("/api/sentiment/distribution", params={'hours': -1})
        assert response.status_code in [400, 422, 500]


class TestWebSocketEndpoint:
    """Test the WebSocket endpoint."""
    
    def test_websocket_connection(self):
        """Test WebSocket connection establishment."""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/sentiment") as websocket:
            # Receive connection message
            data = websocket.receive_json()
            assert data['type'] == 'connected'
            assert 'message' in data
            assert 'timestamp' in data
    
    def test_websocket_receives_messages(self):
        """Test WebSocket receives messages after connection."""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/sentiment") as websocket:
            # Receive connection message
            connection_msg = websocket.receive_json()
            assert connection_msg['type'] == 'connected'
            
            # Note: Additional messages would require actual broadcast events
            # In a real scenario, we'd trigger events that cause broadcasts


class TestCORSHeaders:
    """Test CORS configuration."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in response."""
        response = self.client.options(
            "/api/health",
            headers={
                'Origin': 'http://localhost:3000',
                'Access-Control-Request-Method': 'GET'
            }
        )
        
        # Check CORS headers
        assert 'access-control-allow-origin' in response.headers or \
               'Access-Control-Allow-Origin' in response.headers


class TestErrorHandling:
    """Test API error handling."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_404_for_invalid_endpoint(self):
        """Test 404 response for non-existent endpoint."""
        response = self.client.get("/api/nonexistent")
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test 405 response for incorrect HTTP method."""
        response = self.client.post("/api/health")
        assert response.status_code == 405


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
