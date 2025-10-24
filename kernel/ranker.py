"""
Semantic ranking system for tweets using sentence transformers.

This module provides fast semantic ranking of tweets using pre-trained
sentence transformers to filter and prioritize content.
"""

import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None
    np = None

from sources.x_client import Tweet
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class RankedTweet:
    """A tweet with its semantic ranking score."""
    tweet: Tweet
    score: float
    relevance_reason: str


class SemanticRanker:
    """Semantic ranker using sentence transformers for fast filtering."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the semantic ranker.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not available. Using simple text matching.")
            self.model = None
            return
        
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded semantic ranker model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load semantic ranker model: {e}")
            self.model = None
    
    def rank_tweets(self, tweets: List[Tweet], query_terms: List[str], 
                   min_score: float = 0.3) -> List[RankedTweet]:
        """
        Rank tweets based on semantic similarity to query terms.
        
        Args:
            tweets: List of tweets to rank
            query_terms: Search terms to match against
            min_score: Minimum similarity score threshold
            
        Returns:
            List of ranked tweets sorted by relevance
        """
        if not tweets:
            return []
        
        if not self.model:
            # Fallback to simple text matching
            return self._simple_ranking(tweets, query_terms, min_score)
        
        try:
            # Prepare texts for embedding
            tweet_texts = [tweet.text for tweet in tweets]
            query_text = " ".join(query_terms)
            
            # Generate embeddings
            tweet_embeddings = self.model.encode(tweet_texts)
            query_embedding = self.model.encode([query_text])
            
            # Calculate similarities
            similarities = np.dot(tweet_embeddings, query_embedding.T).flatten()
            
            # Create ranked tweets
            ranked_tweets = []
            for tweet, score in zip(tweets, similarities):
                if score >= min_score:
                    relevance_reason = self._generate_relevance_reason(tweet.text, query_terms, score)
                    ranked_tweets.append(RankedTweet(
                        tweet=tweet,
                        score=float(score),
                        relevance_reason=relevance_reason
                    ))
            
            # Sort by score (highest first)
            ranked_tweets.sort(key=lambda x: x.score, reverse=True)
            
            logger.info(f"Ranked {len(tweets)} tweets, {len(ranked_tweets)} above threshold {min_score}")
            return ranked_tweets
            
        except Exception as e:
            logger.error(f"Error in semantic ranking: {e}")
            return self._simple_ranking(tweets, query_terms, min_score)
    
    def _simple_ranking(self, tweets: List[Tweet], query_terms: List[str], 
                       min_score: float = 0.3) -> List[RankedTweet]:
        """Fallback simple text-based ranking."""
        ranked_tweets = []
        
        for tweet in tweets:
            score = self._calculate_simple_score(tweet.text, query_terms)
            if score >= min_score:
                relevance_reason = f"Text contains {score:.2f} matching terms"
                ranked_tweets.append(RankedTweet(
                    tweet=tweet,
                    score=score,
                    relevance_reason=relevance_reason
                ))
        
        ranked_tweets.sort(key=lambda x: x.score, reverse=True)
        return ranked_tweets
    
    def _calculate_simple_score(self, text: str, query_terms: List[str]) -> float:
        """Calculate a simple text matching score."""
        text_lower = text.lower()
        matches = sum(1 for term in query_terms if term.lower() in text_lower)
        return matches / len(query_terms) if query_terms else 0.0
    
    def _generate_relevance_reason(self, text: str, query_terms: List[str], score: float) -> str:
        """Generate a human-readable relevance reason."""
        if score > 0.8:
            return f"Highly relevant (score: {score:.2f})"
        elif score > 0.6:
            return f"Moderately relevant (score: {score:.2f})"
        else:
            return f"Somewhat relevant (score: {score:.2f})"
    
    def filter_by_keywords(self, tweets: List[Tweet], keywords: List[str]) -> List[Tweet]:
        """Filter tweets by keyword presence."""
        if not keywords:
            return tweets
        
        filtered = []
        for tweet in tweets:
            text_lower = tweet.text.lower()
            if any(keyword.lower() in text_lower for keyword in keywords):
                filtered.append(tweet)
        
        logger.info(f"Filtered {len(tweets)} tweets to {len(filtered)} by keywords")
        return filtered
    
    def is_available(self) -> bool:
        """Check if semantic ranking is available."""
        return self.model is not None
