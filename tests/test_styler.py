"""
Test article style and writing style adjustment functionality
"""

import pytest
import asyncio
from open_deep_research.styler import styler_graph, convert_text, get_supported_tags
from open_deep_research.configuration import WorkflowConfiguration


class TestStyler:
    """Test article style adjustment functionality"""
    
    def test_supported_tags(self):
        """Test getting supported genre tags"""
        tags = get_supported_tags()
        assert isinstance(tags, list)
        assert "tweet" in tags
        assert len(tags) > 0
    
    @pytest.mark.asyncio
    async def test_tweet_conversion_basic(self):
        """Test basic Tweet conversion functionality"""
        # Test long text
        original_text = """
        Artificial intelligence technology has made tremendous progress in recent years, especially in natural language processing.
        Large language models like GPT-4 and Claude demonstrate amazing understanding and generation capabilities.
        These models can not only have conversations, but also perform complex reasoning tasks, code writing, creative writing, etc.
        However, the development of AI also brings some challenges, including data privacy, model bias, employment impact and other issues.
        We need to seriously consider these ethical and social issues while advancing technological development.
        """
        
        # Configuration
        config = {
            "configurable": {
                "writer_provider": "anthropic",
                "writer_model": "claude-3-haiku-20240307",
            }
        }
        
        # Prepare input
        input_data = {
            "original_text": original_text.strip(),
            "tag": "tweet",
            "custom_prompt": "",
            "reference_text": ""
        }
        
        # Execute conversion
        result = await styler_graph.ainvoke(input_data, config)
        
        # Verify results
        assert "styled_text" in result
        assert isinstance(result["styled_text"], str)
        assert len(result["styled_text"]) > 0
        # Tweet should be much shorter than original text
        assert len(result["styled_text"]) < len(original_text)
        
        print(f"Original length: {len(original_text)}")
        print(f"Tweet length: {len(result['styled_text'])}")
        print(f"Tweet content: {result['styled_text']}")
    
    @pytest.mark.asyncio
    async def test_tweet_with_reference_style(self):
        """Test Tweet conversion with reference style"""
        original_text = "Blockchain technology is a distributed ledger technology with characteristics of decentralization, immutability, and transparency."
        
        reference_text = """
        Just tried the new AI tool, so cool! 😍 
        This tech progress is really exciting, feels like the future is here ✨
        #AI #Tech #Future
        """
        
        config = {
            "configurable": {
                "writer_provider": "anthropic", 
                "writer_model": "claude-3-haiku-20240307",
            }
        }
        
        input_data = {
            "original_text": original_text,
            "tag": "tweet",
            "custom_prompt": "",
            "reference_text": reference_text
        }
        
        result = await styler_graph.ainvoke(input_data, config)
        
        assert "styled_text" in result
        assert isinstance(result["styled_text"], str)
        assert len(result["styled_text"]) > 0
        
        print(f"Reference style Tweet: {result['styled_text']}")
        
    @pytest.mark.asyncio 
    async def test_custom_prompt(self):
        """Test custom prompt functionality"""
        original_text = "Machine learning is a branch of artificial intelligence that enables computers to learn patterns from data through algorithms."
        
        custom_prompt = "Please use a very formal and academic tone, including specific technical terminology"
        
        config = {
            "configurable": {
                "writer_provider": "anthropic",
                "writer_model": "claude-3-haiku-20240307",
            }
        }
        
        input_data = {
            "original_text": original_text,
            "tag": "academic",
            "custom_prompt": custom_prompt,
            "reference_text": ""
        }
        
        result = await styler_graph.ainvoke(input_data, config)
        
        assert "styled_text" in result
        assert isinstance(result["styled_text"], str)
        assert len(result["styled_text"]) > 0
        
        print(f"Academic style conversion: {result['styled_text']}")
    
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test convenience function"""
        original_text = "The development speed of artificial intelligence is amazing."
        
        config = {
            "configurable": {
                "writer_provider": "anthropic",
                "writer_model": "claude-3-haiku-20240307",
            }
        }
        
        result = await convert_text(
            original_text=original_text,
            tag="tweet",
            config=config,
            custom_prompt="Make it very interesting and engaging",
            reference_text=""
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        
        print(f"Convenience function result: {result}")


if __name__ == "__main__":
    # Run basic test
    async def run_basic_test():
        test_instance = TestStyler()
        await test_instance.test_tweet_conversion_basic()
        
    asyncio.run(run_basic_test()) 