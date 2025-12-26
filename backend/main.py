"""
Backend API Service - Main Entry Point

This module initializes the FastAPI application, sets up database connections,
mounts API routes and WebSocket endpoints, and handles application lifecycle events.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from models.database import Base

# Import routers
from api.routes import router as api_router
from api.websocket import router as ws_router

# Import alert service
from services.alerting import get_alert_service

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://sentiment_user:secure_password_123@db:5432/sentiment_db"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 Starting Sentiment Analysis Backend API...")
    
    # Initialize database tables
    try:
        logger.info("📊 Initializing database tables...")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        logger.info("✅ Database tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Start alert monitoring service in background
    alert_task = None
    ws_metrics_task = None
    ws_monitor_task = None
    try:
        logger.info("🚨 Starting alert monitoring service...")
        alert_service = await get_alert_service()
        alert_task = asyncio.create_task(alert_service.run_monitoring_loop())
        logger.info("✅ Alert monitoring service started")
        
        # Start WebSocket background tasks
        logger.info("🔌 Starting WebSocket monitoring tasks...")
        from api.websocket import send_periodic_metrics, monitor_new_posts
        ws_metrics_task = asyncio.create_task(send_periodic_metrics())
        ws_monitor_task = asyncio.create_task(monitor_new_posts())
        logger.info("✅ WebSocket monitoring tasks started")
    except Exception as e:
        logger.warning(f"⚠️  Background services failed to start: {e}")
    
    logger.info("✅ Backend API ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Backend API...")
    if alert_task:
        alert_task.cancel()
        try:
            await alert_task
        except asyncio.CancelledError:
            logger.info("✅ Alert monitoring service stopped")
    
    # Stop WebSocket tasks
    if ws_metrics_task:
        ws_metrics_task.cancel()
        try:
            await ws_metrics_task
        except asyncio.CancelledError:
            pass
    if ws_monitor_task:
        ws_monitor_task.cancel()
        try:
            await ws_monitor_task
        except asyncio.CancelledError:
            pass

# Create FastAPI application
app = FastAPI(
    title="Sentiment Analysis Platform API",
    description="Real-time sentiment analysis platform with AI/ML models",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration - Allow frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(api_router, tags=["API"])
app.include_router(ws_router, tags=["WebSocket"])

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "service": "Sentiment Analysis Backend API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "posts": "/api/posts",
            "sentiment_aggregate": "/api/sentiment/aggregate",
            "sentiment_distribution": "/api/sentiment/distribution",
            "websocket": "/ws/sentiment"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    
    logger.info(f"🌐 Starting server at http://{host}:{port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )