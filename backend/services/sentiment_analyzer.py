import os
import asyncio
import httpx
import json
import re
import logging
from typing import Optional
from transformers import pipeline
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

def build_prompt(text: str, task: str) -> str:
    """Build structured prompt that requests JSON-only responses."""
    if not isinstance(text, str) or not isinstance(task, str):
        raise ValueError("Input text and task must be strings")
    
    if task == "sentiment":
        return f"""Analyze the sentiment of the following text and respond with ONLY a valid JSON object in this exact format:
{{"label": "positive|negative|neutral", "confidence": 0.85}}

Do not include any explanations, markdown formatting, or additional text. Only return the JSON object.

Text to analyze:
{text}"""
    elif task == "emotion":
        return f"""Identify the primary emotion in the following text and respond with ONLY a valid JSON object in this exact format:
{{"emotion": "joy|sadness|anger|fear|surprise|disgust|neutral", "confidence": 0.85}}

Do not include any explanations, markdown formatting, or additional text. Only return the JSON object.

Text to analyze:
{text}"""
    else:
        raise ValueError("Unknown task")

class SentimentAnalyzer:
    def __init__(self, model_type: str = 'local', model_name: Optional[str] = None):
        self.model_type = model_type
        self.device = -1  # CPU by default
        
        if self.model_type == 'local':
            # Sentiment Model
            s_model = model_name or os.getenv("HUGGINGFACE_MODEL", "distilbert-base-uncased-finetuned-sst-2-english")
            self.sentiment_pipe = pipeline("text-classification", model=s_model, device=self.device)
            
            # Emotion Model
            e_model = os.getenv("EMOTION_MODEL", "j-hartmann/emotion-english-distilroberta-base")
            self.emotion_pipe = pipeline("text-classification", model=e_model, device=self.device)
            
        else:
            self.api_key = os.getenv("EXTERNAL_LLM_API_KEY")
            self.api_url = "https://api.groq.com/openai/v1/chat/completions" # Default to Groq
            self.llm_model = os.getenv("EXTERNAL_LLM_MODEL", "llama-3.1-8b-instant")

    async def analyze_sentiment(self, text: str) -> dict:
        if not text:
            return {"sentiment_label": "neutral", "confidence_score": 0.0, "model_name": "none"}
        
        if not isinstance(text, str):
            raise ValueError("Input text must be a string")
        
        if self.model_type == 'local':
            result = self.sentiment_pipe(text[:512])[0]
            # Map labels to lowercase standard
            label = result['label'].lower()
            if label == 'positive' or label == 'negative':
                final_label = label
            else:
                final_label = 'neutral'
                
            return {
                'sentiment_label': final_label,
                'confidence_score': float(result['score']),
                'model_name': self.sentiment_pipe.model.config._name_or_path
            }
        else:
            return await self._analyze_external(text, "sentiment")

    async def analyze_emotion(self, text: str) -> dict:
        if not text: raise ValueError("Empty text")

        if not isinstance(text, str):
            raise ValueError("Input text must be a string")
        
        if len(text) < 10: return {"emotion": "neutral", "confidence_score": 1.0, "model_name": "rule-based"}

        if self.model_type == 'local':
            result = self.emotion_pipe(text[:512])[0]
            return {
                'emotion': result['label'].lower(),
                'confidence_score': float(result['score']),
                'model_name': self.emotion_pipe.model.config._name_or_path
            }
        else:
            return await self._analyze_external(text, "emotion")

    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON response, handling markdown formatting and edge cases."""
        # Remove markdown code blocks if present
        content = content.strip()
        
        # Handle ```json formatting
        if content.startswith("```"):
            # Extract content between ``` markers
            match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
            if match:
                content = match.group(1)
            else:
                # Try removing just the ``` markers
                content = re.sub(r'```(?:json)?', '', content).strip()
        
        # Parse the JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {content}")
            # Try to extract JSON object using regex as fallback
            match = re.search(r'{.*}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse JSON from response: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    async def _analyze_external(self, text: str, task: str) -> dict:
        """Call external LLM API (Groq/OpenAI) for sentiment or emotion analysis with retry logic."""
        if not self.api_key:
            raise ValueError("EXTERNAL_LLM_API_KEY not configured")
        
        if not isinstance(text, str):
            raise ValueError("Input text must be a string")
        
        prompt = build_prompt(text[:2000], task)  # Limit text length
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": "You are a precise text analysis assistant. Respond with only valid JSON objects as requested."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,  # Lower temperature for more consistent outputs
            "max_tokens": 100
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Extract the response text
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                logger.debug(f"External API raw response: {content}")
                
                # Parse JSON response carefully
                parsed = self._parse_json_response(content)
                logger.debug(f"Parsed JSON: {parsed}")

                # Normalize the response based on task
                if task == "sentiment":
                    label = parsed.get("label", "neutral").lower()
                    confidence = parsed.get("confidence", 0.85)
                    
                    # Validate label
                    if label not in ["positive", "negative", "neutral"]:
                        logger.warning(f"Invalid sentiment label '{label}', defaulting to 'neutral'")
                        label = "neutral"
                    
                    return {
                        'sentiment_label': label,
                        'confidence_score': float(confidence),
                        'model_name': self.llm_model
                    }
                
                elif task == "emotion":
                    emotion = parsed.get("emotion", "neutral").lower()
                    confidence = parsed.get("confidence", 0.85)
                    
                    # Validate emotion
                    valid_emotions = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]
                    if emotion not in valid_emotions:
                        logger.warning(f"Invalid emotion '{emotion}', defaulting to 'neutral'")
                        emotion = "neutral"
                    
                    return {
                        'emotion': emotion,
                        'confidence_score': float(confidence),
                        'model_name': self.llm_model
                    }
                
                else:
                    raise ValueError(f"Unknown task: {task}")
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling external API (attempt will retry): {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error calling external API (attempt will retry): {e}")
            raise
        except ValueError as e:
            # Don't retry on validation errors
            logger.error(f"Validation error in external analysis: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in external analysis: {e}")
            raise

    async def batch_analyze(self, texts: list[str]) -> list[dict]:
        if not texts: return []
        
        if not isinstance(texts, list):
            raise ValueError("Input must be a list of texts")
        
        if not all(isinstance(t, str) for t in texts):
            raise ValueError("All items in the input list must be strings")
        
        if self.model_type == 'local':
            # Local pipeline supports lists natively for batching
            results = self.sentiment_pipe(texts, batch_size=len(texts))
            return [{
                'sentiment_label': r['label'].lower(),
                'confidence_score': float(r['score']),
                'model_name': 'batch-local'
            } for r in results]
        else:
            return await asyncio.gather(*[self.analyze_sentiment(t) for t in texts])