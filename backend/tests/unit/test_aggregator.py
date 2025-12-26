import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import json

# Mock Redis before importing
sys_modules_backup = {}

import sys
sys_modules_backup['redis'] = sys.modules.get('redis')
sys_modules_backup['redis.asyncio'] = sys.modules.get('redis.asyncio')

mock_redis = MagicMock()
mock_redis.asyncio = MagicMock()
sys.modules['redis'] = mock_redis
sys.modules['redis.asyncio'] = mock_redis.asyncio

from services.aggregator import AggregatorService


class TestAggregatorService:
    """Test the AggregatorService class."""
    
    @pytest.fixture
    async def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db
    
    @pytest.fixture
    async def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.ping = AsyncMock()
        return redis
    
    @pytest.fixture
    async def aggregator(self, mock_db, mock_redis):
        """Create aggregator service instance."""
        return AggregatorService(mock_db, mock_redis)
    
    @pytest.mark.asyncio
    async def test_get_sentiment_aggregate_hour(self, aggregator, mock_db):
        """Test hourly sentiment aggregation."""
        # Create mock row objects with named attributes
        class MockRow:
            def __init__(self, time_bucket, sentiment_label, count, avg_confidence=0.95):
                self.time_bucket = time_bucket
                self.sentiment_label = sentiment_label
                self.count = count
                self.avg_confidence = avg_confidence
        
        # Mock database response
        mock_result = Mock()
        mock_result.all = Mock(return_value=[
            MockRow(datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc), 'positive', 45),
            MockRow(datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc), 'negative', 10),
            MockRow(datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc), 'neutral', 25),
            MockRow(datetime(2025, 12, 26, 11, 0, 0, tzinfo=timezone.utc), 'positive', 50),
            MockRow(datetime(2025, 12, 26, 11, 0, 0, tzinfo=timezone.utc), 'negative', 15),
            MockRow(datetime(2025, 12, 26, 11, 0, 0, tzinfo=timezone.utc), 'neutral', 30),
        ])
        mock_db.execute.return_value = mock_result
        
        # Call service method
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=datetime(2025, 12, 26, 10, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 12, 26, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        # Verify results
        assert result['period'] == 'hour'
        assert len(result['data']) == 2
        
        # Check first hour
        first_hour = result['data'][0]
        assert first_hour['positive'] == 45
        assert first_hour['negative'] == 10
        assert first_hour['neutral'] == 25
        assert first_hour['total'] == 80
        
        # Check second hour
        second_hour = result['data'][1]
        assert second_hour['positive'] == 50
        assert second_hour['negative'] == 15
        assert second_hour['neutral'] == 30
        assert second_hour['total'] == 95
    
    @pytest.mark.asyncio
    async def test_get_sentiment_aggregate_invalid_period(self, aggregator):
        """Test that invalid period raises ValueError."""
        with pytest.raises(ValueError, match="Invalid period"):
            await aggregator.get_sentiment_aggregate(
                period='invalid',
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc)
            )
    
    @pytest.mark.asyncio
    async def test_get_sentiment_distribution(self, aggregator, mock_db):
        """Test sentiment distribution calculation."""
        # Mock database responses
        # First query: distribution
        dist_result = AsyncMock()
        dist_result.fetchall = AsyncMock(return_value=[
            ('positive', 150),
            ('negative', 50),
            ('neutral', 50),
        ])
        
        # Second query: top emotions
        emotion_result = AsyncMock()
        emotion_result.fetchall = AsyncMock(return_value=[
            ('joy', 80),
            ('neutral', 50),
            ('anger', 30),
            ('sadness', 20),
            ('fear', 15),
        ])
        
        mock_db.execute.side_effect = [dist_result, emotion_result]
        
        # Call service method
        result = await aggregator.get_sentiment_distribution(hours=24)
        
        # Verify results
        assert result['time_window'] == '24 hours'
        assert len(result['distribution']) == 3
        
        # Check distribution
        positive = next(d for d in result['distribution'] if d['sentiment'] == 'positive')
        assert positive['count'] == 150
        assert positive['percentage'] == '60.00'
        
        # Check summary
        assert result['summary']['total_posts'] == 250
        assert result['summary']['positive'] == 150
        assert result['summary']['negative'] == 50
        assert result['summary']['neutral'] == 50
        
        # Check top emotions
        assert len(result['top_emotions']) == 5
        assert result['top_emotions'][0]['emotion'] == 'joy'
        assert result['top_emotions'][0]['count'] == 80
    
    @pytest.mark.asyncio
    async def test_get_from_cache_hit(self, aggregator, mock_redis):
        """Test cache hit returns cached data."""
        cached_data = {'test': 'data'}
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = await aggregator._get_from_cache('test_key')
        
        assert result == cached_data
        mock_redis.get.assert_called_once_with('test_key')
    
    @pytest.mark.asyncio
    async def test_get_from_cache_miss(self, aggregator, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None
        
        result = await aggregator._get_from_cache('test_key')
        
        assert result is None
        mock_redis.get.assert_called_once_with('test_key')
    
    @pytest.mark.asyncio
    async def test_save_to_cache(self, aggregator, mock_redis):
        """Test saving data to cache."""
        data = {'test': 'data'}
        
        await aggregator._save_to_cache('test_key', data, ttl=60)
        
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == 'test_key'
        assert args[1] == 60
        assert json.loads(args[2]) == data
    
    @pytest.mark.asyncio
    async def test_organize_by_timestamp(self, aggregator):
        """Test timestamp organization."""
        rows = [
            (datetime(2025, 12, 26, 10, 0, 0), 'positive', 10),
            (datetime(2025, 12, 26, 10, 0, 0), 'negative', 5),
            (datetime(2025, 12, 26, 11, 0, 0), 'positive', 15),
        ]
        
        result = aggregator._organize_by_timestamp(rows)
        
        assert len(result) == 2
        assert datetime(2025, 12, 26, 10, 0, 0) in result
        assert datetime(2025, 12, 26, 11, 0, 0) in result
        
        first_hour = result[datetime(2025, 12, 26, 10, 0, 0)]
        assert first_hour['positive'] == 10
        assert first_hour['negative'] == 5
        assert first_hour['neutral'] == 0
    
    @pytest.mark.asyncio
    async def test_calculate_percentages_and_summary(self, aggregator):
        """Test percentage calculation."""
        rows = [
            ('positive', 150),
            ('negative', 50),
            ('neutral', 50),
        ]
        
        distribution, summary = aggregator._calculate_percentages_and_summary(rows)
        
        # Check distribution
        assert len(distribution) == 3
        positive = next(d for d in distribution if d['sentiment'] == 'positive')
        assert positive['percentage'] == '60.00'
        
        # Check summary
        assert summary['total_posts'] == 250
        assert summary['positive'] == 150
        assert summary['negative'] == 50
        assert summary['neutral'] == 50
    
    @pytest.mark.asyncio
    async def test_aggregate_with_cache(self, aggregator, mock_db, mock_redis):
        """Test that aggregation uses cache when available."""
        # Set up cache hit
        cached_data = {
            'period': 'hour',
            'data': [{'test': 'cached'}]
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc)
        )
        
        # Verify cache was used and database was not called
        assert result == cached_data
        mock_db.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_distribution_with_cache(self, aggregator, mock_db, mock_redis):
        """Test that distribution uses cache when available."""
        # Set up cache hit
        cached_data = {
            'time_window': '24 hours',
            'distribution': [],
            'summary': {},
            'top_emotions': []
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        result = await aggregator.get_sentiment_distribution(hours=24)
        
        # Verify cache was used and database was not called
        assert result == cached_data
        mock_db.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_top_emotions(self, aggregator, mock_db):
        """Test getting top emotions."""
        # Mock database response
        mock_result = AsyncMock()
        mock_result.fetchall = AsyncMock(return_value=[
            ('joy', 100),
            ('sadness', 50),
            ('anger', 30),
        ])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator._get_top_emotions(
            datetime.now(timezone.utc) - timedelta(hours=24)
        )
        
        assert len(result) == 3
        assert result[0] == {'emotion': 'joy', 'count': 100}
        assert result[1] == {'emotion': 'sadness', 'count': 50}
        assert result[2] == {'emotion': 'anger', 'count': 30}
    
    @pytest.mark.asyncio
    async def test_empty_database_returns_empty_aggregate(self, aggregator, mock_db):
        """Test handling of empty database."""
        mock_result = AsyncMock()
        mock_result.fetchall = AsyncMock(return_value=[])
        mock_db.execute.return_value = mock_result
        
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc)
        )
        
        assert result['period'] == 'hour'
        assert result['data'] == []
    
    @pytest.mark.asyncio
    async def test_redis_unavailable_skips_cache(self, aggregator, mock_db, mock_redis):
        """Test that service works when Redis is unavailable."""
        # Make Redis operations fail
        mock_redis.get.side_effect = Exception("Redis connection failed")
        
        # Mock database response
        mock_result = AsyncMock()
        mock_result.fetchall = AsyncMock(return_value=[
            (datetime.now(timezone.utc), 'positive', 10),
        ])
        mock_db.execute.return_value = mock_result
        
        # Should still work without cache
        result = await aggregator.get_sentiment_aggregate(
            period='hour',
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc)
        )
        
        # Verify database was called
        mock_db.execute.assert_called_once()
        assert 'data' in result


# Restore sys.modules
def teardown_module():
    """Restore original sys.modules after tests."""
    for key, value in sys_modules_backup.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value
