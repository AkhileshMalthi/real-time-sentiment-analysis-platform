# Backend API Service

FastAPI-based backend service that provides REST API endpoints and WebSocket connections for real-time sentiment analysis data access and monitoring.

## Overview

The backend service acts as the central API layer for the sentiment analysis platform, managing:

- REST API endpoints for querying sentiment data
- WebSocket connections for real-time dashboard updates
- PostgreSQL database interactions for data persistence
- Redis integration for real-time metrics and alerts
- ML model inference for sentiment and emotion analysis
- Automated alerting when negative sentiment thresholds are exceeded

## Dependencies

Core dependencies (see [pyproject.toml](pyproject.toml) for full list):

- **FastAPI** (0.127.0+): Modern web framework for building APIs
- **Uvicorn** (0.40.0+): ASGI server for serving FastAPI
- **SQLAlchemy** (2.0.45+): Database ORM with async support
- **asyncpg** (0.31.0+): PostgreSQL async driver
- **Redis** (7.1.0+): Redis client for streams and pub/sub
- **Transformers** (4.30.0+): Hugging Face models for sentiment analysis
- **PyTorch** (2.0.0+): Deep learning framework
- **websockets** (12.0+): WebSocket protocol implementation
- **python-dotenv** (1.0.0): Environment variable management

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

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# LLM API (for external model fallback)
LLM_PROVIDER=groq  # groq, openai, or anthropic
LLM_API_KEY=your_api_key_here
LLM_MODEL=llama-3.1-8b-instant

# Alert Settings
ALERT_THRESHOLD=0.4  # Alert when negative % exceeds 40%
ALERT_WINDOW_MINUTES=5
```

## API Endpoints

### REST API

**GET** `/api/metrics` - Retrieve aggregated sentiment metrics
- Returns: Distribution of positive/negative/neutral sentiment
- Query params: Optional time range filters

**GET** `/api/posts` - Fetch recent analyzed posts
- Returns: Paginated list of posts with sentiment scores
- Query params: `limit`, `offset`, `sentiment_filter`

**GET** `/api/alerts` - Get recent alerts
- Returns: List of triggered sentiment alerts
- Query params: `limit`, `since`

**GET** `/api/health` - Health check endpoint
- Returns: Service health status

### WebSocket

**WS** `/ws` - Real-time updates connection
- Pushes live metrics every 2 seconds
- Broadcasts new post analysis results
- Sends alert notifications

## Services

### Sentiment Analyzer (`services/sentiment_analyzer.py`)

Performs sentiment and emotion analysis using:
- Local Hugging Face models (cardiffnlp/twitter-roberta-base-sentiment-latest)
- External LLM APIs as fallback (Groq/OpenAI/Anthropic)
- Graceful degradation and retry logic

### Aggregator (`services/aggregator.py`)

Calculates real-time metrics from database:
- Sentiment distribution (positive/negative/neutral percentages)
- Emotion distribution across 6 categories
- Temporal aggregations

### Alerting (`services/alerting.py`)

Monitors sentiment trends and triggers alerts:
- Continuous monitoring of recent posts
- Threshold-based alert triggering
- Alert storage and retrieval

## Database Models

Defined in `models/database.py`:

**SocialMediaPost** - Stores original posts and metadata
- `id`, `post_id`, `source`, `content`, `author`, `created_at`

**SentimentAnalysis** - Stores analysis results
- `id`, `post_id` (FK), `sentiment`, `confidence`, `emotion`, `analyzed_at`

**Alert** - Stores triggered alerts
- `id`, `alert_type`, `message`, `severity`, `created_at`

## Development

### Setup Local Environment

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run database migrations
python init_db.py

# Start development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/unit/test_sentiment_analyzer.py
```

### Project Structure

```
backend/
├── api/
│   ├── routes.py        # REST API endpoints
│   └── websocket.py     # WebSocket handlers
├── models/
│   └── database.py      # SQLAlchemy models
├── services/
│   ├── sentiment_analyzer.py  # ML inference
│   ├── aggregator.py          # Metrics calculation
│   └── alerting.py            # Alert monitoring
├── tests/
│   ├── test_api.py
│   └── unit/
│       ├── test_sentiment_analyzer.py
│       ├── test_aggregator.py
│       └── test_alerting.py
├── main.py              # Application entry point
├── config.py            # Configuration management
├── init_db.py           # Database initialization
└── Dockerfile           # Container definition
```

## Docker Deployment

Build and run using Docker:

```bash
# Build image
docker build -t sentiment-backend .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_HOST=redis \
  -e LLM_API_KEY=... \
  sentiment-backend
```

Or use docker-compose from project root:

```bash
docker-compose up backend
```

## Troubleshooting

**Model Loading Issues**: Ensure sufficient memory (4GB+) and check Hugging Face model cache

**Database Connection Errors**: Verify `DATABASE_URL` format and database availability

**WebSocket Disconnections**: Check firewall settings and increase timeout values if needed

**High Memory Usage**: PyTorch models require significant memory; consider reducing batch sizes

## Performance

- Handles 100+ requests/second on standard hardware
- Local model inference: ~100-200ms per post
- WebSocket updates with sub-second latency
- Database queries optimized with proper indexing

## License

MIT License - See root [LICENSE](../LICENSE) file
