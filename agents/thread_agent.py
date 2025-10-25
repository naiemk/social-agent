"""
Thread agent for analyzing conversation threads.

This agent handles the "dig_deeper" action by retrieving and analyzing
conversation replies to find valuable interactions.
"""

import logging
import random
from typing import List, Dict, Tuple, Optional

from google.adk.agents import BaseAgent
from sources.tweepy_client import TweepyTwitterClient
from kernel.decider import TweetDecider, TweetDecision
from kernel.ranker import RankedTweet, SemanticRanker
from config import settings

logger = logging.getLogger(__name__)


class ThreadAgent(BaseAgent):
    """Agent responsible for analyzing conversation threads."""
    
    def __init__(self, twitter_client: TweepyTwitterClient = None, 
                 decider: TweetDecider = None, ranker: SemanticRanker = None):
        """Initialize the thread agent.
        
        Args:
            twitter_client: Twitter client instance
            decider: Tweet decision engine instance
            ranker: Semantic ranker instance
        """
        super().__init__(name="thread_agent", description="Analyzes conversation threads")
        self.twitter_client = twitter_client or TweepyTwitterClient()
        self.decider = decider or TweetDecider()
        self.ranker = ranker or SemanticRanker()
        
    def analyze_thread(self, tweet: RankedTweet, max_depth: int = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """
        Analyze a conversation thread for valuable replies.
        
        Args:
            tweet: The original tweet to analyze
            max_depth: Maximum depth of thread analysis
            
        Returns:
            List of (ranked_tweet, decision) tuples for thread replies
        """
        max_depth = max_depth or settings.max_conversation_depth
        
        if not tweet.tweet.conversation_id:
            logger.warning(f"No conversation ID for tweet {tweet.tweet.id}")
            return []
        
        logger.info(f"Analyzing thread for tweet {tweet.tweet.id} (conversation: {tweet.tweet.conversation_id})")
        
        try:
            # Get conversation replies
            replies = self.twitter_client.get_conversation_replies(
                tweet.tweet.conversation_id,
                max_results=20
            )
            
            if not replies:
                logger.info(f"No replies found for conversation {tweet.tweet.conversation_id}")
                return []
            
            logger.info(f"Found {len(replies)} replies in conversation")
            
            # Filter out the original tweet and any we've already processed
            filtered_replies = [
                reply for reply in replies 
                if reply.id != tweet.tweet.id
            ]
            
            if not filtered_replies:
                logger.info("No new replies to analyze")
                return []
            
            # Rank the replies
            ranked_replies = self.ranker.rank_tweets(
                filtered_replies,
                [tweet.tweet.text],  # Use original tweet text as context
                min_score=0.2  # Lower threshold for thread analysis
            )
            
            logger.info(f"Ranked {len(ranked_replies)} replies above threshold")
            
            # Analyze top replies
            top_replies = ranked_replies[:10]  # Limit to top 10 replies
            
            # Make decisions for replies
            reply_decisions = self.decider.batch_decide(
                top_replies,
                context={
                    "original_tweet": tweet.tweet.text,
                    "conversation_context": f"Reply in conversation started by: {tweet.tweet.text[:100]}..."
                }
            )
            
            # Filter by confidence and focus on actionable decisions
            actionable_decisions = []
            for ranked_reply, decision in reply_decisions:
                if (decision.confidence >= settings.kernel_confidence_threshold and
                    decision.decision in ["like", "comment"]):
                    actionable_decisions.append((ranked_reply, decision))
            
            logger.info(f"Found {len(actionable_decisions)} actionable replies in thread")
            return actionable_decisions
            
        except Exception as e:
            logger.error(f"Error analyzing thread for tweet {tweet.tweet.id}: {e}")
            return []
    
    def analyze_multiple_threads(self, tweets: List[RankedTweet]) -> Dict[str, List[Tuple[RankedTweet, TweetDecision]]]:
        """
        Analyze multiple conversation threads.
        
        Args:
            tweets: List of tweets to analyze threads for
            
        Returns:
            Dictionary mapping tweet IDs to their thread analysis results
        """
        results = {}
        
        for tweet in tweets:
            if tweet.tweet.conversation_id:
                thread_results = self.analyze_thread(tweet)
                if thread_results:
                    results[tweet.tweet.id] = thread_results
            else:
                logger.debug(f"Skipping tweet {tweet.tweet.id} - no conversation ID")
        
        total_thread_actions = sum(len(actions) for actions in results.values())
        logger.info(f"Thread analysis complete: {total_thread_actions} total actions across {len(results)} threads")
        
        return results
    
    def prioritize_thread_actions(self, thread_results: Dict[str, List[Tuple[RankedTweet, TweetDecision]]], 
                                 max_actions: int = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """
        Prioritize thread actions across multiple conversations.
        
        Args:
            thread_results: Results from thread analysis
            max_actions: Maximum number of actions to return
            
        Returns:
            List of prioritized thread actions
        """
        max_actions = max_actions or settings.max_tweets_per_run
        
        # Flatten all thread actions
        all_actions = []
        for tweet_id, actions in thread_results.items():
            all_actions.extend(actions)
        
        if not all_actions:
            return []
        
        # Sort by confidence and randomize slightly to avoid predictable patterns
        all_actions.sort(key=lambda x: (x[1].confidence, random.random()), reverse=True)
        
        # Take top actions
        prioritized = all_actions[:max_actions]
        
        logger.info(f"Prioritized {len(prioritized)} thread actions from {len(all_actions)} total")
        return prioritized
