"""
Kernel agent for analyzing and deciding on tweet actions.

This agent combines semantic ranking with LLM-based decision making
to determine appropriate actions for tweets.
"""

import logging
from typing import List, Dict, Tuple, Optional

from google.adk.agents import BaseAgent
from kernel.ranker import RankedTweet, SemanticRanker
from kernel.decider import TweetDecider, TweetDecision
from config import settings

logger = logging.getLogger(__name__)


class KernelAgent(BaseAgent):
    """Agent responsible for analyzing tweets and making decisions."""
    
    def __init__(self, ranker: SemanticRanker = None, decider: TweetDecider = None):
        """Initialize the kernel agent.
        
        Args:
            ranker: Semantic ranker instance
            decider: Tweet decision engine instance
        """
        super().__init__(name="kernel_agent", description="Analyzes tweets and makes decisions")
        self.ranker = ranker or SemanticRanker()
        self.decider = decider or TweetDecider()
        
    def analyze_and_decide(self, ranked_tweets: List[RankedTweet], 
                          context: Dict = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """
        Analyze ranked tweets and make decisions.
        
        Args:
            ranked_tweets: List of ranked tweets to analyze
            context: Additional context for decision making
            
        Returns:
            List of tuples (ranked_tweet, decision) for successful analyses
        """
        if not ranked_tweets:
            logger.info("No tweets to analyze")
            return []
        
        logger.info(f"Analyzing {len(ranked_tweets)} ranked tweets")
        
        # Make decisions for all tweets
        decisions = self.decider.batch_decide(ranked_tweets, context)
        
        # Filter by confidence threshold
        filtered_decisions = self.decider.filter_by_confidence(
            decisions, 
            settings.kernel_confidence_threshold
        )
        
        logger.info(f"Analysis complete: {len(filtered_decisions)} decisions above confidence threshold")
        return filtered_decisions
    
    def get_actionable_tweets(self, ranked_tweets: List[RankedTweet], 
                             context: Dict = None) -> Dict[str, List[Tuple[RankedTweet, TweetDecision]]]:
        """
        Get tweets grouped by their recommended action.
        
        Args:
            ranked_tweets: List of ranked tweets to analyze
            context: Additional context for decision making
            
        Returns:
            Dictionary mapping action types to lists of (tweet, decision) tuples
        """
        decisions = self.analyze_and_decide(ranked_tweets, context)
        
        # Group by decision type
        action_groups = {
            "interesting": [],
            "like": [],
            "comment": [],
            "dig_deeper": []
        }
        
        for ranked_tweet, decision in decisions:
            action = decision.decision
            if action in action_groups:
                action_groups[action].append((ranked_tweet, decision))
        
        # Log summary
        total_actions = sum(len(group) for group in action_groups.values())
        logger.info(f"Action summary: {total_actions} total actions")
        for action, tweets in action_groups.items():
            if tweets:
                logger.info(f"  {action}: {len(tweets)} tweets")
        
        return action_groups
    
    def prioritize_actions(self, action_groups: Dict[str, List[Tuple[RankedTweet, TweetDecision]]], 
                          max_actions: int = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """
        Prioritize actions based on decision confidence and tweet ranking.
        
        Args:
            action_groups: Dictionary of action groups
            max_actions: Maximum number of actions to return
            
        Returns:
            List of prioritized (tweet, decision) tuples
        """
        max_actions = max_actions or settings.max_tweets_per_run
        
        # Combine all actions and sort by priority
        all_actions = []
        
        # Priority order: dig_deeper > comment > like > interesting
        priority_order = ["dig_deeper", "comment", "like", "interesting"]
        
        for action in priority_order:
            if action in action_groups:
                # Sort by confidence within each action type
                actions = sorted(action_groups[action], key=lambda x: x[1].confidence, reverse=True)
                all_actions.extend(actions)
        
        # Take top actions
        prioritized = all_actions[:max_actions]
        
        logger.info(f"Prioritized {len(prioritized)} actions from {len(all_actions)} total")
        return prioritized
