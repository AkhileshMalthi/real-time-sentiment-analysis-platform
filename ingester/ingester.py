import asyncio
import os
import random
import logging
from datetime import datetime, timezone
from typing import Optional
from redis.asyncio import Redis, RedisError

# Configure logging as per functional requirements
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataIngester:
    """
    Publishes simulated social media posts to Redis Stream
    """
    
    def __init__(self, redis_client, stream_name: str, posts_per_minute: int = 60):
        self.redis = redis_client
        self.stream_name = stream_name
        self.posts_per_minute = posts_per_minute
        
        # Strategies defined in instructions
        self.products = ["iPhone 16", "Tesla Model 3", "ChatGPT", "Netflix", "Amazon Prime"]
        self.authors = ["tech_guru", "daily_vibe", "user_99", "reviewer_pro", "anonymous_user"]
        
        self.templates = {
            "positive": [
                "I absolutely love {product}!", 
                "This is amazing!", 
                "{product} exceeded my expectations!"
            ],
            "negative": [
                "Very disappointed with {product}", 
                "Terrible experience", 
                "Would not recommend {product}"
            ],
            "neutral": [
                "Just tried {product}", 
                "Received {product} today", 
                "Using {product} for the first time"
            ]
        }
    
    def generate_post(self) -> dict:
        """
        Generates realistic post with ~40% pos, ~30% neu, ~30% neg sentiment.
        """
        roll = random.random()
        if roll < 0.40:
            sentiment = "positive"
        elif roll < 0.70:
            sentiment = "neutral"
        else:
            sentiment = "negative"
            
        product = random.choice(self.products)
        content = random.choice(self.templates[sentiment]).format(product=product)
        
        # Required exact keys and format
        return {
            'post_id': f'post_{random.getrandbits(32)}',
            'source': random.choice(['reddit', 'twitter']),
            'content': content,
            'author': random.choice(self.authors),
            'created_at': datetime.now(timezone.utc).isoformat() + 'Z'
        }
    
    async def publish_post(self, post_data: dict) -> bool:
        """
        Must use XADD command and handle connection errors.
        """
        try:
            # XADD stream_name * key1 val1 key2 val2...
            # '*' tells Redis to generate the message ID
            await self.redis.xadd(self.stream_name, post_data)
            return True
        except RedisError as e:
            logger.error(f"Redis connection failure: {e}")
            return False
    
    async def start(self, duration_seconds: Optional[int] = None):
        """
        Main loop handling rate limiting and graceful shutdown.
        """
        start_time = datetime.now(timezone.utc)
        sleep_time = 60.0 / self.posts_per_minute
        
        try:
            while True:
                # Check duration if provided
                if duration_seconds:
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    if elapsed >= duration_seconds:
                        break
                
                post = self.generate_post()
                success = await self.publish_post(post)
                
                if success:
                    logger.info(f"Published post {post['post_id']} to {self.stream_name}")
                
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            logger.info("Ingester service shutting down...")
        except KeyboardInterrupt:
            logger.info("Manually stopped.")

async def run_service():
    # Environment variables from Phase 1.2
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    stream_name = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")
    
    # Initialize Async Redis Client
    client = Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    ingester = DataIngester(client, stream_name)
    await ingester.start()

if __name__ == "__main__":
    asyncio.run(run_service())