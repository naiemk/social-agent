"""
Action agent for executing social media actions.

This agent handles the execution of actions like liking tweets and replying,
with proper rate limiting and safety checks.
"""

import logging
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta

from google.adk.agents import BaseAgent
from sources.tweepy_client import TweepyTwitterClient
from kernel.decider import TweetDecision
from kernel.ranker import RankedTweet
from config import settings

logger = logging.getLogger(__name__)


class ActionAgent(BaseAgent):
    """Agent responsible for executing social media actions."""
    
    def __init__(self, twitter_client: TweepyTwitterClient = None):
        """Initialize the action agent.
        
        Args:
            twitter_client: Twitter client instance
        """
        super().__init__(name="action_agent", description="Executes social media actions")
        self.twitter_client = twitter_client or TweepyTwitterClient()
        
        # Track daily action limits
        self.daily_likes = 0
        self.daily_replies = 0
        self.last_reset = datetime.now().date()
        
    def _check_daily_limits(self) -> Dict[str, bool]:
        """Check if daily action limits have been reached."""
        today = datetime.now().date()
        
        # Reset counters if it's a new day
        if today != self.last_reset:
            self.daily_likes = 0
            self.daily_replies = 0
            self.last_reset = today
            logger.info("Daily action counters reset")
        
        return {
            "likes_available": self.daily_likes < settings.max_likes_per_day,
            "replies_available": self.daily_replies < settings.max_replies_per_day
        }
    
    def _update_action_counters(self, actions: List[str]) -> None:
        """Update daily action counters."""
        for action in actions:
            if action == "like":
                self.daily_likes += 1
            elif action == "comment":
                self.daily_replies += 1
        
        logger.info(f"Daily actions: {self.daily_likes}/{settings.max_likes_per_day} likes, "
                   f"{self.daily_replies}/{settings.max_replies_per_day} replies")
    
    def execute_actions(self, actions: List[Tuple[RankedTweet, TweetDecision]]) -> Dict[str, List[Dict]]:
        """
        Execute a list of actions.
        
        Args:
            actions: List of (ranked_tweet, decision) tuples
            
        Returns:
            Dictionary with results grouped by action type
        """
        if not actions:
            logger.info("No actions to execute")
            return {}
        
        logger.info(f"Executing {len(actions)} actions")
        
        # Check daily limits
        limits = self._check_daily_limits()
        
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        executed_actions = []
        
        for ranked_tweet, decision in actions:
            tweet = ranked_tweet.tweet
            action = decision.decision
            
            try:
                if action == "interesting":
                    # Log interesting tweets but don't take action
                    results["successful"].append({
                        "tweet_id": tweet.id,
                        "action": "interesting",
                        "reason": "Logged as interesting"
                    })
                    logger.info(f"Tweet {tweet.id} logged as interesting")
                
                elif action == "like":
                    if not limits["likes_available"]:
                        results["skipped"].append({
                            "tweet_id": tweet.id,
                            "action": "like",
                            "reason": "Daily like limit reached"
                        })
                        logger.warning(f"Skipping like for tweet {tweet.id} - daily limit reached")
                        continue
                    
                    success = self.twitter_client.like_tweet(tweet.id)
                    if success:
                        results["successful"].append({
                            "tweet_id": tweet.id,
                            "action": "like",
                            "reason": decision.reasoning
                        })
                        executed_actions.append("like")
                        logger.info(f"Successfully liked tweet {tweet.id}")
                    else:
                        results["failed"].append({
                            "tweet_id": tweet.id,
                            "action": "like",
                            "reason": "API call failed"
                        })
                        logger.error(f"Failed to like tweet {tweet.id}")
                
                elif action == "comment":
                    if not limits["replies_available"]:
                        results["skipped"].append({
                            "tweet_id": tweet.id,
                            "action": "comment",
                            "reason": "Daily reply limit reached"
                        })
                        logger.warning(f"Skipping reply to tweet {tweet.id} - daily limit reached")
                        continue
                    
                    comment_text = decision.comment.strip()
                    if not comment_text:
                        comment_text = "Thanks for sharing!"
                    
                    success = self.twitter_client.reply_to_tweet(tweet.id, comment_text)
                    if success:
                        results["successful"].append({
                            "tweet_id": tweet.id,
                            "action": "comment",
                            "reason": decision.reasoning,
                            "comment": comment_text
                        })
                        executed_actions.append("comment")
                        logger.info(f"Successfully replied to tweet {tweet.id}")
                    else:
                        results["failed"].append({
                            "tweet_id": tweet.id,
                            "action": "comment",
                            "reason": "API call failed",
                            "comment": comment_text
                        })
                        logger.error(f"Failed to reply to tweet {tweet.id}")
                
                elif action == "dig_deeper":
                    # This will be handled by the thread agent
                    results["successful"].append({
                        "tweet_id": tweet.id,
                        "action": "dig_deeper",
                        "reason": "Queued for thread analysis"
                    })
                    logger.info(f"Tweet {tweet.id} queued for thread analysis")
                
                else:
                    logger.warning(f"Unknown action: {action}")
                    results["failed"].append({
                        "tweet_id": tweet.id,
                        "action": action,
                        "reason": "Unknown action type"
                    })
                
                # Add small delay between actions to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error executing action {action} for tweet {tweet.id}: {e}")
                results["failed"].append({
                    "tweet_id": tweet.id,
                    "action": action,
                    "reason": f"Exception: {str(e)}"
                })
        
        # Update action counters
        self._update_action_counters(executed_actions)
        
        # Log summary
        total_actions = len(actions)
        successful = len(results["successful"])
        failed = len(results["failed"])
        skipped = len(results["skipped"])
        
        logger.info(f"Action execution complete: {successful}/{total_actions} successful, "
                   f"{failed} failed, {skipped} skipped")
        
        return results
    
    def get_daily_stats(self) -> Dict[str, int]:
        """Get current daily action statistics."""
        self._check_daily_limits()  # Ensure counters are up to date
        
        return {
            "likes_today": self.daily_likes,
            "replies_today": self.daily_replies,
            "likes_remaining": settings.max_likes_per_day - self.daily_likes,
            "replies_remaining": settings.max_replies_per_day - self.daily_replies
        }
