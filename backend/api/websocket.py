from datetime import datetime, timezone, timedelta
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func, and_
import asyncio
import os
import logging
from models.database import SocialMediaPost, SentimentAnalysis

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

router = APIRouter()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://sentiment_user:secure_password_123@localhost:5432/sentiment_db")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client {websocket.client} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client {websocket.client} disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.exception(f"Error sending to client: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

async def get_metrics_data():
    """
    Get sentiment metrics for different timeframes

    Returns:
        {
            "last_minute": {"positive": int, "negative": int, "neutral": int, "total": int},
            "last_hour": {"positive": int, "negative": int, "neutral": int, "total": int},
            "last_24_hours": {"positive": int, "negative": int, "neutral": int, "total": int
        }
    """
    async with AsyncSessionLocal() as db:
        metrics = {
            "last_minute": {"positive": 0, "negative": 0, "neutral": 0, "total": 0},
            "last_hour": {"positive": 0, "negative": 0, "neutral": 0, "total": 0},
            "last_24_hours": {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
        }
        
        now = datetime.now(timezone.utc)
        
        logger.info(f"Calculating sentiment metrics for timeframes up to {now.isoformat()}")

        timeframes = {
            "last_minute": now - timedelta(minutes=1),
            "last_hour": now - timedelta(hours=1),
            "last_24_hours": now - timedelta(hours=24)
        }
        
        for timeframe_key, threshold in timeframes.items():
            logger.debug(f"Querying sentiment counts for timeframe '{timeframe_key}' since {threshold.isoformat()}")
            query = select(
                SentimentAnalysis.sentiment_label,
                func.count(SentimentAnalysis.id).label('count')
            ).where(
                SentimentAnalysis.analyzed_at >= threshold
            ).group_by(SentimentAnalysis.sentiment_label)
            
            result = await db.execute(query)
            rows = result.all()
            logger.debug(f"Sentiment counts for timeframe '{timeframe_key}': {rows}")
            
            for row in rows:
                sentiment_label = row[0]
                count_value = row[1]
                metrics[timeframe_key][sentiment_label] = count_value
                metrics[timeframe_key]["total"] += count_value
        
        logger.info(f"Calculated metrics: {metrics}")
        return metrics

async def send_periodic_metrics():
    """Send metrics updates every 30 seconds to all connected clients"""
    while True:
        try:
            await asyncio.sleep(30)
            
            if len(manager.active_connections) > 0:
                metrics = await get_metrics_data()
                
                message = {
                    "type": "metrics_update",
                    "data": metrics,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                await manager.broadcast(message)
        except Exception as e:
            print(f"Error in periodic metrics: {e}")

async def monitor_new_posts():
    """Monitor database for new posts and broadcast them"""
    last_check = datetime.now(timezone.utc)
    
    while True:
        try:
            await asyncio.sleep(2)  # Check every 2 seconds
            
            # Check if there are any active connections
            if len(manager.active_connections) == 0:
                last_check = datetime.now(timezone.utc)
                continue # Skip if no clients connected
            
            async with AsyncSessionLocal() as db:
                # Query for new posts since last check
                query = select(SocialMediaPost, SentimentAnalysis).join(
                    SentimentAnalysis,
                    SocialMediaPost.post_id == SentimentAnalysis.post_id,
                    isouter=True
                ).where(
                    SocialMediaPost.ingested_at > last_check
                ).order_by(SocialMediaPost.ingested_at)
                
                result = await db.execute(query)
                rows = result.all()
                
                if rows:
                    logger.info(f"Found {len(rows)} new posts to broadcast")
                
                for post, sentiment_data in rows:
                    # Truncate content to first 100 characters
                    content_preview = post.content[:100] + "..." if len(post.content) > 100 else post.content
                    
                    message = {
                        "type": "new_post",
                        "data": {
                            "post_id": post.post_id,
                            "content": content_preview,
                            "source": post.source,
                            "author": post.author,
                            "created_at": post.created_at.isoformat() if post.created_at else datetime.now(timezone.utc).isoformat(),
                            "sentiment": {
                                "label": sentiment_data.sentiment_label if sentiment_data else None,
                                "confidence": sentiment_data.confidence_score if sentiment_data else None,
                                "emotion": sentiment_data.emotion if sentiment_data else None,
                                "model_name": sentiment_data.model_name if sentiment_data else None
                            }
                        }
                    }
                    
                    await manager.broadcast(message)
                
                last_check = datetime.now(timezone.utc)
        
        except Exception as e:
            print(f"Error monitoring new posts: {e}")
            await asyncio.sleep(5)

# WebSocket endpoint
@router.websocket("/ws/sentiment")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time sentiment updates"""
    await manager.connect(websocket)
    
    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "message": "Connected to sentiment stream",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    try:
        # Keep connection alive and listen for messages
        while True:
            # Wait for any messages from client (ping/pong, etc.)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)