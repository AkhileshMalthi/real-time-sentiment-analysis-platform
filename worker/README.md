# Sentiment Analysis Worker

Background worker service that consumes posts from Redis Streams, performs sentiment and emotion analysis using machine learning models, and persists results to PostgreSQL.

## Overview

The worker is a critical component in the processing pipeline:

1. **Consumes** posts from Redis Streams using consumer groups
2. **Analyzes** sentiment (positive/negative/neutral) and emotion using ML models
3. **Persists** analysis results to PostgreSQL database
4. **Acknowledges** processed messages to Redis

Workers can be horizontally scaled to handle increased load, with Redis consumer groups ensuring each message is processed exactly once.

## Dependencies

Core dependencies (see [pyproject.toml](pyproject.toml) for full list):

- **Redis** (7.1.0+): Redis client for stream consumption
- **SQLAlchemy** (2.0.45+): Database ORM with async support
- **asyncpg** (0.31.0+): PostgreSQL async driver
- **Transformers** (4.30.0+): Hugging Face models for NLP
- **PyTorch** (2.0.0+): Deep learning framework (CPU version)
- **httpx** (0.24.0+): HTTP client for external API calls
- **tenacity** (9.1.2+): Retry logic for fault tolerance
- **python-dotenv** (1.0.0): Environment configuration

## Architecture

The worker implements a consumer group pattern:

```
Redis Stream (social_posts)
    |
    v
[Consumer Group: sentiment_workers]
    |
    +-- Worker 1 (PID: 1234)
    +-- Worker 2 (PID: 1235)
    +-- Worker N (PID: 123N)
    |
    v
PostgreSQL Database
```

Each worker:
- Reads batch of messages using `XREADGROUP`
- Processes messages concurrently using asyncio
- Stores results in database
- Acknowledges successful processing with `XACK`

## Configuration

Environment variables (set in `.env` or docker-compose):

```bash
# Database
DATABASE_URL=postgresql://sentiment_user:password@db:5432/sentiment_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_STREAM_NAME=social_posts
REDIS_CONSUMER_GROUP=sentiment_workers

# ML Model Configuration
MODEL_TYPE=local  # Use local Hugging Face models
# Optional: Configure fallback to external LLM
LLM_PROVIDER=groq
LLM_API_KEY=your_api_key_here
LLM_MODEL=llama-3.1-8b-instant
```

## Processing Pipeline

### Message Format

Workers consume messages with the following structure:

```json
{
  "post_id": "post_123456",
  "source": "reddit",
  "content": "I absolutely love this product!",
  "author": "tech_guru",
  "created_at": "2025-12-27T10:30:00Z"
}
```

### Analysis Output

For each post, the worker generates:

**Sentiment Analysis**:
- Classification: `positive`, `negative`, or `neutral`
- Confidence score: 0.0 to 1.0

**Emotion Analysis**:
- Detected emotion: `joy`, `sadness`, `anger`, `fear`, `surprise`, or `neutral`
- Confidence score: 0.0 to 1.0

### Database Storage

Results are stored in two tables:

**social_media_posts**: Original post data
**sentiment_analysis**: Analysis results with foreign key to post

## Scaling

Workers support horizontal scaling for increased throughput:

```bash
# Scale to 3 worker instances
docker-compose up -d --scale worker=3

# Verify running workers
docker-compose ps worker
```

Each worker instance:
- Has unique consumer name based on process ID
- Competes for messages from shared stream
- Processes different messages (no duplication)
- Can be added/removed dynamically

## ML Model Details

### Local Model (Primary)

- **Model**: `cardiffnlp/twitter-roberta-base-sentiment-latest`
- **Type**: RoBERTa-based transformer fine-tuned for sentiment
- **Inference Time**: ~100-200ms per post
- **Memory**: ~500MB model size
- **Lazy Loading**: Model loaded on first message to reduce startup time

### External LLM (Fallback)

When local model fails or is unavailable:
- Fallback to Groq/OpenAI/Anthropic APIs
- Implements exponential backoff retry logic
- Graceful degradation to ensure resilience

## Development

### Setup Local Environment

```bash
# Navigate to worker directory
cd worker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run worker
python worker.py
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests
pytest tests/

# Run with output
pytest tests/ -v
```

### Project Structure

```
worker/
├── worker.py          # Main worker class and entry point
├── processor.py       # Database persistence logic
├── tests/
│   └── test_worker.py # Worker unit tests
├── Dockerfile         # Container definition
├── pyproject.toml     # Dependencies and metadata
└── requirements.txt   # Frozen dependencies
```

## Docker Deployment

Build and run using Docker:

```bash
# Build image
docker build -t sentiment-worker .

# Run single worker
docker run \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_HOST=redis \
  sentiment-worker

# Run multiple workers
docker-compose up -d --scale worker=3
```

## Monitoring

### Logging

Workers output structured logs:

```
2025-12-27 10:30:15 - worker - INFO - Initializing SentimentAnalyzer...
2025-12-27 10:30:17 - worker - INFO - SentimentAnalyzer initialized successfully
2025-12-27 10:30:18 - worker - INFO - Processed message 1234-0
2025-12-27 10:30:19 - worker - ERROR - Error processing message: ...
```

### Key Metrics

Monitor these for worker health:
- Message processing rate (messages/second)
- Processing latency (time per message)
- Error rate and types
- Consumer group lag (pending messages)

### Redis Consumer Group Commands

```bash
# Check consumer group info
redis-cli XINFO GROUPS social_posts

# Check pending messages
redis-cli XPENDING social_posts sentiment_workers

# View consumer list
redis-cli XINFO CONSUMERS social_posts sentiment_workers
```

## Troubleshooting

**Worker Not Processing Messages**: Verify Redis connection and consumer group setup

**High Memory Usage**: PyTorch models require significant memory; allocate at least 1GB per worker

**Slow Processing**: Check model inference time; consider using external LLM API for faster throughput

**Message Duplication**: Ensure `XACK` is called after successful processing

**Consumer Group Errors**: Consumer group is auto-created on first run; check Redis permissions

## Performance

- Throughput: ~50-100 posts/second per worker (local model)
- Latency: ~100-200ms per post (model inference)
- Memory: ~500MB per worker (model loaded)
- CPU: High during inference; benefits from multi-core systems

## License

MIT License - See root [LICENSE](../LICENSE) file
