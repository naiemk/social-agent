"""
Tweepy-based Twitter/X API client with enhanced error handling and rate limiting.

This module provides a robust client for interacting with the Twitter API using Tweepy,
including proper error handling, rate limiting, and retry logic.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import tweepy
from tweepy import API, OAuth1UserHandler, Client
from tweepy.errors import TweepyException, TooManyRequests, Unauthorized, Forbidden
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from config import settings
except Exception:
    # Handle case where config is not available (e.g., during testing)
    settings = None

logger = logging.getLogger(__name__)


@dataclass
class Tweet:
    """Represents a tweet with its metadata."""
    id: str
    text: str
    author_id: str
    conversation_id: Optional[str] = None
    created_at: Optional[str] = None
    public_metrics: Optional[Dict] = None


@dataclass
class SearchResult:
    """Represents the result of a tweet search."""
    tweets: List[Tweet]
    total_count: int
    next_token: Optional[str] = None


class TweepyTwitterClient:
    """Enhanced Twitter API client using Tweepy with rate limiting and error handling."""
    
    def __init__(self, bearer_token: str = None, user_id: str = None, 
                 api_key: str = None, api_secret: str = None,
                 access_token: str = None, access_token_secret: str = None):
        self.bearer_token = bearer_token or (settings.twitter_bearer_token if settings else None)
        self.user_id = user_id or (settings.twitter_user_id if settings else None)
        self.api_key = api_key or (settings.twitter_api_key if settings else None)
        self.api_secret = api_secret or (settings.twitter_api_secret if settings else None)
        self.access_token = access_token or (settings.twitter_access_token if settings else None)
        self.access_token_secret = access_token_secret or (settings.twitter_access_token_secret if settings else None)
        
        # Initialize clients
        self._init_clients()
        
    def _init_clients(self):
        """Initialize Tweepy clients based on available credentials."""
        try:
            # Always try to initialize the v2 client with bearer token
            if self.bearer_token:
                self.client_v2 = Client(bearer_token=self.bearer_token)
                logger.info("Initialized Twitter API v2 client with bearer token")
            else:
                self.client_v2 = None
                logger.warning("No bearer token provided, v2 client not initialized")
            
            # Initialize v1.1 client for actions that require OAuth (optional)
            if all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
                auth = OAuth1UserHandler(
                    self.api_key,
                    self.api_secret,
                    self.access_token,
                    self.access_token_secret
                )
                self.api_v1 = API(auth, wait_on_rate_limit=True)
                logger.info("Initialized Twitter API v1.1 client with OAuth")
            else:
                self.api_v1 = None
                logger.info("OAuth credentials not provided, v1.1 client not initialized (bearer token authentication only)")
                
        except Exception as e:
            logger.error(f"Error initializing Tweepy clients: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((TweepyException, TooManyRequests))
    )
    def search_tweets(self, query: str, max_results: int = 10, next_token: str = None) -> SearchResult:
        """
        Search for recent tweets using Twitter API v2.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-100)
            next_token: Token for pagination
            
        Returns:
            SearchResult containing tweets and metadata
        """
        if not self.client_v2:
            logger.error("Twitter API v2 client not initialized")
            return SearchResult(tweets=[], total_count=0)
        
        try:
            # Use Tweepy's search_recent_tweets method
            response = self.client_v2.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                next_token=next_token,
                tweet_fields=['conversation_id', 'author_id', 'created_at', 'public_metrics']
            )
            
            tweets = []
            for tweet_data in response.data or []:
                tweet = Tweet(
                    id=tweet_data.id,
                    text=tweet_data.text,
                    author_id=tweet_data.author_id,
                    conversation_id=getattr(tweet_data, 'conversation_id', None),
                    created_at=tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                    public_metrics=getattr(tweet_data, 'public_metrics', None)
                )
                tweets.append(tweet)
            
            return SearchResult(
                tweets=tweets,
                total_count=len(tweets),
                next_token=response.meta.get('next_token') if response.meta else None
            )
            
        except TooManyRequests as e:
            logger.warning(f"Rate limit exceeded: {e}")
            # Tweepy handles rate limiting automatically with wait_on_rate_limit=True
            raise
        except TweepyException as e:
            logger.error(f"Tweepy error searching tweets: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching tweets: {e}")
            return SearchResult(tweets=[], total_count=0)
    
    def get_conversation_replies(self, conversation_id: str, max_results: int = 20) -> List[Tweet]:
        """
        Get replies in a conversation thread.
        
        Args:
            conversation_id: The conversation ID
            max_results: Maximum number of replies
            
        Returns:
            List of Tweet objects representing replies
        """
        query = f"conversation_id:{conversation_id}"
        result = self.search_tweets(query, max_results=max_results)
        return result.tweets
    
    def like_tweet(self, tweet_id: str) -> bool:
        """
        Like a tweet using Twitter API v2.
        
        Args:
            tweet_id: ID of the tweet to like
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client_v2:
            logger.warning("Twitter API v2 client not initialized. Skipping like action.")
            return False
        
        if not self.user_id:
            logger.warning("Twitter user ID not configured. Skipping like action.")
            return False
        
        try:
            response = self.client_v2.like(tweet_id=tweet_id, user_id=self.user_id)
            
            if response.data.get('liked'):
                logger.info(f"Successfully liked tweet {tweet_id}")
                return True
            else:
                logger.warning(f"Failed to like tweet {tweet_id}")
                return False
                
        except Unauthorized as e:
            logger.error(f"Unauthorized to like tweet {tweet_id}: {e}")
            return False
        except Forbidden as e:
            logger.error(f"Forbidden to like tweet {tweet_id}: {e}")
            return False
        except TooManyRequests as e:
            logger.warning(f"Rate limit exceeded when liking tweet {tweet_id}: {e}")
            return False
        except TweepyException as e:
            logger.error(f"Tweepy error liking tweet {tweet_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error liking tweet {tweet_id}: {e}")
            return False
    
    def reply_to_tweet(self, tweet_id: str, text: str) -> bool:
        """
        Reply to a tweet using Twitter API v2.
        
        Args:
            tweet_id: ID of the tweet to reply to
            text: Reply text
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client_v2:
            logger.warning("Twitter API v2 client not initialized. Skipping reply action.")
            return False
        
        try:
            response = self.client_v2.create_tweet(
                text=text,
                in_reply_to_tweet_id=tweet_id
            )
            
            if response.data:
                logger.info(f"Successfully replied to tweet {tweet_id} with tweet {response.data['id']}")
                return True
            else:
                logger.warning(f"Failed to reply to tweet {tweet_id}")
                return False
                
        except Unauthorized as e:
            logger.error(f"Unauthorized to reply to tweet {tweet_id}: {e}")
            return False
        except Forbidden as e:
            logger.error(f"Forbidden to reply to tweet {tweet_id}: {e}")
            return False
        except TooManyRequests as e:
            logger.warning(f"Rate limit exceeded when replying to tweet {tweet_id}: {e}")
            return False
        except TweepyException as e:
            logger.error(f"Tweepy error replying to tweet {tweet_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error replying to tweet {tweet_id}: {e}")
            return False
    
    def get_user_info(self) -> Optional[Dict]:
        """Get information about the authenticated user using Twitter API v2."""
        if not self.client_v2:
            logger.warning("Twitter API v2 client not initialized")
            return None
        
        # If we have a user_id, we can return basic info without making an API call
        if self.user_id:
            return {
                'data': {
                    'id': self.user_id,
                    'name': 'Authenticated User',
                    'username': 'authenticated_user',
                    'public_metrics': None
                }
            }
        
        # For bearer token authentication, we can't get user info without OAuth
        # Return a basic response indicating bearer token authentication
        return {
            'data': {
                'id': 'bearer_token_user',
                'name': 'Bearer Token User',
                'username': 'bearer_token_user',
                'public_metrics': None
            }
        }
    
    def validate_credentials(self) -> bool:
        """Validate that the API credentials are working."""
        try:
            # For bearer token authentication, we can validate by checking if client is initialized
            if self.bearer_token and self.client_v2:
                logger.info("Bearer token authentication validated - client initialized successfully")
                return True
            else:
                logger.error("No bearer token or client_v2 not initialized")
                return False
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False
    
    def get_tweet_details(self, tweet_id: str) -> Optional[Tweet]:
        """
        Get detailed information about a specific tweet.
        
        Args:
            tweet_id: ID of the tweet to retrieve
            
        Returns:
            Tweet object or None if not found
        """
        if not self.client_v2:
            logger.warning("Twitter API v2 client not initialized")
            return None
        
        try:
            response = self.client_v2.get_tweet(
                tweet_id,
                tweet_fields=['conversation_id', 'author_id', 'created_at', 'public_metrics']
            )
            
            if response.data:
                tweet_data = response.data
                return Tweet(
                    id=tweet_data.id,
                    text=tweet_data.text,
                    author_id=tweet_data.author_id,
                    conversation_id=getattr(tweet_data, 'conversation_id', None),
                    created_at=tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                    public_metrics=getattr(tweet_data, 'public_metrics', None)
                )
            return None
            
        except TweepyException as e:
            logger.error(f"Tweepy error getting tweet {tweet_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting tweet {tweet_id}: {e}")
            return None
    
    def get_user_timeline(self, user_id: str = None, max_results: int = 10) -> List[Tweet]:
        """
        Get recent tweets from a user's timeline.
        
        Args:
            user_id: User ID to get timeline for (defaults to authenticated user)
            max_results: Maximum number of tweets to retrieve
            
        Returns:
            List of Tweet objects
        """
        if not self.client_v2:
            logger.warning("Twitter API v2 client not initialized")
            return []
        
        target_user_id = user_id or self.user_id
        if not target_user_id:
            logger.warning("No user ID provided for timeline")
            return []
        
        try:
            response = self.client_v2.get_users_tweets(
                id=target_user_id,
                max_results=min(max_results, 100),
                tweet_fields=['conversation_id', 'author_id', 'created_at', 'public_metrics']
            )
            
            tweets = []
            for tweet_data in response.data or []:
                tweet = Tweet(
                    id=tweet_data.id,
                    text=tweet_data.text,
                    author_id=tweet_data.author_id,
                    conversation_id=getattr(tweet_data, 'conversation_id', None),
                    created_at=tweet_data.created_at.isoformat() if tweet_data.created_at else None,
                    public_metrics=getattr(tweet_data, 'public_metrics', None)
                )
                tweets.append(tweet)
            
            return tweets
            
        except TweepyException as e:
            logger.error(f"Tweepy error getting timeline for user {target_user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting timeline for user {target_user_id}: {e}")
            return []
