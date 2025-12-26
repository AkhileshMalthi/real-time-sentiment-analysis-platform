import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import os

from services.alerting import AlertService


class TestAlertService:
    """Test the AlertService class."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_db_session_maker(self, mock_db_session):
        """Create mock database session maker."""
        maker = MagicMock()
        maker.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
        maker.return_value.__aexit__ = AsyncMock(return_value=None)
        return maker
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.ping = AsyncMock()
        return redis
    
    @pytest.fixture
    def alert_service(self, mock_db_session_maker, mock_redis):
        """Create alert service instance."""
        with patch.dict(os.environ, {
            'ALERT_NEGATIVE_RATIO_THRESHOLD': '2.0',
            'ALERT_WINDOW_MINUTES': '5',
            'ALERT_MIN_POSTS': '10'
        }):
            return AlertService(
                db_session_maker=mock_db_session_maker,
                redis_client=mock_redis
            )
    
    @pytest.mark.asyncio
    async def test_check_thresholds_no_alert_below_threshold(self, alert_service, mock_db_session):
        """Test that no alert is triggered when ratio is below threshold."""
        # Mock database response - ratio below threshold (20/60 = 0.33 < 2.0)
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=60),
            Mock(sentiment_label='negative', count=20),
            Mock(sentiment_label='neutral', count=20),
        ])
        mock_db_session.execute.return_value = mock_result
        
        # Check threshold
        result = await alert_service.check_thresholds()
        
        # Verify no alert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_thresholds_triggers_alert(self, alert_service, mock_db_session):
        """Test that alert is triggered when negative ratio exceeds threshold."""
        # Mock database response - high negative ratio (150/30 = 5.0 > 2.0)
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=30),
            Mock(sentiment_label='negative', count=150),
            Mock(sentiment_label='neutral', count=20),
        ])
        mock_db_session.execute.return_value = mock_result
        
        # Check threshold
        result = await alert_service.check_thresholds()
        
        # Verify alert was triggered
        assert result is not None
        assert result['alert_triggered'] is True
        assert result['alert_type'] == 'high_negative_ratio'
        assert result['actual_ratio'] == 5.0
        assert result['threshold'] == 2.0
        assert result['metrics']['positive_count'] == 30
        assert result['metrics']['negative_count'] == 150
    
    @pytest.mark.asyncio
    async def test_check_thresholds_insufficient_data(self, alert_service, mock_db_session):
        """Test handling when not enough posts in window."""
        # Mock database response - below min_posts threshold
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=3),
            Mock(sentiment_label='negative', count=2),
        ])
        mock_db_session.execute.return_value = mock_result
        
        # Check threshold
        result = await alert_service.check_thresholds()
        
        # Should return None (not enough data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_thresholds_no_positive_posts(self, alert_service, mock_db_session):
        """Test handling when there are no positive posts (division by zero)."""
        # Mock database response - no positive posts
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='negative', count=50),
            Mock(sentiment_label='neutral', count=20),
        ])
        mock_db_session.execute.return_value = mock_result
        
        # Check threshold
        result = await alert_service.check_thresholds()
        
        # Should trigger alert with very high ratio
        assert result is not None
        assert result['alert_triggered'] is True
        assert result['actual_ratio'] == 999.99  # Capped infinity value
    
    @pytest.mark.asyncio
    async def test_check_thresholds_empty_database(self, alert_service, mock_db_session):
        """Test handling of empty database."""
        # Mock empty database response
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[])
        mock_db_session.execute.return_value = mock_result
        
        # Should not raise exception
        result = await alert_service.check_thresholds()
        
        # Should return None (no data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_save_alert(self, alert_service, mock_db_session):
        """Test saving alert to database."""
        alert_data = {
            'alert_type': 'high_negative_ratio',
            'threshold': 2.0,
            'actual_ratio': 5.0,
            'window_start': datetime.now(timezone.utc) - timedelta(minutes=5),
            'window_end': datetime.now(timezone.utc),
            'metrics': {
                'total_count': 100,
                'positive_count': 20,
                'negative_count': 60,
                'neutral_count': 20
            }
        }
        
        # Mock alert object with id
        mock_alert = Mock()
        mock_alert.id = 123
        mock_db_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 123))
        
        # Save alert
        alert_id = await alert_service.save_alert(alert_data)
        
        # Verify database operations were called
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_thresholds_exact_threshold(self, alert_service, mock_db_session):
        """Test behavior when ratio equals threshold exactly."""
        # Mock database response - ratio exactly at threshold (40/20 = 2.0)
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=20),
            Mock(sentiment_label='negative', count=40),
            Mock(sentiment_label='neutral', count=10),
        ])
        mock_db_session.execute.return_value = mock_result
        
        result = await alert_service.check_thresholds()
        
        # Should not trigger (threshold is >, not >=)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_thresholds_calculates_ratio_correctly(self, alert_service, mock_db_session):
        """Test correct calculation of negative/positive ratio."""
        # Mock database response - negative=75, positive=25, ratio=3.0
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=25),
            Mock(sentiment_label='negative', count=75),
            Mock(sentiment_label='neutral', count=10),
        ])
        mock_db_session.execute.return_value = mock_result
        
        result = await alert_service.check_thresholds()
        
        # Verify alert with correct ratio
        assert result is not None
        assert result['actual_ratio'] == 3.0
        assert result['metrics']['positive_count'] == 25
        assert result['metrics']['negative_count'] == 75
        assert result['metrics']['total_count'] == 110
    
    def test_alert_service_initialization(self):
        """Test alert service initialization with environment variables."""
        with patch.dict(os.environ, {
            'ALERT_NEGATIVE_RATIO_THRESHOLD': '3.5',
            'ALERT_WINDOW_MINUTES': '10',
            'ALERT_MIN_POSTS': '20'
        }):
            mock_maker = MagicMock()
            mock_redis = AsyncMock()
            
            service = AlertService(
                db_session_maker=mock_maker,
                redis_client=mock_redis
            )
            
            assert service.negative_ratio_threshold == 3.5
            assert service.window_minutes == 10
            assert service.min_posts == 20
    
    @pytest.mark.asyncio
    async def test_alert_includes_window_times(self, alert_service, mock_db_session):
        """Test that alert includes window start and end times."""
        # Mock database response triggering alert
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=10),
            Mock(sentiment_label='negative', count=50),
        ])
        mock_db_session.execute.return_value = mock_result
        
        result = await alert_service.check_thresholds()
        
        # Verify window times are included
        assert 'window_start' in result
        assert 'window_end' in result
        
        # Verify times are reasonable (within last 10 minutes)
        window_start = result['window_start']
        now = datetime.now(timezone.utc)
        assert (now - window_start).total_seconds() < 600
    
    @pytest.mark.asyncio
    async def test_alert_includes_all_metrics(self, alert_service, mock_db_session):
        """Test that alert includes all required metrics."""
        mock_result = AsyncMock()
        mock_result.all = Mock(return_value=[
            Mock(sentiment_label='positive', count=20),
            Mock(sentiment_label='negative', count=60),
            Mock(sentiment_label='neutral', count=30),
        ])
        mock_db_session.execute.return_value = mock_result
        
        result = await alert_service.check_thresholds()
        
        # Verify all metrics are present
        assert result is not None
        assert 'metrics' in result
        assert result['metrics']['positive_count'] == 20
        assert result['metrics']['negative_count'] == 60
        assert result['metrics']['neutral_count'] == 30
        assert result['metrics']['total_count'] == 110


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
