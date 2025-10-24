"""
Twitter/X API client with enhanced error handling and rate limiting.

This module provides a robust client for interacting with the Twitter API v2,
including proper error handling, rate limiting, and retry logic.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

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


class TwitterClient:
    """Enhanced Twitter API client with rate limiting and error handling."""
    
    def __init__(self, bearer_token: str = None, user_id: str = None):
        self.bearer_token = bearer_token or settings.twitter_bearer_token
        self.user_id = user_id or settings.twitter_user_id
        self.base_url = "https://api.twitter.com/2"
        self.session = requests.Session()
        self.session.headers.update(self._get_headers())
        
        # Rate limiting tracking
        self._rate_limit_reset = 0
        self._requests_made = 0
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Twitter API requests."""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "social-agent/1.0"
        }
    
    def _check_rate_limit(self, response: requests.Response) -> None:
        """Check and handle rate limiting from response headers."""
        if "x-rate-limit-remaining" in response.headers:
            remaining = int(response.headers["x-rate-limit-remaining"])
            reset_time = int(response.headers.get("x-rate-limit-reset", 0))
            
            if remaining == 0:
                wait_time = reset_time - int(time.time()) + 1
                logger.warning(f"Rate limit reached. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
    )
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request with retry logic and rate limiting."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Handle rate limiting
            if response.status_code == 429:
                self._check_rate_limit(response)
                raise requests.exceptions.RequestException("Rate limited")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def search_tweets(self, query: str, max_results: int = 10, next_token: str = None) -> SearchResult:
        """
        Search for recent tweets.
        
        Args:
            query: Search query string
            max_results: Maximum number of results (1-100)
            next_token: Token for pagination
            
        Returns:
            SearchResult containing tweets and metadata
        """
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "conversation_id,author_id,created_at,public_metrics"
        }
        
        if next_token:
            params["next_token"] = next_token
        
        try:
            response = self._make_request("GET", "/tweets/search/recent", params=params)
            data = response.json()
            
            tweets = []
            for tweet_data in data.get("data", []):
                tweet = Tweet(
                    id=tweet_data["id"],
                    text=tweet_data["text"],
                    author_id=tweet_data.get("author_id", ""),
                    conversation_id=tweet_data.get("conversation_id"),
                    created_at=tweet_data.get("created_at"),
                    public_metrics=tweet_data.get("public_metrics")
                )
                tweets.append(tweet)
            
            return SearchResult(
                tweets=tweets,
                total_count=len(tweets),
                next_token=data.get("meta", {}).get("next_token")
            )
            
        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
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
        Like a tweet.
        
        Args:
            tweet_id: ID of the tweet to like
            
        Returns:
            True if successful, False otherwise
        """
        if not self.user_id:
            logger.warning("Twitter user ID not configured. Skipping like action.")
            return False
        
        url = f"/users/{self.user_id}/likes"
        payload = {"tweet_id": tweet_id}
        
        try:
            response = self._make_request("POST", url, json=payload)
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully liked tweet {tweet_id}")
                return True
            else:
                logger.warning(f"Failed to like tweet {tweet_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error liking tweet {tweet_id}: {e}")
            return False
    
    def reply_to_tweet(self, tweet_id: str, text: str) -> bool:
        """
        Reply to a tweet.
        
        Args:
            tweet_id: ID of the tweet to reply to
            text: Reply text
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id}
        }
        
        try:
            response = self._make_request("POST", "/tweets", json=payload)
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully replied to tweet {tweet_id}")
                return True
            else:
                logger.warning(f"Failed to reply to tweet {tweet_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error replying to tweet {tweet_id}: {e}")
            return False
    
    def get_user_info(self) -> Optional[Dict]:
        """Get information about the authenticated user."""
        try:
            response = self._make_request("GET", "/users/me")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    def validate_credentials(self) -> bool:
        """Validate that the API credentials are working."""
        try:
            user_info = self.get_user_info()
            return user_info is not None and "data" in user_info
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False
