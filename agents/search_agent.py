"""
Search agent for finding and retrieving tweets.

This agent handles searching for tweets based on configured search terms
and returns ranked results for further processing.
"""

import logging
from typing import List, Dict, Optional

from google.adk.agents import BaseAgent
from sources.x_client import TwitterClient, SearchResult
from kernel.ranker import SemanticRanker, RankedTweet
from config import settings

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """Agent responsible for searching and ranking tweets."""
    
    def __init__(self, twitter_client: TwitterClient = None, ranker: SemanticRanker = None):
        """Initialize the search agent.
        
        Args:
            twitter_client: Twitter client instance
            ranker: Semantic ranker instance
        """
        super().__init__(name="search_agent", description="Searches and ranks tweets")
        self.twitter_client = twitter_client or TwitterClient()
        self.ranker = ranker or SemanticRanker()
        
    def search_for_term(self, search_term: str, max_results: int = None) -> List[RankedTweet]:
        """
        Search for tweets matching a specific term.
        
        Args:
            search_term: The search term to look for
            max_results: Maximum number of results
            
        Returns:
            List of ranked tweets
        """
        max_results = max_results or settings.max_tweets_per_run
        
        # Create search query (exclude retweets and replies to reduce noise)
        query = f"{search_term} -is:retweet -is:reply"
        
        logger.info(f"Searching for tweets with query: {query}")
        
        try:
            # Search for tweets
            search_result = self.twitter_client.search_tweets(query, max_results=max_results)
            
            if not search_result.tweets:
                logger.info(f"No tweets found for search term: {search_term}")
                return []
            
            logger.info(f"Found {len(search_result.tweets)} tweets for '{search_term}'")
            
            # Rank the tweets semantically
            ranked_tweets = self.ranker.rank_tweets(
                search_result.tweets, 
                [search_term],
                min_score=0.3
            )
            
            logger.info(f"Ranked {len(ranked_tweets)} tweets above threshold")
            return ranked_tweets
            
        except Exception as e:
            logger.error(f"Error searching for term '{search_term}': {e}")
            return []
    
    def search_multiple_terms(self, search_terms: List[str] = None) -> Dict[str, List[RankedTweet]]:
        """
        Search for multiple terms and return results grouped by term.
        
        Args:
            search_terms: List of search terms (defaults to configured terms)
            
        Returns:
            Dictionary mapping search terms to ranked tweet lists
        """
        search_terms = search_terms or settings.search_terms
        results = {}
        
        for term in search_terms:
            logger.info(f"Searching for term: {term}")
            ranked_tweets = self.search_for_term(term)
            results[term] = ranked_tweets
        
        total_tweets = sum(len(tweets) for tweets in results.values())
        logger.info(f"Search completed. Found {total_tweets} total ranked tweets across {len(search_terms)} terms")
        
        return results
    
    def get_top_tweets(self, search_terms: List[str] = None, top_n: int = 10) -> List[RankedTweet]:
        """
        Get the top N tweets across all search terms.
        
        Args:
            search_terms: List of search terms to search
            top_n: Number of top tweets to return
            
        Returns:
            List of top ranked tweets
        """
        results = self.search_multiple_terms(search_terms)
        
        # Flatten and sort all tweets by score
        all_tweets = []
        for term, tweets in results.items():
            all_tweets.extend(tweets)
        
        # Sort by score (highest first) and take top N
        all_tweets.sort(key=lambda x: x.score, reverse=True)
        top_tweets = all_tweets[:top_n]
        
        logger.info(f"Selected top {len(top_tweets)} tweets from {len(all_tweets)} total")
        return top_tweets
