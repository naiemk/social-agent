"""
Tweet decision engine using LLM for structured decision making.

This module provides a structured decision-making system that uses an LLM
to analyze tweets and determine appropriate actions.
"""

import json
import logging
import asyncio
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from models.adapters import create_adapter
from sources.tweepy_client import Tweet
from kernel.ranker import RankedTweet
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TweetDecision:
    """Structured decision result for a tweet."""
    decision: str  # "interesting", "like", "comment", "dig_deeper"
    comment: str
    confidence: float
    reasoning: str


class TweetDecider:
    """LLM-based decision engine for tweet actions."""
    
    def __init__(self, model_adapter=None):
        """Initialize the tweet decider.
        
        Args:
            model_adapter: Model adapter to use (defaults to configured adapter)
        """
        self.model_adapter = model_adapter or create_adapter()
        self.agent = self._create_decision_agent()
        self.runner = InMemoryRunner(
            agent=self.agent,
            app_name="tweet_decider",
            session_service=InMemorySessionService()
        )
        self.session_id = None
    
    def _create_decision_agent(self) -> LlmAgent:
        """Create the decision-making agent."""
        instruction = """
You are a social media analysis agent that decides on actions for tweets. 

Given a tweet's text, analyze it and decide on one of these actions:

1. "interesting" - The tweet is relevant/valuable but no immediate action needed
2. "like" - The tweet is valuable and should be liked
3. "comment" - Reply to the tweet with a helpful, positive comment
4. "dig_deeper" - The tweet hints at valuable conversation; explore replies

Guidelines:
- Be selective with "like" - only for truly valuable content
- Use "comment" sparingly - only when you can add genuine value
- "dig_deeper" for tweets that seem to have interesting discussions
- Keep comments concise, positive, and relevant
- Consider the context and tone of the original tweet

Output your decision as a JSON object with these exact keys:
{
    "decision": "interesting|like|comment|dig_deeper",
    "comment": "your reply text (empty string if not commenting)",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of your decision"
}

Be thoughtful and selective in your decisions.
"""
        
        return self.model_adapter.create_agent(
            name="tweet_decider",
            description="Decides on actions for social media tweets",
            instruction=instruction,
            output_key="decision_result"
        )
    
    async def _ensure_session(self) -> str:
        """Ensure we have an active session."""
        if self.session_id is None:
            session = await self.runner.session_service.create_session(
                app_name="tweet_decider",
                user_id="user"
            )
            self.session_id = session.id
        return self.session_id
    
    def decide(self, ranked_tweet: RankedTweet, context: Dict = None) -> Optional[TweetDecision]:
        """
        Make a decision for a ranked tweet.
        
        Args:
            ranked_tweet: The ranked tweet to analyze
            context: Additional context for decision making
            
        Returns:
            TweetDecision object or None if decision fails
        """
        try:
            # Prepare the input text
            tweet_text = ranked_tweet.tweet.text
            relevance_info = f"Relevance: {ranked_tweet.relevance_reason} (score: {ranked_tweet.score:.2f})"
            
            input_text = f"""
Tweet: {tweet_text}

{relevance_info}

Analyze this tweet and provide your decision.
"""
            
            if context:
                input_text += f"\nContext: {context}"
            
            # Run the decision agent
            session_id = asyncio.run(self._ensure_session())
            user_content = types.Content(role="user", parts=[types.Part.from_text(input_text)])
            
            final_response = None
            for event in self.runner.run(user_id="user", session_id=session_id, new_message=user_content):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text
            
            if not final_response:
                logger.warning("Decision agent returned no response")
                return None
            
            # Parse the JSON response
            try:
                result = json.loads(final_response)
                
                # Validate the response structure
                required_keys = ["decision", "comment", "confidence", "reasoning"]
                if not all(key in result for key in required_keys):
                    logger.warning(f"Decision result missing required keys: {result}")
                    return None
                
                decision = TweetDecision(
                    decision=result["decision"].lower(),
                    comment=result.get("comment", ""),
                    confidence=float(result.get("confidence", 0.0)),
                    reasoning=result.get("reasoning", "")
                )
                
                # Validate decision value
                valid_decisions = ["interesting", "like", "comment", "dig_deeper"]
                if decision.decision not in valid_decisions:
                    logger.warning(f"Invalid decision: {decision.decision}")
                    return None
                
                logger.debug(f"Decision for tweet {ranked_tweet.tweet.id}: {decision.decision} (confidence: {decision.confidence:.2f})")
                return decision
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse decision JSON: {e}")
                logger.debug(f"Raw response: {final_response}")
                return None
                
        except Exception as e:
            logger.error(f"Error making decision for tweet: {e}")
            return None
    
    def batch_decide(self, ranked_tweets: List[RankedTweet], 
                    context: Dict = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """
        Make decisions for multiple ranked tweets.
        
        Args:
            ranked_tweets: List of ranked tweets to analyze
            context: Additional context for decision making
            
        Returns:
            List of tuples (ranked_tweet, decision) for successful decisions
        """
        results = []
        
        for ranked_tweet in ranked_tweets:
            decision = self.decide(ranked_tweet, context)
            if decision:
                results.append((ranked_tweet, decision))
            else:
                logger.warning(f"Failed to make decision for tweet {ranked_tweet.tweet.id}")
        
        logger.info(f"Made decisions for {len(results)} out of {len(ranked_tweets)} tweets")
        return results
    
    def filter_by_confidence(self, decisions: List[Tuple[RankedTweet, TweetDecision]], 
                           min_confidence: float = None) -> List[Tuple[RankedTweet, TweetDecision]]:
        """Filter decisions by confidence threshold."""
        min_confidence = min_confidence or settings.kernel_confidence_threshold
        
        filtered = [
            (rt, d) for rt, d in decisions 
            if d.confidence >= min_confidence
        ]
        
        logger.info(f"Filtered {len(decisions)} decisions to {len(filtered)} by confidence >= {min_confidence}")
        return filtered
