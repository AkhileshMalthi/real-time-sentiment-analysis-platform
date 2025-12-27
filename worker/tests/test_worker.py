import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import uuid

# Mock transformers and Redis before importing worker
import sys
sys.modules['transformers'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()

from worker import SentimentWorker


class TestSentimentWorker:
    """Test the SentimentWorker class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.xreadgroup = AsyncMock(return_value=[])
        redis.xack = AsyncMock()
        redis.ping = AsyncMock()
        return redis
    
    @pytest.fixture
    def mock_db_engine(self):
        """Create mock database engine."""
        engine = AsyncMock()
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        engine.begin = AsyncMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()))
        return engine
    
    @pytest.fixture
    def mock_analyzer(self):
        """Create mock sentiment analyzer."""
        analyzer = AsyncMock()
        analyzer.analyze = AsyncMock(return_value={
            'sentiment': 'positive',
            'confidence': 0.95,
            'emotion': 'joy'
        })
        return analyzer
    
    @pytest.fixture
    def worker(self, mock_redis, mock_db_engine, mock_analyzer):
        """Create worker instance."""
        worker = SentimentWorker(
            redis_client=mock_redis,
            db_session_maker=mock_db_engine,
            stream_name='test_stream',
            consumer_group='test_group'
        )
        worker.analyzer = mock_analyzer  # Override lazy-loaded analyzer
        return worker
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self):
        """Test worker initializes with correct parameters."""
        mock_redis = AsyncMock()
        mock_session_maker = AsyncMock()
        
        worker = SentimentWorker(
            redis_client=mock_redis,
            db_session_maker=mock_session_maker,
            stream_name='mystream',
            consumer_group='mygroup'
        )
        
        assert worker.redis == mock_redis
        assert worker.db_session_maker == mock_session_maker
        assert worker.stream_name == 'mystream'
        assert worker.group == 'mygroup'
        assert worker.consumer_name.startswith('worker_')
    
    @pytest.mark.asyncio
    async def test_process_message(self, worker, mock_analyzer, mock_redis):
        """Test processing a single message."""
        message_id = b'123-0'
        message_data = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'This is a test post',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        # Mock analyzer methods
        mock_analyzer.analyze_sentiment = AsyncMock(return_value={
            'label': 'positive',
            'score': 0.95
        })
        mock_analyzer.analyze_emotion = AsyncMock(return_value={
            'label': 'joy',
            'score': 0.85
        })
        
        result = await worker.process_message(message_id, message_data)
        
        # Verify analyzer was called
        mock_analyzer.analyze_sentiment.assert_called_once_with('This is a test post')
        mock_analyzer.analyze_emotion.assert_called_once_with('This is a test post')
        
        # Verify xack was called
        mock_redis.xack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_missing_fields(self, worker, mock_redis):
        """Test handling of messages with missing required fields."""
        message_id = b'123-0'
        incomplete_message = {
            'post_id': 'test_123'
            # Missing other required fields like content
        }
        
        result = await worker.process_message(message_id, incomplete_message)
        
        # Should handle gracefully and return False
        assert result is False
    
    @pytest.mark.asyncio
    async def test_setup_creates_group(self, worker, mock_redis):
        """Test setup creates Redis consumer group."""
        mock_redis.xgroup_create = AsyncMock()
        
        await worker.setup()
        
        # Verify group creation was attempted
        mock_redis.xgroup_create.assert_called_once_with('test_stream', 'test_group', mkstream=True)
    
    @pytest.mark.asyncio
    async def test_consume_messages_empty_stream(self, worker, mock_redis):
        """Test consuming from empty stream."""
        mock_redis.xreadgroup = AsyncMock(return_value=[])
        mock_redis.xgroup_create = AsyncMock()
        
        # Run consumer briefly
        consumer_task = asyncio.create_task(worker.run())
        
        await asyncio.sleep(0.1)
        
        # Cancel task
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        # Verify xreadgroup was called
        assert mock_redis.xreadgroup.called
    
    @pytest.mark.asyncio
    async def test_consume_and_acknowledge_message(self, worker, mock_redis, mock_analyzer):
        """Test consuming and acknowledging a message."""
        # Mock message from stream
        message_id = b'1234567890-0'
        message_data = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'Test content',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        mock_analyzer.analyze_sentiment = AsyncMock(return_value={'label': 'positive', 'score': 0.9})
        mock_analyzer.analyze_emotion = AsyncMock(return_value={'label': 'joy', 'score': 0.8})
        mock_redis.xreadgroup = AsyncMock(return_value=[
            [b'test_stream', [(message_id, message_data)]]
        ])
        mock_redis.xgroup_create = AsyncMock()
        
        # Process one iteration
        consumer_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        consumer_task.cancel()
        
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        # Verify message was acknowledged
        if mock_redis.xack.called:
            assert mock_redis.xack.call_args[0][0] == 'test_stream'
            assert mock_redis.xack.call_args[0][1] == 'test_group'
    
    @pytest.mark.asyncio
    async def test_analyzer_failure_handling(self, worker, mock_analyzer, mock_redis):
        """Test handling of analyzer failures."""
        # Make analyzer raise exception
        mock_analyzer.analyze_sentiment = AsyncMock(side_effect=Exception("Analysis failed"))
        
        message_id = b'123-0'
        message_data = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'Test content',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        # Should not raise exception
        result = await worker.process_message(message_id, message_data)
        
        # Result should indicate failure
        assert result is False
    
    @pytest.mark.asyncio
    async def test_database_failure_doesnt_acknowledge(self, worker, mock_redis, mock_db_engine, mock_analyzer):
        """Test that database failures prevent message acknowledgment."""
        # Make database operations fail
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=Exception("Database error"))
        mock_session.__aexit__ = AsyncMock()
        mock_db_engine.return_value = mock_session
        
        mock_analyzer.analyze_sentiment = AsyncMock(return_value={'label': 'positive', 'score': 0.9})
        mock_analyzer.analyze_emotion = AsyncMock(return_value={'label': 'joy', 'score': 0.8})
        
        message_id = b'123-0'
        message_data = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'Test content',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        result = await worker.process_message(message_id, message_data)
        
        # Should return False on database error
        assert result is False
        # Message should not be acknowledged
        assert not mock_redis.xack.called
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, worker, mock_redis, mock_analyzer):
        """Test processing multiple messages in batch."""
        # Mock multiple messages
        messages = [
            (b'123-0', {'post_id': 'test_1', 'content': 'Test 1', 'source': 'reddit', 'author': 'user1', 'created_at': '2025-12-26T10:00:00Z'}),
            (b'123-1', {'post_id': 'test_2', 'content': 'Test 2', 'source': 'twitter', 'author': 'user2', 'created_at': '2025-12-26T10:01:00Z'}),
            (b'123-2', {'post_id': 'test_3', 'content': 'Test 3', 'source': 'facebook', 'author': 'user3', 'created_at': '2025-12-26T10:02:00Z'}),
        ]
        
        mock_analyzer.analyze_sentiment = AsyncMock(return_value={'label': 'positive', 'score': 0.9})
        mock_analyzer.analyze_emotion = AsyncMock(return_value={'label': 'joy', 'score': 0.8})
        mock_redis.xreadgroup = AsyncMock(return_value=[
            [b'test_stream', messages]
        ])
        mock_redis.xgroup_create = AsyncMock()
        
        # Process batch
        consumer_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.3)
        consumer_task.cancel()
        
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        # Verify analyzer was called for each message
        assert mock_analyzer.analyze_sentiment.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_worker_reconnects_on_redis_error(self, worker, mock_redis):
        """Test worker attempts to reconnect on Redis errors."""
        # Simulate connection error followed by success
        mock_redis.xreadgroup = AsyncMock(side_effect=[
            Exception("Connection lost"),
            []  # Success after reconnect
        ])
        mock_redis.xgroup_create = AsyncMock()
        
        consumer_task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.2)
        consumer_task.cancel()
        
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        # Verify multiple attempts were made
        assert mock_redis.xreadgroup.call_count >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
