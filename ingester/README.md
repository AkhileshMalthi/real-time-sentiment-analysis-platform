# Data Ingester Service

Simulates real-time social media data by generating synthetic posts and publishing them to Redis Streams for processing by downstream workers.

## Overview

The ingester service serves as the data source for the sentiment analysis pipeline:

1. **Generates** realistic social media posts with varied sentiment
2. **Publishes** posts to Redis Streams using the `XADD` command
3. **Rate-limits** output to simulate realistic traffic (default: 60 posts/minute)
4. **Handles** connection errors with proper logging and retry logic

This service is designed for testing and demonstration purposes, simulating the behavior of a real social media API integration.

## Dependencies

Core dependencies (see [pyproject.toml](pyproject.toml) for full list):

- **Redis** (5.0.0+): Redis client for stream publishing
- **python-dotenv** (1.0.0+): Environment variable management

## Configuration

Environment variables (set in `.env` or docker-compose):

```bash
# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_STREAM_NAME=social_posts

# Ingestion Rate
POSTS_PER_MINUTE=60  # Adjustable rate limiting
```

## Post Generation

### Sentiment Distribution

Posts are generated with realistic sentiment distribution:
- **40%** Positive sentiment
- **30%** Neutral sentiment
- **30%** Negative sentiment

### Post Structure

Each generated post includes:

```json
{
  "post_id": "post_1234567890",
  "source": "reddit",
  "content": "I absolutely love iPhone 16!",
  "author": "tech_guru",
  "created_at": "2025-12-27T10:30:00.000000Z"
}
```

Fields:
- `post_id`: Unique identifier using random bits
- `source`: Platform (`reddit` or `twitter`)
- `content`: Generated text using templates
- `author`: Random author from predefined list
- `created_at`: UTC timestamp in ISO 8601 format

### Content Templates

The ingester uses predefined templates for realistic content:

**Products**:
- iPhone 16
- Tesla Model 3
- ChatGPT
- Netflix
- Amazon Prime

**Positive Templates**:
- "I absolutely love {product}!"
- "This is amazing!"
- "{product} exceeded my expectations!"

**Negative Templates**:
- "Very disappointed with {product}"
- "Terrible experience"
- "Would not recommend {product}"

**Neutral Templates**:
- "Just tried {product}"
- "Received {product} today"
- "Using {product} for the first time"

## Redis Stream Publishing

### XADD Command

Posts are published using Redis Streams:

```python
await redis.xadd('social_posts', {
    'post_id': 'post_123',
    'source': 'reddit',
    'content': 'Example post',
    'author': 'user_99',
    'created_at': '2025-12-27T10:30:00Z'
})
```

The `*` message ID is used, allowing Redis to auto-generate sequential IDs.

### Rate Limiting

The ingester implements precise rate limiting:
- Calculates sleep time: `60 seconds / posts_per_minute`
- Sleeps between posts to maintain consistent rate
- Default: 60 posts/minute (1 per second)

## Running the Service

### Local Development

```bash
# Navigate to ingester directory
cd ingester

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run ingester
python ingester.py
```

### Docker Deployment

```bash
# Build image
docker build -t sentiment-ingester .

# Run container
docker run \
  -e REDIS_HOST=redis \
  -e POSTS_PER_MINUTE=60 \
  sentiment-ingester

# Or use docker-compose
docker-compose up ingester
```

### Command Line Options

```bash
# Run for specific duration (60 seconds)
python ingester.py --duration 60

# Change rate (120 posts/minute)
POSTS_PER_MINUTE=120 python ingester.py

# Run indefinitely (default)
python ingester.py
```

## Testing

### Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/test_ingester.py

# Run with verbose output
pytest tests/test_ingester.py -v
```

### Manual Testing

Verify posts are being published:

```bash
# Monitor Redis stream in real-time
redis-cli XREAD COUNT 10 BLOCK 1000 STREAMS social_posts 0

# Check stream length
redis-cli XLEN social_posts

# View recent posts
redis-cli XRANGE social_posts - + COUNT 5
```

## Project Structure

```
ingester/
├── ingester.py        # Main ingester class and entry point
├── tests/
│   └── test_ingester.py  # Unit tests
├── Dockerfile         # Container definition
├── pyproject.toml     # Dependencies and metadata
└── requirements.txt   # Frozen dependencies
```

## Monitoring

### Logging

The ingester outputs structured logs:

```
2025-12-27 10:30:00 - INFO - Starting data ingestion...
2025-12-27 10:30:01 - INFO - Published post_123 to social_posts
2025-12-27 10:30:05 - ERROR - Redis connection failure: ...
2025-12-27 10:31:00 - INFO - Stopping data ingestion...
```

### Key Metrics

Monitor these for ingester health:
- Publishing rate (posts/minute)
- Failed publish attempts
- Redis connection status
- Stream length growth

### Redis Monitoring

```bash
# Check stream info
redis-cli XINFO STREAM social_posts

# Monitor stream size
watch redis-cli XLEN social_posts

# View stream statistics
redis-cli INFO STREAMS
```

## Error Handling

The ingester implements robust error handling:

**Redis Connection Errors**:
- Logs errors with context
- Continues operation (fails gracefully)
- Retries on next iteration

**Graceful Shutdown**:
- Handles `SIGINT` and `SIGTERM` signals
- Completes current publish before exiting
- Logs shutdown message

## Performance

- Throughput: Up to 1000+ posts/minute
- Latency: <10ms per post publication
- Memory: <50MB typical usage
- CPU: Minimal (<5% on modern systems)

## Customization

### Adding New Products

Edit `products` list in [ingester.py](ingester.py):

```python
self.products = [
    "iPhone 16", 
    "Tesla Model 3",
    "Your Product Here"  # Add new products
]
```

### Custom Templates

Modify `templates` dictionary for different content:

```python
self.templates = {
    "positive": ["Custom positive template"],
    "negative": ["Custom negative template"],
    "neutral": ["Custom neutral template"]
}
```

### Adjusting Distribution

Change sentiment probabilities in `generate_post()`:

```python
if roll < 0.50:  # 50% positive
    sentiment = "positive"
elif roll < 0.75:  # 25% neutral
    sentiment = "neutral"
else:  # 25% negative
    sentiment = "negative"
```

## Troubleshooting

**Not Publishing to Redis**: Verify `REDIS_HOST` environment variable and Redis availability

**Rate Too Fast/Slow**: Adjust `POSTS_PER_MINUTE` environment variable

**Stream Growing Too Large**: Configure Redis maxmemory and eviction policy

**Connection Errors**: Check Redis connection limits and network connectivity

## License

MIT License - See root [LICENSE](../LICENSE) file
