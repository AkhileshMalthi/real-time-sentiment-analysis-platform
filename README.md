# Real-Time Sentiment Analysis Platform

A production-grade, real-time sentiment analysis platform that processes social media posts, analyzes sentiment and emotions using AI models, and provides live visualization through a web dashboard.

![Platform Status](https://img.shields.io/badge/status-production--ready-success)
![Python](https://img.shields.io/badge/python-3.12-blue)
![React](https://img.shields.io/badge/react-18.2-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)

## 🌟 Features

- **Real-time Processing**: Analyze social media posts in real-time using Redis Streams
- **Dual AI Analysis**: Combine local Hugging Face models with external LLM APIs (Groq/OpenAI/Anthropic)
- **Live Dashboard**: React-based dashboard with WebSocket updates and interactive charts
- **Sentiment & Emotion Detection**: Classify sentiment (positive/negative/neutral) and detect 6 emotions
- **Intelligent Alerting**: Automated alerts when negative sentiment exceeds thresholds
- **Microservices Architecture**: 6 containerized services with Docker Compose orchestration
- **Production-Ready**: Comprehensive error handling, logging, and graceful degradation

## 📋 Prerequisites

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **API Key** for external LLM (Groq, OpenAI, or Anthropic) - [Get Groq API Key](https://console.groq.com/keys)
- **System Resources**: 4GB RAM minimum, 8GB recommended
- **Ports Available**: 3000 (frontend), 8000 (backend)

## 🚀 Quick Start

### 1. Clone and Configure

```bash
git clone <repository-url>
cd sentiment-analysis-platform

# Create environment file from template
cp .env.example .env

# Edit .env and add your API key
# Required: LLM_API_KEY=your_api_key_here
# Optional: Adjust other settings as needed
```

### 2. Start All Services

```bash
# Start all 6 services
docker-compose up -d

# Verify all services are running
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Access the Dashboard

Open your browser to **http://localhost:3000**

The dashboard will display:
- Real-time sentiment distribution (pie chart)
- Sentiment trends over time (line chart)
- Live post feed with sentiment badges
- Key metrics (total posts, positive/negative/neutral counts)

## Objective
Build a production-grade, real-time sentiment analysis platform that processes social media posts, analyzes sentiment and emotions using AI models, and provides live visualization through a web dashboard. This capstone project demonstrates mastery of full-stack AI engineering, including microservices architecture, message queue systems, real-time data processing, and modern web development

## Key Learning Outcomes:

- Design and implement a distributed system with multiple containerized services
- Integrate AI/ML models (both local and cloud-based) into production workflows
- Build real-time data pipelines using message queues (Redis Streams)
- Create responsive web dashboards with live updates via WebSocket
- Write comprehensive tests and documentation for production systems
- Deploy and orchestrate services using Docker Compose

### Business Context:
This platform simulates real-world systems used by companies to monitor brand reputation, track customer sentiment on social media, and respond quickly to negative feedback. The system must handle continuous data streams, provide accurate sentiment analysis, and deliver insights through an intuitive dashboard.

## Core Requirements

### 1. Technology Stack Requirements

#### Core Requirements (Mandatory - No Substitutions):
- **Message Queue**: Redis 7+ using Redis Streams (required for consumer groups, XACK, message persistence)
- **AI/ML**: Hugging Face Transformers library + one external LLM API (Groq, OpenAI, or Anthropic)
- **Containerization**: Docker with Docker Compose for orchestration
- **Architecture**: Exactly 6 containerized services (Database, Message Queue, Ingester, Worker, Backend API, Frontend)

#### Flexible Requirements (Choose one per category):

##### Backend API Framework:

- **FastAPI** (Python 3.9+) - Recommended for Python developers
- **Flask** with async support (Python 3.9+)
- **Express.js** (Node.js 18+)
- **Spring Boot** (Java 17+)
- **Other**: Must support async operations, REST endpoints, and WebSocket

##### Database:

- **PostgreSQL** 15+ - Recommended
- **MySQL** 8.0+
- **MongoDB** 6.0+ (with schema validation)

##### Frontend Framework:

- **React** 18+ with Vite - Recommended
- **Vue** 3+ with Vite
- **Angular** 15+
- **SvelteKit**
- **Other**: Must support WebSocket client and charting libraries

##### Visualization Library:

- Any charting library (Recharts, Chart.js, D3.js, Plotly.js, etc.)

##### Testing Framework:

- **Backend**: Any testing framework (pytest, Jest, JUnit, etc.)
- **Frontend**: Optional, but recommended

### 2. System Architecture

- **Exactly 6 containerized services**: Database, Redis, Ingester, Worker, Backend API, Frontend
- **Services communicate via**: Database connections, Redis Streams, HTTP/WebSocket
- **Zero-configuration startup**: System must work immediately after `docker-compose up -d`
- **Auto-initialization**: Database schema, Redis consumer groups, and all dependencies must be created automatically on startup
- **Port requirements**: Frontend accessible on port 3000, Backend API on port 8000

### 3. Functional Requirements

- **Data Ingestion**: Generate and publish realistic social media posts to Redis Stream at configurable rates
- **Sentiment Analysis**: Analyze posts using both local (`Hugging Face`) and external LLM models
- **Emotion Detection**: Identify emotions (joy, anger, sadness, fear, surprise, neutral) in posts
- **Data Storage**: Persist posts and analysis results in database (`PostgreSQL`/`MySQL`/`MongoDB`) with proper relationships
- **REST API**: Provide endpoints for health checks, post retrieval, sentiment aggregation, and distribution
- **WebSocket**: Broadcast real-time updates for new posts and periodic metrics
- **Alerting**: Monitor sentiment trends and trigger alerts when negative ratio exceeds thresholds
- **Dashboard**: Display sentiment distribution, trends over time, and live post feed

### 4. Data Model Requirements

- Three database tables/collections: `social_media_posts`, `sentiment_analysis`, `sentiment_alerts`
- Proper relationships (foreign keys for SQL, validation for NoSQL) and indexes on frequently queried columns/fields
- Support for filtering by source, sentiment, date ranges

### 5. Quality Requirements

- Test coverage ≥70% for backend code
- Comprehensive documentation: `README.md` and `ARCHITECTURE.md`
- Error handling for all external service connections
- Graceful degradation when services are unavailable
- **Performance**: Process ≥2 messages/second in worker service

### 6. Submission Requirements

Complete source code in specified directory structure
Working `docker-compose.yml` that starts all services
`.env.example` with all configuration variables (no real secrets)
All tests passing with adequate coverage
Documentation that enables others to run the system from scratch


## Implementation Details

> Note on Automated Evaluation: This task is designed for automated evaluation. All requirements focus on functional correctness and standardized interfaces that can be programmatically tested. While you have flexibility in technology choices, you must provide the exact interfaces specified to ensure your submission can be evaluated automatically.

### Project Scope
Your system will analyze social media posts in real-time, determining whether each post expresses positive, negative, or neutral sentiment. The system will also detect specific emotions (joy, anger, sadness, etc.) and track sentiment trends over time.

**Example Use Case:** A company launching a new product wants to monitor social media reactions in real-time. Your platform ingests Reddit posts mentioning the product, analyzes sentiment using AI models, and displays live metrics showing whether reactions are mostly positive or negative, enabling the marketing team to respond quickly to issues.

### Technical Requirements & Constraints
#### Technology Stack Requirements
##### Core Requirements (Mandatory - No Substitutions):

These technologies are required for specific learning objectives and evaluation:

- **Message Queue**: Redis 7+ using Redis Streams

- **Required for:** Consumer groups, message acknowledgment (XACK), at-least-once delivery
- **Must use:** XADD, XREADGROUP, XACK commands
- **No substitutions:** Redis Streams is a core learning objective
- **AI/ML:** Hugging Face Transformers library + one external LLM API

- **Required models:** Sentiment analysis (e.g., distilbert-base-uncased-finetuned-sst-2-english)
- **Required models:** Emotion detection (e.g., j-hartmann/emotion-english-distilroberta-base)
- **External API:** Groq, OpenAI, or Anthropic
- **No substitutions:** Specific model interfaces are evaluated
- **Containerization:** Docker with Docker Compose
- **Required for:** Automated evaluation and deployment
- **Must support:** Health checks, service dependencies, environment variables

#### Flexible Requirements (Choose Based On Your Expertise):

##### Backend API Framework (Choose one):

- **FastAPI** (Python 3.9+) - Recommended for Python developers
- **Flask** with async support (Python 3.9+)
- **Express.js** (Node.js 18+)
- **Spring Boot** (Java 17+)
- **Other:** Must support async operations, REST, and WebSocket

##### Database (Choose one):

- **PostgreSQL** 15+ - Recommended
- **MySQL** 8.0+
- **MongoDB** 6.0+ (with schema validation)

##### Frontend Framework (Choose one):

- **React** 18+ with Vite - Recommended
- **Vue** 3+ with Vite
- **Angular** 15+
- **SvelteKit**
- **Other:** Must support WebSocket client and charting

##### Visualization Library (Any):

- Recharts, Chart.js, D3.js, Plotly.js, or any charting library

##### Testing Framework (Any):

- **Backend**: pytest, Jest, JUnit, or any testing framework
- **Frontend**: Optional but recommended

> Note: The entire system must work immediately after docker-compose up -d with NO manual database setup, migrations, or configuration. Auto-initialize everything on startup.

#### Interface Contracts (All Stacks Must Provide)
Regardless of technology choices, your system must provide these standardized interfaces:

##### REST API Endpoints:

- `GET /api/health` - Health check with service status
- `GET /api/posts` - Retrieve posts with pagination and filtering
- `GET /api/sentiment/aggregate` - Time-series aggregated sentiment data
- `GET /api/sentiment/distribution` - Current sentiment distribution

##### WebSocket:

`ws://localhost:8000/ws/sentiment` - Real-time sentiment updates
**Must send:** Connection confirmation, new post updates, periodic metrics

##### Database Schema:

- Table: `social_media_posts` (id, post_id, source, content, author, created_at, ingested_at)
- Table: `sentiment_analysis` (id, post_id, model_name, sentiment_label, confidence_score, emotion, analyzed_at)
- Table: `sentiment_alerts` (id, alert_type, threshold_value, actual_value, window_start, window_end, post_count, triggered_at, details)
**Must support:** Foreign keys, indexes, time-based queries

##### Frontend:

- Dashboard accessible at http://localhost:3000
- Must display: Sentiment distribution chart, sentiment trend chart, live post feed, metrics cards
- Must connect to WebSocket for real-time updates

##### System Architecture Requirements
Your platform must consist of exactly 6 containerized services:

1. **Database Service:** Stores all post data and analysis results (PostgreSQL/MySQL/MongoDB)
2. **Redis Service:** Manages message queues using Redis Streams and caches aggregated metrics
3. **Ingester Service:** Publishes posts to Redis Stream
4. **Worker Service:** Consumes posts from Redis Stream, runs AI analysis, stores results in database
5. **Backend API Service:** Serves data via REST endpoints and WebSocket
6. **Frontend Dashboard Service:** Web application for visualization

These services must communicate exclusively through:

- Database connections (Backend/Worker → Database)
- Redis Streams (Ingester → Redis → Worker)
- HTTP/WebSocket (Frontend → Backend)

##### Port Requirements:

- Frontend: Accessible on port 3000
- Backend API: Accessible on port 8000
- Database: Internal only (not exposed to host)
- Redis: Internal only (not exposed to host)

#### Project Structure Requirements
Your project structure should follow this general organization (adapt file names/extensions based on your chosen stack):

```bash
sentiment-platform/
├── docker-compose.yml          # Orchestrates all 6 services
├── .env.example               # Template with all required variables
├── README.md                  # Complete setup guide
├── ARCHITECTURE.md            # System design documentation
│
├── backend/                   # Backend API service
│   ├── Dockerfile
│   ├── [dependency-file]      # requirements.txt, package.json, pom.xml, etc.
│   ├── [main-entry]          # main.py, app.js, Application.java, etc.
│   ├── [config-file]         # config.py, config.js, application.properties, etc.
│   ├── api/                   # API route handlers
│   │   └── [routes-file]     # REST endpoints and WebSocket handler
│   ├── models/                # Database models/ORM
│   │   └── [models-file]     # database.py, models.js, entities/, etc.
│   ├── services/               # Business logic
│   │   ├── sentiment_analyzer.py  # Sentiment analysis service
│   │   ├── aggregator.py          # Data aggregation service
│   │   └── alerting.py            # Alert service
│   └── tests/                 # Test files
│       └── [test-files]      # test_api.*, test_sentiment.*, etc.
│
├── worker/                    # Worker service
│   ├── Dockerfile
│   ├── [dependency-file]
│   ├── worker.py              # Main worker loop (or worker.js, Worker.java, etc.)
│   └── processor.py           # Message processing logic
│
├── ingester/                  # Ingester service
│   ├── Dockerfile
│   ├── [dependency-file]
│   └── ingester.py            # Stream publisher
│
└── frontend/                  # Frontend dashboard
    ├── Dockerfile
    ├── [config-files]         # package.json, vite.config.js, angular.json, etc.
    ├── index.html
    └── src/                   # Source files (or app/, components/, etc.)
        ├── [main-entry]       # App.jsx, main.js, app.component.ts, etc.
        ├── components/         # React/Vue/Angular components
        │   ├── Dashboard.*
        │   ├── SentimentChart.*
        │   ├── DistributionChart.*
        │   └── LiveFeed.*
        └── services/
            └── api.*          # API client functions
```
Note: File names and extensions should match your chosen technology stack. The important part is that the functionality is organized logically and the services can be containerized.


