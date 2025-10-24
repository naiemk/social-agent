"""
Supervisor agent for orchestrating the social media automation workflow.

This agent coordinates all other agents to implement the complete workflow:
search -> rank -> decide -> act -> dig deeper.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple

from google.adk.agents import BaseAgent
from sources.x_client import TwitterClient
from kernel.ranker import SemanticRanker, RankedTweet
from kernel.decider import TweetDecider, TweetDecision
from agents.search_agent import SearchAgent
from agents.kernel_agent import KernelAgent
from agents.action_agent import ActionAgent
from agents.thread_agent import ThreadAgent
from config import settings

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Supervisor agent that orchestrates the complete workflow."""
    
    def __init__(self):
        """Initialize the supervisor agent and all sub-agents."""
        super().__init__(name="supervisor_agent", description="Orchestrates social media automation")
        
        # Initialize components
        self.twitter_client = TwitterClient()
        self.ranker = SemanticRanker()
        self.decider = TweetDecider()
        
        # Initialize agents
        self.search_agent = SearchAgent(self.twitter_client, self.ranker)
        self.kernel_agent = KernelAgent(self.ranker, self.decider)
        self.action_agent = ActionAgent(self.twitter_client)
        self.thread_agent = ThreadAgent(self.twitter_client, self.decider, self.ranker)
        
        logger.info("Supervisor agent initialized with all sub-agents")
    
    def run_cycle(self, search_terms: List[str] = None) -> Dict[str, any]:
        """
        Run a complete cycle of the social media automation workflow.
        
        Args:
            search_terms: List of search terms (defaults to configured terms)
            
        Returns:
            Dictionary with results from the cycle
        """
        search_terms = search_terms or settings.search_terms
        
        logger.info(f"Starting automation cycle with search terms: {search_terms}")
        cycle_start_time = time.time()
        
        results = {
            "cycle_start_time": cycle_start_time,
            "search_terms": search_terms,
            "search_results": {},
            "kernel_results": {},
            "action_results": {},
            "thread_results": {},
            "summary": {}
        }
        
        try:
            # Step 1: Search for tweets
            logger.info("Step 1: Searching for tweets")
            search_results = self.search_agent.search_multiple_terms(search_terms)
            results["search_results"] = {
                term: len(tweets) for term, tweets in search_results.items()
            }
            
            # Combine all ranked tweets
            all_ranked_tweets = []
            for term, tweets in search_results.items():
                all_ranked_tweets.extend(tweets)
            
            if not all_ranked_tweets:
                logger.info("No tweets found in search phase")
                return results
            
            logger.info(f"Found {len(all_ranked_tweets)} total ranked tweets")
            
            # Step 2: Analyze and decide on actions
            logger.info("Step 2: Analyzing tweets and making decisions")
            action_groups = self.kernel_agent.get_actionable_tweets(all_ranked_tweets)
            results["kernel_results"] = {
                action: len(tweets) for action, tweets in action_groups.items()
            }
            
            # Step 3: Execute immediate actions
            logger.info("Step 3: Executing immediate actions")
            immediate_actions = []
            for action_type in ["like", "comment"]:
                if action_type in action_groups:
                    immediate_actions.extend(action_groups[action_type])
            
            if immediate_actions:
                action_results = self.action_agent.execute_actions(immediate_actions)
                results["action_results"] = action_results
            else:
                logger.info("No immediate actions to execute")
                results["action_results"] = {"successful": [], "failed": [], "skipped": []}
            
            # Step 4: Handle "dig_deeper" actions
            logger.info("Step 4: Analyzing conversation threads")
            dig_deeper_tweets = action_groups.get("dig_deeper", [])
            
            if dig_deeper_tweets:
                # Extract just the ranked tweets for thread analysis
                thread_tweets = [ranked_tweet for ranked_tweet, _ in dig_deeper_tweets]
                
                # Analyze threads
                thread_analysis = self.thread_agent.analyze_multiple_threads(thread_tweets)
                
                # Prioritize thread actions
                thread_actions = self.thread_agent.prioritize_thread_actions(thread_analysis)
                
                if thread_actions:
                    # Execute thread actions
                    thread_results = self.action_agent.execute_actions(thread_actions)
                    results["thread_results"] = thread_results
                else:
                    logger.info("No thread actions to execute")
                    results["thread_results"] = {"successful": [], "failed": [], "skipped": []}
            else:
                logger.info("No threads to analyze")
                results["thread_results"] = {"successful": [], "failed": [], "skipped": []}
            
            # Step 5: Generate summary
            cycle_duration = time.time() - cycle_start_time
            results["summary"] = self._generate_summary(results, cycle_duration)
            
            logger.info(f"Automation cycle completed in {cycle_duration:.2f} seconds")
            return results
            
        except Exception as e:
            logger.error(f"Error in automation cycle: {e}")
            results["error"] = str(e)
            return results
    
    def _generate_summary(self, results: Dict, cycle_duration: float) -> Dict[str, any]:
        """Generate a summary of the cycle results."""
        summary = {
            "cycle_duration": cycle_duration,
            "total_tweets_found": sum(results["search_results"].values()),
            "total_decisions_made": sum(results["kernel_results"].values()),
            "actions_executed": 0,
            "thread_actions_executed": 0
        }
        
        # Count executed actions
        if "action_results" in results:
            summary["actions_executed"] = len(results["action_results"].get("successful", []))
        
        if "thread_results" in results:
            summary["thread_actions_executed"] = len(results["thread_results"].get("successful", []))
        
        # Add daily stats
        summary["daily_stats"] = self.action_agent.get_daily_stats()
        
        return summary
    
    def validate_setup(self) -> Dict[str, bool]:
        """Validate that all components are properly configured."""
        validation_results = {
            "twitter_credentials": False,
            "model_connection": False,
            "semantic_ranker": False,
            "database_connection": False
        }
        
        try:
            # Test Twitter credentials
            validation_results["twitter_credentials"] = self.twitter_client.validate_credentials()
            
            # Test model connection
            validation_results["model_connection"] = self.decider.model_adapter.validate_connection()
            
            # Test semantic ranker
            validation_results["semantic_ranker"] = self.ranker.is_available()
            
            # Test database (would need storage module)
            validation_results["database_connection"] = True  # Placeholder
            
            logger.info(f"Setup validation results: {validation_results}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error during setup validation: {e}")
            return validation_results
    
    def get_status(self) -> Dict[str, any]:
        """Get current status of the supervisor and all agents."""
        return {
            "supervisor_status": "running",
            "daily_stats": self.action_agent.get_daily_stats(),
            "search_agent": "ready",
            "kernel_agent": "ready", 
            "action_agent": "ready",
            "thread_agent": "ready"
        }
