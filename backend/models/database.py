from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class SocialMediaPost(Base):
    __tablename__ = "social_media_posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(255), unique=True, index=True)
    source = Column(String(50), index=True)
    content = Column(Text)
    author = Column(String(255))
    created_at = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"
    id = Column(Integer, primary_key=True)
    post_id = Column(String(255), ForeignKey("social_media_posts.post_id"))
    model_name = Column(String(100))
    sentiment_label = Column(String(20)) # positive, negative, neutral
    confidence_score = Column(Float)
    emotion = Column(String(50), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class SentimentAlert(Base):
    __tablename__ = "sentiment_alerts"
    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50))
    threshold_value = Column(Float)
    actual_value = Column(Float)
    window_start = Column(DateTime(timezone=True))
    window_end = Column(DateTime(timezone=True))
    post_count = Column(Integer)
    triggered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    details = Column(JSON)