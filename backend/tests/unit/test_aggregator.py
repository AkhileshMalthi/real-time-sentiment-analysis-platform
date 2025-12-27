"""
Unit tests for the AggregatorService.
These tests verify the aggregation logic with properly mocked dependencies.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Mock Redis before importing
import sys
mock_redis_module = MagicMock()
sys.modules['redis'] = mock_redis_module
sys.modules['redis.asyncio'] = mock_redis_module

from services.aggregator import AggregatorService


class TestAggregatorService:
    """Test the AggregatorService class."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis
    
    @pytest.fixture
    def aggregator(self, mock_db, mock_redis):
        """Create aggregator service instance."""
        return AggregatorService(mock_db, mock_redis)
    
    @pytest.fixture
    def aggregator_no_redis(self, mock_db):
        """Create aggregator without Redis."""
        return AggregatorService(mock_db, None)

    # --- get_sentiment_aggregate tests ---
    
    @pytest.mark.asyncio
    async def test_get_sentiment_aggregate_valid_periods(self, aggregator, mock_db):
        """Test aggregation with valid periods (hour, day, minute)."""
        # Mock empty result
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        for period in ['hour', 'day', 'minute']:
            result = await aggregator.get_sentiment_aggregate(
                period=period,
                start_date=datetime.now(timezone.utc) - timedelta(hours=1),
                end_date=datetime.now(timezone.utc)
            )
            assert result['period'] == period
            assert 'data' in result
            assert 'summary' in result
    
    @pytest.mark.asyncio
    async def test_get_sentiment_aggregate_default_dates(self, aggregator, mock_db):
        """Test aggregation uses default dates when not provided."""
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator.get_sentiment_aggregate(period='hour')
        
        assert result['period'] == 'hour'
        assert 'start_date' in result
        assert 'end_date' in result
    
    @pytest.mark.asyncio
    async def test_get_sentiment_aggregate_with_data(self, aggregator, mock_db):
        """Test aggregation with actual data rows."""
        # Create mock row objects
        class MockRow:
            def __init__(self, time_bucket, sentiment_label, count, avg_confidence=0.9):
                self.time_bucket = time_bucket
                self.sentiment_label = sentiment_label
                self.count = count
                self.avg_confidence = avg_confidence
        
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        mock_result = Mock()
        mock_result.all = Mock(return_value=[
            MockRow(now, 'positive', 50, 0.95),
            MockRow(now, 'negative', 20, 0.85),
            MockRow(now, 'neutral', 30, 0.70),
        ])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=now - timedelta(hours=1),
            end_date=now
        )
        
        assert len(result['data']) >= 1
        # Check the summary
        assert result['summary']['positive_total'] == 50
        assert result['summary']['negative_total'] == 20
        assert result['summary']['neutral_total'] == 30
    
    # --- _organize_by_timestamp tests ---
    
    def test_organize_by_timestamp_groups_correctly(self, aggregator):
        """Test that rows are organized by timestamp."""
        class MockRow:
            def __init__(self, time_bucket, sentiment_label, count, avg_confidence=0.9):
                self.time_bucket = time_bucket
                self.sentiment_label = sentiment_label
                self.count = count
                self.avg_confidence = avg_confidence
        
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        rows = [
            MockRow(now, 'positive', 10, 0.9),
            MockRow(now, 'negative', 5, 0.8),
            MockRow(now + timedelta(hours=1), 'positive', 15, 0.85),
        ]
        
        result = aggregator._organize_by_timestamp(rows)
        
        assert len(result) == 2  # Two time buckets
    
    def test_organize_by_timestamp_empty(self, aggregator):
        """Test organizing empty rows."""
        result = aggregator._organize_by_timestamp([])
        assert result == {}
    
    # --- _calculate_percentages_and_summary tests ---
    
    def test_calculate_percentages_basic(self, aggregator):
        """Test percentage calculation."""
        time_buckets = {
            '2025-01-01T10:00:00': {
                'timestamp': '2025-01-01T10:00:00',
                'positive_count': 60,
                'negative_count': 20,
                'neutral_count': 20,
                'total_count': 100,
                'confidence_sum': 90.0,
                'confidence_count': 100
            }
        }
        
        data, summary = aggregator._calculate_percentages_and_summary(time_buckets)
        
        assert len(data) == 1
        assert data[0]['positive_percentage'] == 60.0
        assert data[0]['negative_percentage'] == 20.0
        assert data[0]['neutral_percentage'] == 20.0
        assert summary['total_posts'] == 100
    
    def test_calculate_percentages_empty(self, aggregator):
        """Test percentage calculation with empty data."""
        data, summary = aggregator._calculate_percentages_and_summary({})
        
        assert data == []
        assert summary['total_posts'] == 0
    
    # --- Cache tests ---
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self, aggregator, mock_redis):
        """Test that cache hit skips database."""
        cached = {'period': 'hour', 'data': [], 'summary': {}}
        mock_redis.get.return_value = json.dumps(cached)
        
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc)
        )
        
        assert result == cached
    
    @pytest.mark.asyncio
    async def test_no_redis_works(self, aggregator_no_redis, mock_db):
        """Test service works without Redis."""
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator_no_redis.get_sentiment_aggregate(period='hour')
        
        assert 'period' in result
    
    # --- get_sentiment_distribution tests ---
    
    @pytest.mark.asyncio
    async def test_get_sentiment_distribution_basic(self, aggregator, mock_db):
        """Test basic distribution calculation."""
        # Mock sentiment count result
        count_result = Mock()
        count_result.all = Mock(return_value=[
            ('positive', 100),
            ('negative', 30),
            ('neutral', 20),
        ])
        
        # Mock emotion result
        emotion_result = Mock()
        emotion_result.all = Mock(return_value=[
            ('joy', 50),
            ('sadness', 20),
        ])
        
        mock_db.execute.side_effect = [count_result, emotion_result]
        
        result = await aggregator.get_sentiment_distribution(hours=24)
        
        assert 'distribution' in result
        assert 'total' in result
        assert result['total'] == 150
    
    @pytest.mark.asyncio
    async def test_get_sentiment_distribution_empty(self, aggregator, mock_db):
        """Test distribution with no data."""
        count_result = Mock()
        count_result.all = Mock(return_value=[])
        
        emotion_result = Mock()
        emotion_result.all = Mock(return_value=[])
        
        mock_db.execute.side_effect = [count_result, emotion_result]
        
        result = await aggregator.get_sentiment_distribution(hours=24)
        
        assert result['total'] == 0


class TestAggregatorEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis
    
    @pytest.fixture
    def aggregator(self, mock_db, mock_redis):
        return AggregatorService(mock_db, mock_redis)
    
    @pytest.mark.asyncio
    async def test_redis_error_continues(self, aggregator, mock_db, mock_redis):
        """Test that Redis errors don't break the service."""
        mock_redis.get.side_effect = Exception("Redis down")
        
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        # Should not raise, should continue with DB
        result = await aggregator.get_sentiment_aggregate(period='hour')
        assert 'period' in result
    
    @pytest.mark.asyncio
    async def test_source_filter_applied(self, aggregator, mock_db):
        """Test that source filter is passed correctly."""
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            source='twitter'
        )
        
        # Just verify it doesn't error
        assert 'period' in result
