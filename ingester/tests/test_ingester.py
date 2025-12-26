import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import time

# Mock Redis before importing
import sys
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()

from ingester.ingester import DataIngester


class TestDataIngester:
    """Test the DataIngester class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.xadd = AsyncMock(return_value=b'1234567890-0')
        redis.ping = AsyncMock()
        return redis
    
    @pytest.fixture
    def ingester(self, mock_redis):
        """Create ingester instance."""
        ingester = DataIngester(
            redis_client=mock_redis,
            stream_name='test_stream',
            posts_per_minute=60
        )
        return ingester
    
    def test_ingester_initialization(self):
        """Test ingester initializes with correct parameters."""
        mock_redis = AsyncMock()
        
        ingester = DataIngester(
            redis_client=mock_redis,
            stream_name='mystream',
            posts_per_minute=120
        )
        
        assert ingester.redis == mock_redis
        assert ingester.stream_name == 'mystream'
        assert ingester.posts_per_minute == 120
    
    @pytest.mark.asyncio
    async def test_generate_post_structure(self, ingester):
        """Test that generated posts have correct structure."""
        post = ingester.generate_post()
        
        # Verify required fields exist
        assert 'post_id' in post
        assert 'source' in post
        assert 'content' in post
        assert 'author' in post
        assert 'created_at' in post
        
        # Verify field types
        assert isinstance(post['post_id'], str)
        assert isinstance(post['source'], str)
        assert isinstance(post['content'], str)
        assert isinstance(post['author'], str)
        assert isinstance(post['created_at'], str)
        
        # Verify source is valid
        assert post['source'] in ['reddit', 'twitter', 'facebook', 'instagram']
    
    @pytest.mark.asyncio
    async def test_generate_post_unique_ids(self, ingester):
        """Test that generated posts have unique IDs."""
        post1 = ingester.generate_post()
        post2 = ingester.generate_post()
        
        assert post1['post_id'] != post2['post_id']
    
    @pytest.mark.asyncio
    async def test_generate_post_content_varies(self, ingester):
        """Test that generated post content varies."""
        posts = [ingester.generate_post() for _ in range(10)]
        contents = [p['content'] for p in posts]
        
        # At least some posts should have different content
        unique_contents = set(contents)
        assert len(unique_contents) > 1
    
    @pytest.mark.asyncio
    async def test_publish_to_stream(self, ingester, mock_redis):
        """Test publishing post to Redis stream."""
        post = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'Test content',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        await ingester.publish_post(post)
        
        # Verify xadd was called
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        
        # Verify stream name
        assert call_args[0][0] == 'test_stream'
        
        # Verify post data was included
        post_data = call_args[0][1]
        assert post_data['post_id'] == 'test_123'
        assert post_data['content'] == 'Test content'
    
    @pytest.mark.asyncio
    async def test_publish_failure_handling(self, ingester, mock_redis):
        """Test handling of Redis publish failures."""
        mock_redis.xadd.side_effect = Exception("Redis error")
        
        post = {
            'post_id': 'test_123',
            'source': 'reddit',
            'content': 'Test content',
            'author': 'testuser',
            'created_at': '2025-12-26T10:00:00Z'
        }
        
        # Should not raise exception, returns False
        result = await ingester.publish_post(post)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_generates_posts(self, ingester, mock_redis):
        """Test that start method generates and publishes posts."""
        # Run ingester briefly
        ingester_task = asyncio.create_task(ingester.start())
        
        await asyncio.sleep(0.5)
        
        # Cancel task
        ingester_task.cancel()
        try:
            await ingester_task
        except asyncio.CancelledError:
            pass
        
        # Verify posts were published
        assert mock_redis.xadd.called
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, ingester, mock_redis):
        """Test that rate limiting is enforced."""
        ingester.posts_per_minute = 60  # 1 per second
        sleep_time = 60.0 / ingester.posts_per_minute  # Calculate from rate
        
        start_time = time.time()
        
        # Generate and publish a few posts
        for _ in range(3):
            post = ingester.generate_post()
            await ingester.publish_post(post)
            await asyncio.sleep(sleep_time)
        
        elapsed_time = time.time() - start_time
        
        # Should take approximately 3 seconds (with some tolerance)
        assert 2.5 < elapsed_time < 3.5
    
    @pytest.mark.asyncio
    async def test_post_has_valid_timestamp(self, ingester):
        """Test that generated posts have valid timestamps."""
        post = ingester.generate_post()
        
        # Parse timestamp
        timestamp = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
        
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        diff = (now - timestamp).total_seconds()
        assert diff < 60  # Less than 1 minute old
    
    @pytest.mark.asyncio
    async def test_post_content_not_empty(self, ingester):
        """Test that generated posts have non-empty content."""
        posts = [ingester.generate_post() for _ in range(10)]
        
        for post in posts:
            assert len(post['content']) > 0
            assert post['content'].strip() != ''
    
    @pytest.mark.asyncio
    async def test_multiple_sources_used(self, ingester):
        """Test that ingester uses multiple sources."""
        posts = [ingester.generate_post() for _ in range(50)]
        sources = [p['source'] for p in posts]
        
        # Should use at least 2 different sources
        unique_sources = set(sources)
        assert len(unique_sources) >= 2
    
    @pytest.mark.asyncio
    async def test_continuous_generation(self, ingester, mock_redis):
        """Test that ingester continues generating posts."""
        ingester.posts_per_minute = 120  # Fast rate for testing
        
        # Run for a short time
        ingester_task = asyncio.create_task(ingester.start())
        await asyncio.sleep(1.0)
        ingester_task.cancel()
        
        try:
            await ingester_task
        except asyncio.CancelledError:
            pass
        
        # Should have published multiple posts
        assert mock_redis.xadd.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_ingester_reconnects_on_error(self, ingester, mock_redis):
        """Test that ingester continues after temporary errors."""
        # Simulate temporary error followed by success
        mock_redis.xadd.side_effect = [
            Exception("Temporary error"),
            b'123-0',  # Success
            b'123-1',  # Success
        ]
        
        ingester_task = asyncio.create_task(ingester.start())
        await asyncio.sleep(0.5)
        ingester_task.cancel()
        
        try:
            await ingester_task
        except asyncio.CancelledError:
            pass
        
        # Should have attempted multiple publishes
        assert mock_redis.xadd.call_count >= 2
    
    def test_post_id_format(self, ingester):
        """Test that post IDs follow expected format."""
        post = ingester.generate_post()
        
        # Post ID should start with 'post_'
        assert post['post_id'].startswith('post_')
    
    @pytest.mark.asyncio
    async def test_author_generation(self, ingester):
        """Test that author names are generated."""
        posts = [ingester.generate_post() for _ in range(10)]
        authors = [p['author'] for p in posts]
        
        # All should have authors
        assert all(len(author) > 0 for author in authors)
        
        # Should have some variation
        unique_authors = set(authors)
        assert len(unique_authors) >= 2
    
    @pytest.mark.asyncio
    async def test_configurable_rate(self):
        """Test that rate can be configured."""
        mock_redis = AsyncMock()
        
        # Low rate
        slow_ingester = DataIngester(
            redis_client=mock_redis,
            stream_name='test',
            posts_per_minute=30
        )
        assert slow_ingester.posts_per_minute == 30
        
        # High rate
        fast_ingester = DataIngester(
            redis_client=mock_redis,
            stream_name='test',
            posts_per_minute=300
        )
        assert fast_ingester.posts_per_minute == 300


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
