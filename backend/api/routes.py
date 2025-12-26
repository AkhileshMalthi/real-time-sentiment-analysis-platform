from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func, and_, text
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import os
import json
import redis.asyncio as aioredis

# Import models
from models.database import SocialMediaPost, SentimentAnalysis, SentimentAlert

# Import services
from services.aggregator import AggregatorService

router = APIRouter()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://sentiment_user:secure_password_123@localhost:5432/sentiment_db")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Redis setup
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Dependency to get Redis client
async def get_redis():
    redis_client = await aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
    try:
        yield redis_client
    finally:
        await redis_client.close()

@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db), redis_client = Depends(get_redis)):
    """
    Health check endpoint to verify database and Redis connectivity.
    """
    services_status = {"database": "disconnected", "redis": "disconnected"}
    stats = {"total_posts": 0, "total_analyses": 0, "recent_posts_1h": 0}
    
    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        services_status["database"] = "connected"
        
        # Get stats
        total_posts_result = await db.execute(select(func.count(SocialMediaPost.id)))
        stats["total_posts"] = total_posts_result.scalar() or 0
        
        total_analyses_result = await db.execute(select(func.count(SentimentAnalysis.id)))
        stats["total_analyses"] = total_analyses_result.scalar() or 0
        
        # Recent posts in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_posts_result = await db.execute(
            select(func.count(SocialMediaPost.id)).where(SocialMediaPost.ingested_at >= one_hour_ago)
        )
        stats["recent_posts_1h"] = recent_posts_result.scalar() or 0
    except Exception as e:
        print(f"Database health check failed: {e}")
    
    # Check Redis
    try:
        await redis_client.ping()
        services_status["redis"] = "connected"
    except Exception as e:
        print(f"Redis health check failed: {e}")
    
    # Determine overall status
    if services_status["database"] == "connected" and services_status["redis"] == "connected":
        overall_status = "healthy"
        status_code = status.HTTP_200_OK
    elif services_status["database"] == "connected" or services_status["redis"] == "connected":
        overall_status = "degraded"
        status_code = status.HTTP_200_OK
    else:
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services_status,
        "stats": stats
    }
    
    if overall_status == "unhealthy":
        raise HTTPException(status_code=status_code, detail=response)
    
    return response

@router.get("/api/posts")
async def get_posts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve social media posts with optional filters and pagination.

    Query Parameters:
        limit: Number of posts to return (default 50, max 100)
        offset: Number of posts to skip (default 0)
        source: Filter by social media platform (e.g., 'twitter', 'facebook')
        sentiment: Filter by sentiment label (e.g., 'positive', 'negative', 'neutral')
        start_date: Filter posts created after this date (ISO 8601 format)
        end_date: Filter posts created before this date (ISO 8601 format)
    Returns:
        {
            "posts": [...],
            "total": 100,
            "limit": 50,
            "offset": 0,
            "filters": {
                "source": "twitter",
                "sentiment": "positive",
                "start_date": "2025-01-14T10:00:00Z",
                "end_date": "2025-01-15T10:00:00Z"
            }
        }
    """
    # Build query with join
    query = select(SocialMediaPost, SentimentAnalysis).join(
        SentimentAnalysis,
        SocialMediaPost.post_id == SentimentAnalysis.post_id,
        isouter=True
    )
    
    # Apply filters
    conditions = []
    if source:
        conditions.append(SocialMediaPost.source == source)
    if sentiment:
        conditions.append(SentimentAnalysis.sentiment_label == sentiment)
    if start_date:
        conditions.append(SocialMediaPost.created_at >= start_date)
    if end_date:
        conditions.append(SocialMediaPost.created_at <= end_date)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count()).select_from(SocialMediaPost).join(
        SentimentAnalysis,
        SocialMediaPost.post_id == SentimentAnalysis.post_id,
        isouter=True
    )
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply ordering and pagination
    query = query.order_by(SocialMediaPost.created_at.desc()).limit(limit).offset(offset)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Format response
    posts = []
    for post, sentiment_data in rows:
        post_dict = {
            "post_id": post.post_id,
            "source": post.source,
            "content": post.content,
            "author": post.author,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "sentiment": None
        }
        
        if sentiment_data:
            post_dict["sentiment"] = {
                "label": sentiment_data.sentiment_label,
                "confidence": sentiment_data.confidence_score,
                "emotion": sentiment_data.emotion,
                "model_name": sentiment_data.model_name
            }
        
        posts.append(post_dict)
    
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "source": source,
            "sentiment": sentiment,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }

@router.get("/api/sentiment/aggregate")
async def get_sentiment_aggregate(
    period: str = Query(..., pattern="^(minute|hour|day)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get sentiment counts aggregated by time period
    
    Query Parameters:
        period: Aggregation granularity ('minute', 'hour', or 'day') [REQUIRED]
        start_date: Start of time range (default: 24 hours ago)
        end_date: End of time range (default: now)
        source: Filter by specific platform
    
    Returns:
        {
            "period": "hour",
            "start_date": "2025-01-14T10:00:00Z",
            "end_date": "2025-01-15T10:00:00Z",
            "data": [...],
            "summary": {...}
        }
    """
    # Delegate to aggregator service
    aggregator = AggregatorService(db, redis_client)
    return await aggregator.get_sentiment_aggregate(period, start_date, end_date, source)

@router.get("/api/sentiment/distribution")
async def get_sentiment_distribution(
    hours: int = Query(24, ge=1, le=168),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis)
):
    """
    Get current sentiment distribution for dashboard
    
    Query Parameters:
        hours: Look back period in hours (1-168, default 24)
        source: Filter by platform
    
    Returns:
        {
            "timeframe_hours": 24,
            "source": null,
            "distribution": {...},
            "total": 800,
            "percentages": {...},
            "top_emotions": {...},
            "cached": true,
            "cached_at": "2025-01-15T10:29:45Z"
        }
    """
    # Delegate to aggregator service
    aggregator = AggregatorService(db, redis_client)
    return await aggregator.get_sentiment_distribution(hours, source)
