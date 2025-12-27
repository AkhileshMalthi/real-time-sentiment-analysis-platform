# Real-Time Sentiment Analysis Platform

A production-grade distributed system for real-time sentiment analysis of social media content. The platform processes streaming data, performs AI-powered sentiment and emotion classification, and delivers insights through a live web dashboard with sub-second latency.

![Platform Status](https://img.shields.io/badge/status-production--ready-success)
![Python](https://img.shields.io/badge/python-3.12-blue)
![React](https://img.shields.io/badge/react-18.2-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

## Overview

This platform implements a microservices architecture for analyzing sentiment in social media posts at scale. It combines event-driven processing with machine learning inference to provide real-time insights into content sentiment and emotional tone.

### Core Capabilities

- **Real-time Stream Processing**: Message queue-based architecture using Redis Streams for at-least-once delivery semantics
- **Hybrid AI Analysis**: Local Hugging Face transformer models with fallback to external LLM providers (Groq, OpenAI, Anthropic)
- **Live Dashboard**: React-based web interface with WebSocket-driven updates and interactive data visualization
- **Multi-label Classification**: Sentiment categorization (positive, negative, neutral) and emotion detection across six categories
- **Automated Alerting**: Threshold-based monitoring with configurable alert triggers for sentiment anomalies
- **Microservices Design**: Six independently scalable containerized services orchestrated via Docker Compose
- **Production Hardening**: Comprehensive error handling, structured logging, health checks, and graceful degradation

### Architecture Documentation

For detailed technical documentation including system architecture, data flow diagrams, database schema, API specifications, deployment strategies, and scalability considerations, please refer to [ARCHITECTURE.md](ARCHITECTURE.md).

## System Requirements

### Software Dependencies

- Docker Engine 20.10 or higher
- Docker Compose 2.0 or higher
- LLM API key from one of the supported providers:
  - Groq (recommended for development) - [Get API Key](https://console.groq.com/keys)
  - OpenAI - [Get API Key](https://platform.openai.com/api-keys)
  - Anthropic - [Get API Key](https://console.anthropic.com/)

### Hardware Requirements

- **Minimum**: 4GB RAM, 2 CPU cores, 10GB disk space
- **Recommended**: 8GB RAM, 4 CPU cores, 20GB disk space
- **Network**: Ports 3000 (frontend) and 8000 (backend) must be available

## Getting Started

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sentiment-analysis-platform
   ```

2. **Configure environment**
   ```bash
   # Create environment file from template
   cp .env.example .env
   
   # Edit .env and configure required settings
   # Required: LLM_API_KEY=your_api_key_here
   # Optional: Adjust SERVICE_* variables as needed
   ```

3. **Launch services**
   ```bash
   # Start all containerized services
   docker-compose up -d
   
   # Verify service health
   docker-compose ps
   
   # Monitor service logs
   docker-compose logs -f
   ```

4. **Access the application**
   
   Open your browser and navigate to `http://localhost:3000`
   
   The dashboard provides:
   - Real-time sentiment distribution visualization (pie chart)
   - Temporal sentiment trend analysis (line chart)
   - Live-updating post feed with sentiment classification
   - Aggregate metrics dashboard

## Architecture

The platform implements a distributed microservices architecture with the following components:

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                    Port: 3000      │
│  - WebSocket client for real-time updates                   │
│  - Interactive data visualization (Recharts)                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────▼────────────────────────────────────┐
│  Backend API (FastAPI)                      Port: 8000      │
│  - REST endpoints for data access                           │
│  - WebSocket server for live updates                        │
│  - Aggregation and caching layer                            │
└───────┬─────────────────────────────────────────┬───────────┘
        │                                         │
┌───────▼─────────────────────┐   ┌──────────────▼──────────┐
│  Redis (v7)                 │   │  PostgreSQL (v15)       │
│  - Stream-based queue       │   │  - Persistent storage   │
│  - L1 cache layer           │   │  - Relational schema    │
└───────▲─────────────────────┘   └─────────────────────────┘
        │
┌───────┴─────────────────────┐
│  Worker (Python)            │
│  - ML model inference       │
│  - Consumer group processor │
└─────────────────────────────┘
        ▲
┌───────┴─────────────────────┐
│  Ingester (Python)          │
│  - Stream publisher         │
│  - Rate-limited data source │
└─────────────────────────────┘
```

### Component Overview

| Component | Technology Stack | Purpose | Scaling Strategy |
|-----------|-----------------|---------|------------------|
| **Frontend** | React 18, Vite, Recharts | User interface and visualization | Horizontal (CDN/load balancer) |
| **Backend** | FastAPI, Python 3.12 | API gateway and business logic | Horizontal (stateless) |
| **Database** | PostgreSQL 15 | Persistent data storage | Vertical + read replicas |
| **Cache/Queue** | Redis 7 | Message streaming and caching | Horizontal (cluster mode) |
| **Worker** | Python 3.12, PyTorch | ML inference and processing | Horizontal (consumer groups) |
| **Ingester** | Python 3.12 | Data generation/ingestion | Horizontal (partitioned) |

For comprehensive architecture documentation including data flow diagrams, database schema, API specifications, caching strategies, and deployment patterns, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

## Data Processing Pipeline

The system implements an event-driven processing pipeline:

1. **Ingestion**: Ingester publishes messages to Redis Stream (`sentiment_stream`) using `XADD`
2. **Queueing**: Redis Streams maintains message ordering and enables consumer group semantics
3. **Processing**: Worker consumes messages via `XREADGROUP`, performs ML inference, stores results
4. **Aggregation**: Backend queries database, caches aggregates in Redis with 60s TTL
5. **Distribution**: WebSocket server broadcasts updates to connected clients in real-time

## Machine Learning Models

### Model Selection Strategy

The platform implements a hybrid approach for maximum reliability and performance:

**Primary (Local Models)**
- Sentiment: `distilbert-base-uncased-finetuned-sst-2-english`
- Emotion: `j-hartmann/emotion-english-distilroberta-base`
- Benefits: Low latency (~100-200ms), no API costs, offline operation
- Drawbacks: Fixed model capabilities, higher memory usage

**Fallback (External LLM APIs)**
- Providers: Groq, OpenAI, Anthropic
- Configuration: `LLM_PROVIDER` and `LLM_API_KEY` environment variables
- Benefits: High accuracy, continuously improving models
- Drawbacks: API costs, network dependency, higher latency

The system automatically attempts local inference first, falling back to external APIs on failure or when local models are unavailable.

For detailed model architecture, performance benchmarks, and configuration options, see the [AI/ML Integration](ARCHITECTURE.md#aiml-integration) section in ARCHITECTURE.md.

## Development

### Local Development Setup

**Backend Service**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
python init_db.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Service**
```bash
cd frontend
npm install
npm run dev
```

**Required Infrastructure**
```bash
# PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=sentiment_user \
  -e POSTGRES_PASSWORD=secure_password_123 \
  -e POSTGRES_DB=sentiment_db \
  postgres:15

# Redis
docker run -d -p 6379:6379 redis:7
```

### Service-Specific Documentation

Each service maintains detailed documentation in its respective directory:

- [Backend API Documentation](backend/README.md) - REST endpoints, WebSocket protocol, database models
- [Worker Documentation](worker/README.md) - Processing logic, consumer groups, scaling strategies  
- [Ingester Documentation](ingester/README.md) - Data generation, stream publishing, rate limiting

## Testing

The platform includes comprehensive test coverage across all services:

```bash
# Backend unit and integration tests
cd backend
pytest tests/ -v --cov=.

# Worker processing tests
cd worker
pytest tests/ -v

# Ingester stream publishing tests
cd ingester
pytest tests/ -v
```

For CI/CD integration, test coverage requirements, and testing strategies, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Monitoring and Operations

### Health Checks

The backend exposes a health endpoint for monitoring:

```bash
curl http://localhost:8000/api/health
```

Response includes database connectivity, Redis availability, and overall system status.

### Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# With timestamps
docker-compose logs -f --timestamps
```

### Scaling Operations

```bash
# Scale worker instances for increased throughput
docker-compose up -d --scale worker=3

# Verify scaling
docker-compose ps worker
```

For production deployment, monitoring setup, alerting configuration, and auto-scaling strategies, refer to the [Deployment Architecture](ARCHITECTURE.md#deployment-architecture) section in ARCHITECTURE.md.

## Troubleshooting

### Common Issues

**Database Connection Failures**
- Verify `DATABASE_URL` environment variable format
- Check PostgreSQL container health: `docker-compose ps db`
- Validate credentials and database existence

**WebSocket Disconnections**
- Check backend logs for `ConnectionManager` errors
- Verify Redis connectivity from backend container
- Review client-side reconnection logic

**High Memory Usage**
- PyTorch models require 500MB+ per worker instance
- Scale vertically or reduce worker replica count
- Consider using external LLM APIs instead of local models

**Model Loading Errors**
- Ensure sufficient disk space for Hugging Face model cache
- Verify network connectivity for initial model downloads
- Check Hugging Face API status if downloads fail

For additional troubleshooting guidance and performance tuning recommendations, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Performance Characteristics

- **Throughput**: 50-100 posts/second per worker instance
- **Latency**: Sub-200ms for local model inference, 500-1000ms for external LLM
- **WebSocket Update Frequency**: 2-second intervals for metrics, real-time for new posts
- **Cache Hit Ratio**: >80% for aggregate queries with 60s TTL

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) - Comprehensive technical architecture documentation
- [Backend API Documentation](backend/README.md) - Backend service details
- [Worker Documentation](worker/README.md) - Worker service implementation
- [Ingester Documentation](ingester/README.md) - Ingester service specifications

