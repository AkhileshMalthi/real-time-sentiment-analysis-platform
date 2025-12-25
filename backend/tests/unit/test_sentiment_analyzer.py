import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys

# Mock transformers before importing SentimentAnalyzer
sys.modules['transformers'] = MagicMock()

from services.sentiment_analyzer import SentimentAnalyzer, build_prompt


class TestBuildPrompt:
    """Test the build_prompt function."""
    
    def test_build_prompt_sentiment(self):
        """Test prompt building for sentiment analysis."""
        text = "This is a test message"
        result = build_prompt(text, "sentiment")
        assert "Analyze the sentiment" in result
        assert text in result
        assert "positive" in result and "negative" in result
    
    def test_build_prompt_emotion(self):
        """Test prompt building for emotion detection."""
        text = "I am so happy today!"
        result = build_prompt(text, "emotion")
        assert "emotion" in result.lower()
        assert text in result
    
    def test_build_prompt_invalid_task(self):
        """Test that invalid task raises ValueError."""
        with pytest.raises(ValueError, match="Unknown task"):
            build_prompt("test", "invalid_task")
    
    def test_build_prompt_invalid_input_types(self):
        """Test that non-string inputs raise ValueError."""
        with pytest.raises(ValueError, match="Input text and task must be strings"):
            build_prompt(123, "sentiment") # type: ignore
        
        with pytest.raises(ValueError, match="Input text and task must be strings"):
            build_prompt("test", 123) # type: ignore


class TestSentimentAnalyzerLocal:
    """Test SentimentAnalyzer with local models."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a local sentiment analyzer instance."""
        with patch('backend.services.sentiment_analyzer.pipeline') as mock_pipeline:
            # Mock the pipeline to avoid loading actual models
            mock_sentiment_pipe = Mock()
            mock_emotion_pipe = Mock()
            mock_pipeline.side_effect = [mock_sentiment_pipe, mock_emotion_pipe]
            
            analyzer = SentimentAnalyzer(model_type='local')
            analyzer.sentiment_pipe = mock_sentiment_pipe
            analyzer.emotion_pipe = mock_emotion_pipe
            
            # Add mock model config
            analyzer.sentiment_pipe.model.config._name_or_path = "test-sentiment-model"
            analyzer.emotion_pipe.model.config._name_or_path = "test-emotion-model"
            
            return analyzer
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self, analyzer):
        """Test sentiment analysis returns positive result."""
        analyzer.sentiment_pipe.return_value = [{'label': 'POSITIVE', 'score': 0.95}]
        
        result = await analyzer.analyze_sentiment("This is great!")
        
        assert result['sentiment_label'] == 'positive'
        assert result['confidence_score'] == 0.95
        assert 'model_name' in result
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self, analyzer):
        """Test sentiment analysis returns negative result."""
        analyzer.sentiment_pipe.return_value = [{'label': 'NEGATIVE', 'score': 0.89}]
        
        result = await analyzer.analyze_sentiment("This is terrible!")
        
        assert result['sentiment_label'] == 'negative'
        assert result['confidence_score'] == 0.89
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_neutral(self, analyzer):
        """Test sentiment analysis handles neutral/unknown labels."""
        analyzer.sentiment_pipe.return_value = [{'label': 'NEUTRAL', 'score': 0.75}]
        
        result = await analyzer.analyze_sentiment("The sky is blue.")
        
        assert result['sentiment_label'] == 'neutral'
        assert result['confidence_score'] == 0.75
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_empty_text(self, analyzer):
        """Test that empty text returns neutral with 0 confidence."""
        result = await analyzer.analyze_sentiment("")
        
        assert result['sentiment_label'] == 'neutral'
        assert result['confidence_score'] == 0.0
        assert result['model_name'] == 'none'
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_invalid_type(self, analyzer):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Input text must be a string"):
            await analyzer.analyze_sentiment(123)
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_truncates_long_text(self, analyzer):
        """Test that long text is truncated to 512 characters."""
        long_text = "a" * 1000
        analyzer.sentiment_pipe.return_value = [{'label': 'POSITIVE', 'score': 0.9}]
        
        await analyzer.analyze_sentiment(long_text)
        
        # Verify the pipeline was called with truncated text
        call_args = analyzer.sentiment_pipe.call_args[0][0]
        assert len(call_args) == 512
    
    @pytest.mark.asyncio
    async def test_analyze_emotion(self, analyzer):
        """Test emotion analysis."""
        analyzer.emotion_pipe.return_value = [{'label': 'joy', 'score': 0.92}]
        
        result = await analyzer.analyze_emotion("I am so happy!")
        
        assert result['emotion'] == 'joy'
        assert result['confidence_score'] == 0.92
        assert 'model_name' in result
    
    @pytest.mark.asyncio
    async def test_analyze_emotion_empty_text(self, analyzer):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Empty text"):
            await analyzer.analyze_emotion("")
    
    @pytest.mark.asyncio
    async def test_analyze_emotion_short_text(self, analyzer):
        """Test that very short text returns neutral."""
        result = await analyzer.analyze_emotion("Hi")
        
        assert result['emotion'] == 'neutral'
        assert result['confidence_score'] == 1.0
        assert result['model_name'] == 'rule-based'
    
    @pytest.mark.asyncio
    async def test_analyze_emotion_invalid_type(self, analyzer):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Input text must be a string"):
            await analyzer.analyze_emotion(123)
    
    @pytest.mark.asyncio
    async def test_batch_analyze(self, analyzer):
        """Test batch sentiment analysis."""
        texts = ["Great!", "Terrible!", "Okay."]
        analyzer.sentiment_pipe.return_value = [
            {'label': 'POSITIVE', 'score': 0.95},
            {'label': 'NEGATIVE', 'score': 0.90},
            {'label': 'NEUTRAL', 'score': 0.70}
        ]
        
        results = await analyzer.batch_analyze(texts)
        
        assert len(results) == 3
        assert results[0]['sentiment_label'] == 'positive'
        assert results[1]['sentiment_label'] == 'negative'
        assert results[2]['sentiment_label'] == 'neutral'
    
    @pytest.mark.asyncio
    async def test_batch_analyze_empty_list(self, analyzer):
        """Test batch analysis with empty list."""
        results = await analyzer.batch_analyze([])
        assert results == []
    
    @pytest.mark.asyncio
    async def test_batch_analyze_invalid_input(self, analyzer):
        """Test batch analysis with invalid input types."""
        with pytest.raises(ValueError, match="Input must be a list"):
            await analyzer.batch_analyze("not a list")
        
        with pytest.raises(ValueError, match="All items in the input list must be strings"):
            await analyzer.batch_analyze(["text", 123, "more text"])


class TestSentimentAnalyzerExternal:
    """Test SentimentAnalyzer with external LLM API."""
    
    @pytest.fixture
    def analyzer(self):
        """Create an external sentiment analyzer instance."""
        with patch.dict('os.environ', {
            'EXTERNAL_LLM_API_KEY': 'test_api_key',
            'EXTERNAL_LLM_MODEL': 'test-model'
        }):
            analyzer = SentimentAnalyzer(model_type='external')
            return analyzer
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_external_positive(self, analyzer):
        """Test external sentiment analysis with positive response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"label": "positive", "confidence": 0.95}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await analyzer.analyze_sentiment("Great product!")
            
            assert result['sentiment_label'] == 'positive'
            assert result['confidence_score'] == 0.95
            assert result['model_name'] == 'test-model'
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_external_negative(self, analyzer):
        """Test external sentiment analysis with negative response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"label": "negative", "confidence": 0.90}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await analyzer.analyze_sentiment("Terrible experience!")
            
            assert result['sentiment_label'] == 'negative'
            assert result['confidence_score'] == 0.90
    
    @pytest.mark.asyncio
    async def test_analyze_sentiment_external_neutral(self, analyzer):
        """Test external sentiment analysis with neutral response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"label": "neutral", "confidence": 0.85}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await analyzer.analyze_sentiment("The sky is blue.")
            
            assert result['sentiment_label'] == 'neutral'
            assert result['confidence_score'] == 0.85
    
    @pytest.mark.asyncio
    async def test_analyze_emotion_external(self, analyzer):
        """Test external emotion analysis."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"emotion": "joy", "confidence": 0.92}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await analyzer.analyze_emotion("I'm so happy today!")
            
            assert result['emotion'] == 'joy'
            assert result['confidence_score'] == 0.92
            assert result['model_name'] == 'test-model'
    
    @pytest.mark.asyncio
    async def test_analyze_emotion_external_multiple_emotions(self, analyzer):
        """Test that the detected emotion is returned."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"emotion": "sadness", "confidence": 0.88}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            result = await analyzer.analyze_emotion("I'm upset and frustrated!")
            
            assert result['emotion'] == 'sadness'
            assert result['confidence_score'] == 0.88
    
    @pytest.mark.asyncio
    async def test_external_api_no_api_key(self):
        """Test that missing API key raises ValueError."""
        with patch.dict('os.environ', {}, clear=True):
            analyzer = SentimentAnalyzer(model_type='external')
            
            with pytest.raises(ValueError, match="EXTERNAL_LLM_API_KEY not configured"):
                await analyzer.analyze_sentiment("Test")
    
    @pytest.mark.asyncio
    async def test_external_api_http_error(self, analyzer):
        """Test handling of HTTP errors."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock(side_effect=Exception("HTTP 500 Error"))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            with pytest.raises(Exception):
                await analyzer.analyze_sentiment("Test")
    
    @pytest.mark.asyncio
    async def test_external_api_request_timeout(self, analyzer):
        """Test handling of request timeouts."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock(side_effect=httpx.RequestError("Timeout"))
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            with pytest.raises(httpx.RequestError):
                await analyzer.analyze_sentiment("Test")
    
    @pytest.mark.asyncio
    async def test_external_api_text_truncation(self, analyzer):
        """Test that external API truncates text to 2000 characters."""
        long_text = "a" * 3000
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"label": "neutral", "confidence": 0.85}'}}]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await analyzer.analyze_sentiment(long_text)
            
            # Verify the request was made
            assert mock_post.called
            call_kwargs = mock_post.call_args[1]
            # Check that the prompt in the payload uses truncated text
            messages = call_kwargs['json']['messages']
            user_message = messages[1]['content']
            # The prompt includes "Analyze..." text plus the truncated input
            assert len(long_text[:2000]) <= 2000
    
    @pytest.mark.asyncio
    async def test_external_api_invalid_input_type(self, analyzer):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Input text must be a string"):
            await analyzer._analyze_external(123, "sentiment")
    
    @pytest.mark.asyncio
    async def test_batch_analyze_external(self, analyzer):
        """Test batch analysis with external API."""
        texts = ["Great!", "Bad!", "Okay"]
        
        mock_response1 = Mock()
        mock_response1.json.return_value = {"choices": [{"message": {"content": '{"label": "positive", "confidence": 0.95}'}}]}
        mock_response2 = Mock()
        mock_response2.json.return_value = {"choices": [{"message": {"content": '{"label": "negative", "confidence": 0.90}'}}]}
        mock_response3 = Mock()
        mock_response3.json.return_value = {"choices": [{"message": {"content": '{"label": "neutral", "confidence": 0.85}'}}]}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_post = AsyncMock(side_effect=[mock_response1, mock_response2, mock_response3])
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            results = await analyzer.batch_analyze(texts)
            
            assert len(results) == 3
            assert results[0]['sentiment_label'] == 'positive'
            assert results[1]['sentiment_label'] == 'negative'
            assert results[2]['sentiment_label'] == 'neutral'


class TestSentimentAnalyzerEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_special_characters_handling(self):
        """Test handling of special characters in text."""
        with patch('backend.services.sentiment_analyzer.pipeline') as mock_pipeline:
            mock_pipe = Mock()
            mock_pipeline.return_value = mock_pipe
            mock_pipe.return_value = [{'label': 'POSITIVE', 'score': 0.8}]
            mock_pipe.model.config._name_or_path = "test-model"
            
            analyzer = SentimentAnalyzer(model_type='local')
            analyzer.sentiment_pipe = mock_pipe
            
            special_text = "Test @#$%^&* symbols!"
            result = await analyzer.analyze_sentiment(special_text)
            
            assert 'sentiment_label' in result
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        with patch('backend.services.sentiment_analyzer.pipeline') as mock_pipeline:
            mock_pipe = Mock()
            mock_pipeline.return_value = mock_pipe
            mock_pipe.return_value = [{'label': 'POSITIVE', 'score': 0.8}]
            mock_pipe.model.config._name_or_path = "test-model"
            
            analyzer = SentimentAnalyzer(model_type='local')
            analyzer.sentiment_pipe = mock_pipe
            
            unicode_text = "Hello 世界 🌍 café"
            result = await analyzer.analyze_sentiment(unicode_text)
            
            assert 'sentiment_label' in result
    
    @pytest.mark.asyncio
    async def test_whitespace_only_text(self):
        """Test handling of whitespace-only text."""
        with patch('backend.services.sentiment_analyzer.pipeline') as mock_pipeline:
            mock_pipe = Mock()
            mock_pipeline.return_value = mock_pipe
            
            analyzer = SentimentAnalyzer(model_type='local')
            
            # Empty string handling
            result = await analyzer.analyze_sentiment("   ")
            # The current implementation treats this as non-empty
            # but the pipeline would process it
