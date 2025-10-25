"""
Test suite for TweepyTwitterClient functionality.
Tests search, like, and reply operations.
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock
from dotenv import load_dotenv
load_dotenv()  # Loads variables from .env file


# Add the parent directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tweepy_client import TweepyTwitterClient, Tweet, SearchResult

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


class TestTweepyTwitterClient:
    """Test cases for TweepyTwitterClient."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock credentials for testing
        self.test_credentials = {
            'bearer_token': 'test_bearer_token',
            'user_id': 'test_user_id',
            'api_key': 'test_api_key',
            'api_secret': 'test_api_secret',
            'access_token': 'test_access_token',
            'access_token_secret': 'test_access_token_secret'
        }
        
        # Create client instance
        self.client = TweepyTwitterClient(**self.test_credentials)
    
    def test_client_initialization(self):
        """Test that the client initializes properly."""
        assert self.client.bearer_token == 'test_bearer_token'
        assert self.client.user_id == 'test_user_id'
        assert self.client.api_key == 'test_api_key'
        assert self.client.api_secret == 'test_api_secret'
        assert self.client.access_token == 'test_access_token'
        assert self.client.access_token_secret == 'test_access_token_secret'
    
    @patch('tweepy.Client')
    def test_search_tweets_success(self, mock_client_class):
        """Test successful tweet search."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock tweet data
        mock_tweet_data = Mock()
        mock_tweet_data.id = '123456789'
        mock_tweet_data.text = 'Test tweet about AI'
        mock_tweet_data.author_id = '987654321'
        mock_tweet_data.conversation_id = '123456789'
        mock_tweet_data.created_at = Mock()
        mock_tweet_data.created_at.isoformat.return_value = '2024-01-01T12:00:00Z'
        mock_tweet_data.public_metrics = {'like_count': 10, 'retweet_count': 5}
        
        # Mock response
        mock_response = Mock()
        mock_response.data = [mock_tweet_data]
        mock_response.meta = {'next_token': 'next_page_token'}
        mock_client.search_recent_tweets.return_value = mock_response
        
        # Initialize client with mocked client
        self.client.client_v2 = mock_client
        
        # Test search
        result = self.client.search_tweets('AI', max_results=10)
        
        # Assertions
        assert isinstance(result, SearchResult)
        assert len(result.tweets) == 1
        assert result.total_count == 1
        assert result.next_token == 'next_page_token'
        
        tweet = result.tweets[0]
        assert tweet.id == '123456789'
        assert tweet.text == 'Test tweet about AI'
        assert tweet.author_id == '987654321'
        assert tweet.conversation_id == '123456789'
        assert tweet.created_at == '2024-01-01T12:00:00Z'
        assert tweet.public_metrics == {'like_count': 10, 'retweet_count': 5}
        
        # Verify API call
        mock_client.search_recent_tweets.assert_called_once_with(
            query='AI',
            max_results=10,
            next_token=None,
            tweet_fields=['conversation_id', 'author_id', 'created_at', 'public_metrics']
        )
    
    @patch('tweepy.Client')
    def test_search_tweets_no_client(self, mock_client_class):
        """Test search when client is not initialized."""
        self.client.client_v2 = None
        
        result = self.client.search_tweets('AI')
        
        assert isinstance(result, SearchResult)
        assert len(result.tweets) == 0
        assert result.total_count == 0
        assert result.next_token is None
    
    @patch('tweepy.Client')
    def test_like_tweet_success(self, mock_client_class):
        """Test successful tweet like."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.data = {'liked': True}
        mock_client.like.return_value = mock_response
        
        # Initialize client with mocked client
        self.client.client_v2 = mock_client
        
        # Test like
        result = self.client.like_tweet('123456789')
        
        # Assertions
        assert result is True
        
        # Verify API call
        mock_client.like.assert_called_once_with(
            tweet_id='123456789',
            user_id='test_user_id'
        )
    
    @patch('tweepy.Client')
    def test_like_tweet_failure(self, mock_client_class):
        """Test failed tweet like."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock response indicating failure
        mock_response = Mock()
        mock_response.data = {'liked': False}
        mock_client.like.return_value = mock_response
        
        # Initialize client with mocked client
        self.client.client_v2 = mock_client
        
        # Test like
        result = self.client.like_tweet('123456789')
        
        # Assertions
        assert result is False
    
    @patch('tweepy.Client')
    def test_like_tweet_no_client(self, mock_client_class):
        """Test like when client is not initialized."""
        self.client.client_v2 = None
        
        result = self.client.like_tweet('123456789')
        
        assert result is False
    
    @patch('tweepy.Client')
    def test_like_tweet_no_user_id(self, mock_client_class):
        """Test like when user ID is not configured."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        self.client.client_v2 = mock_client
        self.client.user_id = None
        
        result = self.client.like_tweet('123456789')
        
        assert result is False
    
    @patch('tweepy.Client')
    def test_reply_to_tweet_success(self, mock_client_class):
        """Test successful tweet reply."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.data = {'id': '987654321'}
        mock_client.create_tweet.return_value = mock_response
        
        # Initialize client with mocked client
        self.client.client_v2 = mock_client
        
        # Test reply
        result = self.client.reply_to_tweet('123456789', 'Great tweet!')
        
        # Assertions
        assert result is True
        
        # Verify API call
        mock_client.create_tweet.assert_called_once_with(
            text='Great tweet!',
            in_reply_to_tweet_id='123456789'
        )
    
    @patch('tweepy.Client')
    def test_reply_to_tweet_failure(self, mock_client_class):
        """Test failed tweet reply."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock response indicating failure
        mock_response = Mock()
        mock_response.data = None
        mock_client.create_tweet.return_value = mock_response
        
        # Initialize client with mocked client
        self.client.client_v2 = mock_client
        
        # Test reply
        result = self.client.reply_to_tweet('123456789', 'Great tweet!')
        
        # Assertions
        assert result is False
    
    @patch('tweepy.Client')
    def test_reply_to_tweet_no_client(self, mock_client_class):
        """Test reply when client is not initialized."""
        self.client.client_v2 = None
        
        result = self.client.reply_to_tweet('123456789', 'Great tweet!')
        
        assert result is False


def test_integration_workflow():
    """
    Integration test demonstrating the complete workflow:
    1. Search for tweets
    2. Like a tweet
    3. Reply to a tweet
    """
    # This would be used for actual integration testing with real API
    # For now, we'll create a mock integration test
    
    with patch('tweepy.Client') as mock_client_class:
        # Mock the client and responses
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock search response
        mock_tweet_data = Mock()
        mock_tweet_data.id = '123456789'
        mock_tweet_data.text = 'Test tweet about AI'
        mock_tweet_data.author_id = '987654321'
        mock_tweet_data.conversation_id = '123456789'
        mock_tweet_data.created_at = Mock()
        mock_tweet_data.created_at.isoformat.return_value = '2024-01-01T12:00:00Z'
        mock_tweet_data.public_metrics = {'like_count': 10, 'retweet_count': 5}
        
        mock_search_response = Mock()
        mock_search_response.data = [mock_tweet_data]
        mock_search_response.meta = {'next_token': None}
        
        # Mock like response
        mock_like_response = Mock()
        mock_like_response.data = {'liked': True}
        
        # Mock reply response
        mock_reply_response = Mock()
        mock_reply_response.data = {'id': '987654321'}
        
        # Configure mock client
        mock_client.search_recent_tweets.return_value = mock_search_response
        mock_client.like.return_value = mock_like_response
        mock_client.create_tweet.return_value = mock_reply_response
        
        # Create client
        client = TweepyTwitterClient(
            bearer_token='test_bearer_token',
            user_id='test_user_id'
        )
        client.client_v2 = mock_client
        
        # Step 1: Search for tweets
        search_result = client.search_tweets('AI', max_results=5)
        assert len(search_result.tweets) == 1
        
        # Step 2: Like the first tweet
        tweet_to_like = search_result.tweets[0]
        like_success = client.like_tweet(tweet_to_like.id)
        assert like_success is True
        
        # Step 3: Reply to the tweet
        reply_success = client.reply_to_tweet(tweet_to_like.id, 'Interesting perspective on AI!')
        assert reply_success is True
        
        # Verify all API calls were made
        mock_client.search_recent_tweets.assert_called_once()
        mock_client.like.assert_called_once_with(tweet_id='123456789', user_id='test_user_id')
        mock_client.create_tweet.assert_called_once_with(
            text='Interesting perspective on AI!',
            in_reply_to_tweet_id='123456789'
        )


def test_real_integration():
    """
    Real integration test that uses actual Twitter API.
    This test will:
    1. Search for tweets about a specific topic
    2. Like a tweet
    3. Reply to a tweet
    
    Requires real Twitter API credentials.
    """
    print("🚀 Running REAL Twitter API Integration Test")
    print("=" * 60)
    
    # Get credentials from environment
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    user_id = os.getenv('TWITTER_USER_ID')
    
    if not bearer_token or not user_id:
        pytest.skip("Skipping real integration test: Missing TWITTER_BEARER_TOKEN or TWITTER_USER_ID")
    
    print(f"✓ Found Twitter credentials")
    print(f"✓ User ID: {user_id}")
    
    # Create client with real credentials
    client = TweepyTwitterClient(
        bearer_token=bearer_token,
        user_id=user_id
    )
    
    # Test 1: Validate credentials
    print("\n1. Testing credential validation...")
    if not client.validate_credentials():
        pytest.fail("Credential validation failed")
    print("✓ Credentials are valid")
    
    # Test 2: Search for tweets
    print("\n2. Testing tweet search...")
    search_query = "AI machine learning"
    search_result = client.search_tweets(search_query, max_results=5)
    
    assert len(search_result.tweets) > 0, f"No tweets found for query: {search_query}"
    print(f"✓ Found {len(search_result.tweets)} tweets about '{search_query}'")
    
    # Display found tweets
    for i, tweet in enumerate(search_result.tweets[:3], 1):
        print(f"   {i}. {tweet.text[:80]}...")
        print(f"      ID: {tweet.id}, Likes: {tweet.public_metrics.get('like_count', 0) if tweet.public_metrics else 0}")
    
    # Test 3: Like a tweet
    print("\n3. Testing tweet like...")
    tweet_to_like = search_result.tweets[0]
    print(f"Liking tweet: {tweet_to_like.text[:60]}...")
    
    like_success = client.like_tweet(tweet_to_like.id)
    assert like_success, f"Failed to like tweet {tweet_to_like.id}"
    print(f"✓ Successfully liked tweet {tweet_to_like.id}")
    
    # Test 4: Reply to a tweet
    print("\n4. Testing tweet reply...")
    reply_text = f"Great insights on {search_query}! Thanks for sharing this valuable information. 🤖✨"
    print(f"Replying to tweet {tweet_to_like.id}...")
    
    reply_success = client.reply_to_tweet(tweet_to_like.id, reply_text)
    assert reply_success, f"Failed to reply to tweet {tweet_to_like.id}"
    print(f"✓ Successfully replied to tweet {tweet_to_like.id}")
    print(f"✓ Reply: {reply_text[:60]}...")
    
    # Test 5: Get user info
    print("\n5. Testing user info retrieval...")
    user_info = client.get_user_info()
    assert user_info is not None, "Failed to get user info"
    assert 'data' in user_info, "User info missing data field"
    
    username = user_info['data']['username']
    print(f"✓ Authenticated as: @{username}")
    
    # Test 6: Get tweet details
    print("\n6. Testing tweet details retrieval...")
    tweet_details = client.get_tweet_details(tweet_to_like.id)
    assert tweet_details is not None, f"Failed to get details for tweet {tweet_to_like.id}"
    assert tweet_details.id == tweet_to_like.id, "Tweet ID mismatch"
    print(f"✓ Retrieved details for tweet {tweet_to_like.id}")
    
    print("\n" + "=" * 60)
    print("🎉 ALL REAL INTEGRATION TESTS PASSED!")
    print("✓ Search tweets: Working")
    print("✓ Like tweets: Working") 
    print("✓ Reply to tweets: Working")
    print("✓ User info: Working")
    print("✓ Tweet details: Working")
    print("\nYour Twitter client is fully functional! 🚀")


if __name__ == '__main__':
    print("Running TweepyTwitterClient tests...")
    
    # Check for real credentials first
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    user_id = os.getenv('TWITTER_USER_ID')
    
    if bearer_token and user_id:
        print("🔑 Found Twitter credentials - Running REAL integration test...")
        print("This will make actual API calls to Twitter!")
        
        try:
            # Run the real integration test
            test_real_integration()
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            print("\nFalling back to unit tests...")
            
            # Fall back to unit tests
            if HAS_PYTEST:
                pytest.main([__file__, '-v', '-k', 'not test_real_integration'])
            else:
                print("Running basic unit tests...")
                test_client = TestTweepyTwitterClient()
                test_client.setup_method()
                test_client.test_client_initialization()
                print("✓ Basic tests passed")
    else:
        print("⚠️  No Twitter credentials found.")
        print("To run REAL integration tests, set these environment variables:")
        print("   export TWITTER_BEARER_TOKEN='your_bearer_token'")
        print("   export TWITTER_USER_ID='your_user_id'")
        print("\nRunning unit tests instead...")
        
        if HAS_PYTEST:
            pytest.main([__file__, '-v', '-k', 'not test_real_integration'])
        else:
            print("pytest not available. Install with: uv add pytest")
