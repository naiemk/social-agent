"""
social_media_agent.py
======================

This module implements a minimal social‑media automation agent built using
Google's Agent Development Kit (ADK).  The goal of this script is to log into
the X (formerly Twitter) API, search for interesting tweets based on a set of
query terms, analyse each tweet using a small language model agent and then
either like the tweet, reply with a generated comment or dig deeper into the
conversation thread.  The agent is orchestrated with ADK and designed to run
entirely on a single machine (for example a personal laptop).

Key features
------------

* **Minimal dependencies** – only the `google‑adk` library, `requests`,
  Python's built‑in `asyncio`, `sqlite3` and `apscheduler` are used.  If you
  wish to swap out models, you can do so by changing the `MODEL_NAME`
  environment variable.
* **Environment based configuration** – all secrets such as your Twitter
  bearer token, your own user ID and your model API key are read from
  environment variables.  See the documentation at the end of this file for
  details.
* **ADK integration** – the kernel that classifies tweets is defined as an
  `LlmAgent` from ADK.  The classification logic is encapsulated in the
  agent's instruction.  The agent returns a JSON object with fields
  `decision` (one of “interesting”, “like”, “comment” or “dig_deeper”) and
  `comment` (a short reply when appropriate).
* **Scheduling support** – an optional APScheduler job can be configured to
  run the agent multiple times per day.

The code is intentionally compact to serve as a solid starting point; you can
extend it to support additional social media platforms such as Instagram by
adding new tool functions and reusing the same kernel agent.  For further
background on ADK and its usage, consult the official documentation and
examples【161930785819024†L246-L260】【100028572330983†L150-L198】.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

import requests

# APScheduler is an optional dependency used for scheduling repeated runs of
# the agent.  When the library is unavailable (for example in a testing
# environment), the scheduler parts of this script will gracefully degrade.
try:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
except ImportError:
    BackgroundScheduler = None  # type: ignore

# ADK imports.  The ADK library exposes agent types and a lightweight in‑memory
# runner for executing them directly in Python【100028572330983†L150-L208】.
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration and constants
# ---------------------------------------------------------------------------

# Read configuration from environment variables.  Provide sensible defaults
# where possible; however, for API credentials a missing variable will raise
# immediately.
TWITTER_BEARER_TOKEN: str = os.environ.get("TWITTER_BEARER_TOKEN", "")
"""A Twitter bearer token for authentication.  You can generate one by
registering an application on the X Developer Portal.  See
https://developer.x.com/ for details.  Must be set in your environment.
"""

TWITTER_USER_ID: str = os.environ.get("TWITTER_USER_ID", "")
"""Your user ID on X.  This is required for liking tweets.  You can look
it up using the `/2/users/me` endpoint once you have a bearer token.  Must
be set in your environment.
"""

SEARCH_TERMS: List[str] = (
    os.environ.get("SEARCH_TERMS", "python langchain agent").split(",")
    if os.environ.get("SEARCH_TERMS")
    else ["python", "AI", "agent"]
)
"""List of query terms to search for when looking for tweets.  Provide
comma‑separated values in the SEARCH_TERMS environment variable.  A few
generic defaults are used if unspecified.
"""

MODEL_NAME: str = os.environ.get("MODEL_NAME", "gemini-2.5-pro")
"""The model identifier used by the LLM agent.  Examples include
"gemini-2.5-pro" for Google Gemini or "gpt-4o" for OpenAI.  You must
configure the corresponding API key in your environment (see `GOOGLE_API_KEY`
or `OPENAI_API_KEY`).【161930785819024†L320-L341】
"""

MAX_TWEETS_PER_RUN: int = int(os.environ.get("MAX_TWEETS_PER_RUN", "10"))
"""Maximum number of tweets to process in a single run.  Keeping this
value modest helps stay within the free tier limits for Twitter's API
【100028572330983†L150-L198】.
"""

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/tmp/agent_state.db")
"""Path to the SQLite database used to record processed tweets.  This
prevents acting on the same tweet multiple times.
"""

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
"""Logging level.  Use "DEBUG" for verbose output.
"""

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

if not TWITTER_BEARER_TOKEN:
    logger.warning(
        "TWITTER_BEARER_TOKEN is not set. Twitter API calls will fail. "
        "Please set this environment variable before running the agent."
    )

if not TWITTER_USER_ID:
    logger.warning(
        "TWITTER_USER_ID is not set. Like actions will be skipped. "
        "Set this environment variable to your X user ID."
    )

# ---------------------------------------------------------------------------
# Twitter API helper functions
# ---------------------------------------------------------------------------

def twitter_headers() -> Dict[str, str]:
    """Return HTTP headers required for Twitter API requests."""
    return {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
        "Content-Type": "application/json",
    }


def search_tweets(query: str, max_results: int = 10) -> List[Dict]:
    """Perform a recent search on Twitter for the given query.

    Args:
        query: The search terms.
        max_results: Maximum number of tweets to return (1–100).

    Returns:
        A list of tweet objects returned by the Twitter API.  Each object
        contains at least `id` and `text` keys.
    """
    if not TWITTER_BEARER_TOKEN:
        logger.error("Cannot search tweets: TWITTER_BEARER_TOKEN is missing.")
        return []
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": query,
        "max_results": max_results,
        "tweet.fields": "conversation_id,author_id"
    }
    try:
        response = requests.get(url, headers=twitter_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as exc:
        logger.error(f"Error searching tweets: {exc}")
        return []


def like_tweet(tweet_id: str) -> None:
    """Like a tweet using the authenticated user account.

    Args:
        tweet_id: The ID of the tweet to like.

    Notes:
        On the free tier, the number of likes you can perform per month is
        limited【100028572330983†L150-L198】.  Errors are logged but not raised.
    """
    if not (TWITTER_BEARER_TOKEN and TWITTER_USER_ID):
        logger.info(f"Skipping like for tweet {tweet_id} – missing credentials.")
        return
    url = f"https://api.twitter.com/2/users/{TWITTER_USER_ID}/likes"
    payload = {"tweet_id": tweet_id}
    try:
        resp = requests.post(url, headers=twitter_headers(), json=payload)
        if resp.status_code == 200 or resp.status_code == 201:
            logger.info(f"Liked tweet {tweet_id}.")
        else:
            logger.warning(f"Failed to like tweet {tweet_id}: {resp.status_code} {resp.text}")
    except Exception as exc:
        logger.error(f"Error liking tweet {tweet_id}: {exc}")


def reply_to_tweet(tweet_id: str, text: str) -> None:
    """Reply to a tweet with the given text.

    Args:
        tweet_id: The ID of the tweet you are replying to.
        text: The reply content.

    Notes:
        Replies are created by posting a new tweet with a `reply` object that
        references the original tweet.  The API call is logged rather than
        raising on failure.
    """
    if not TWITTER_BEARER_TOKEN:
        logger.info(f"Skipping reply to tweet {tweet_id} – missing credentials.")
        return
    url = "https://api.twitter.com/2/tweets"
    payload = {
        "text": text,
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }
    try:
        resp = requests.post(url, headers=twitter_headers(), json=payload)
        if resp.status_code in (200, 201):
            logger.info(f"Replied to tweet {tweet_id}: {text[:30]}…")
        else:
            logger.warning(f"Failed to reply to tweet {tweet_id}: {resp.status_code} {resp.text}")
    except Exception as exc:
        logger.error(f"Error replying to tweet {tweet_id}: {exc}")


def get_conversation_replies(conversation_id: str, max_results: int = 20) -> List[Dict]:
    """Retrieve replies in a conversation thread for a given conversation ID.

    Args:
        conversation_id: The conversation ID of the root tweet.
        max_results: Maximum number of replies to retrieve.

    Returns:
        A list of tweet objects representing the replies.
    """
    if not TWITTER_BEARER_TOKEN:
        logger.error("Cannot retrieve replies: TWITTER_BEARER_TOKEN is missing.")
        return []
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": f"conversation_id:{conversation_id}",
        "max_results": max_results,
        "tweet.fields": "conversation_id,author_id"
    }
    try:
        response = requests.get(url, headers=twitter_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as exc:
        logger.error(f"Error retrieving conversation replies: {exc}")
        return []


# ---------------------------------------------------------------------------
# Database helper functions
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """Initialise the SQLite database and return a connection.

    The database contains a single table `seen_tweets` with a primary key on
    `tweet_id`.  A simple index prevents duplicate actions for the same tweet.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seen_tweets (tweet_id TEXT PRIMARY KEY, processed_at TEXT)"
    )
    conn.commit()
    return conn


def has_seen(conn: sqlite3.Connection, tweet_id: str) -> bool:
    """Check whether a tweet ID has already been processed."""
    cur = conn.execute("SELECT 1 FROM seen_tweets WHERE tweet_id = ?", (tweet_id,))
    return cur.fetchone() is not None


def mark_seen(conn: sqlite3.Connection, tweet_id: str) -> None:
    """Record that a tweet has been processed."""
    conn.execute(
        "INSERT OR IGNORE INTO seen_tweets (tweet_id, processed_at) VALUES (?, ?)",
        (tweet_id, datetime.utcnow().isoformat()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Kernel: define the classification agent using ADK
# ---------------------------------------------------------------------------

def create_kernel_agent() -> LlmAgent:
    """Create and return the kernel agent responsible for classifying tweets.

    The agent will consume a tweet's text (plain string) and produce a short
    JSON response containing two fields:

    * `decision` – must be one of "interesting", "like", "comment" or
      "dig_deeper".
    * `comment` – when the decision is "comment", this field should contain
      the text to reply with.  For other decisions, it may be an empty string.

    You can modify the instruction string below to tune the behaviour of the
    kernel.  The instruction contains a few example cases to guide the model
    (few‑shot examples) and constraints for the JSON output.【161930785819024†L320-L341】
    """
    instruction = (
        "You are a social media analysis agent.  You will be given the text of a "
        "tweet.  Carefully read the tweet and decide which of the following "
        "actions should be taken: \n"
        "1. \"interesting\" – the tweet is relevant but no immediate action is needed.\n"
        "2. \"like\" – the tweet is valuable and should be liked.\n"
        "3. \"comment\" – reply to the tweet with a concise, positive comment.  Also "
        "provide the comment text.\n"
        "4. \"dig_deeper\" – the tweet hints at a valuable thread; the agent should "
        "read the conversation replies before acting.\n"
        "\nOutput your answer strictly as a JSON object with two keys: \"decision\" "
        "and \"comment\".  For example: {\"decision\": \"like\", \"comment\": \"Great post!\"}.\n"
        "Do not include any additional keys or text outside the JSON."
    )
    kernel_agent = LlmAgent(
        model=MODEL_NAME,
        name="kernel_agent",
        description="Classifies tweets and optionally generates comments.",
        instruction=instruction,
        # The output_key stores the final response in the session state.  We
        # choose a descriptive key name.
        output_key="kernel_result",
    )
    return kernel_agent


class KernelRunner:
    """Encapsulates the ADK runner and session for the kernel agent.

    Running an ADK agent requires a `Runner` and a `Session` service.  This
    helper class hides the boilerplate so that classification can be called
    synchronously from regular Python code.  Internally it manages a single
    in‑memory session.
    """

    def __init__(self, agent: LlmAgent, app_name: str = "twitter_kernel_app") -> None:
        self.agent = agent
        self.app_name = app_name
        self.session_service = InMemorySessionService()
        # Create runner
        self.runner = InMemoryRunner(agent=agent, app_name=app_name, session_service=self.session_service)
        # Create a session immediately
        self.session_id = None

    def ensure_session(self) -> str:
        """Ensure that a session exists and return its ID."""
        if self.session_id is None:
            session = asyncio.run(self.session_service.create_session(app_name=self.app_name, user_id="user"))
            self.session_id = session.id
        return self.session_id

    def classify(self, tweet_text: str) -> Optional[Dict[str, str]]:
        """Run the kernel agent on a single tweet and return the JSON decision.

        Args:
            tweet_text: The raw text of the tweet to classify.

        Returns:
            A dictionary with keys "decision" and "comment" if classification
            succeeds.  Returns None if the agent fails to return a JSON result.
        """
        session_id = self.ensure_session()
        user_content = types.Content(role="user", parts=[types.Part.from_text(tweet_text)])
        final_response: Optional[str] = None
        # Run the agent.  Iterate over events to collect the final response.
        for event in self.runner.run(user_id="user", session_id=session_id, new_message=user_content):
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text
        if not final_response:
            logger.warning("Kernel agent returned no final response for tweet.")
            return None
        # Parse the JSON safely
        try:
            result = json.loads(final_response)
            if isinstance(result, dict) and "decision" in result and "comment" in result:
                return {"decision": result.get("decision", ""), "comment": result.get("comment", "")}
            else:
                logger.warning(f"Kernel result missing expected keys: {result}")
                return None
        except json.JSONDecodeError:
            logger.warning(f"Kernel result is not valid JSON: {final_response}")
            return None


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def process_tweets_once(conn: sqlite3.Connection, kernel: KernelRunner) -> None:
    """Perform a single run of the agent: search, classify and act on tweets.

    This function searches Twitter for each term in `SEARCH_TERMS`, takes up
    to `MAX_TWEETS_PER_RUN` results, and processes them using the kernel
    agent.  For each tweet, the decision returned by the kernel dictates the
    next action:

    * `interesting` – the tweet is logged but no API action is taken.
    * `like` – the tweet is liked via the Twitter API.
    * `comment` – the tweet is replied to with the provided comment.
    * `dig_deeper` – the agent retrieves replies in the conversation thread
      and classifies them, potentially liking or commenting on those replies.

    The function keeps track of processed tweets in a SQLite database to avoid
    acting on the same tweet repeatedly.  Any errors encountered during
    network calls are logged but do not halt processing.
    """
    for term in SEARCH_TERMS:
        # Compose a query; filter out retweets and replies to reduce noise.
        query = f"{term} -is:retweet"
        tweets = search_tweets(query, max_results=MAX_TWEETS_PER_RUN)
        logger.info(f"Found {len(tweets)} tweets for query '{term}'.")
        for tweet in tweets:
            tweet_id = tweet.get("id")
            text = tweet.get("text", "")
            conversation_id = tweet.get("conversation_id")
            if not tweet_id or not text:
                continue
            if has_seen(conn, tweet_id):
                logger.debug(f"Skipping already processed tweet {tweet_id}.")
                continue
            # Mark as seen immediately to avoid duplicate processing even if
            # subsequent actions fail.
            mark_seen(conn, tweet_id)
            logger.info(f"Processing tweet {tweet_id}: {text[:50]}…")
            result = kernel.classify(text)
            if result is None:
                logger.warning(f"Kernel classification failed for tweet {tweet_id}.")
                continue
            decision = result["decision"].lower()
            comment = result["comment"]
            # Dispatch action based on decision
            if decision == "interesting":
                logger.info(f"Tweet {tweet_id} considered interesting – no action taken.")
            elif decision == "like":
                like_tweet(tweet_id)
            elif decision == "comment":
                # Use the model's suggestion or fallback to a default
                reply_text = comment.strip() or "Thanks for sharing!"
                reply_to_tweet(tweet_id, reply_text)
            elif decision == "dig_deeper":
                logger.info(f"Digging deeper into conversation for tweet {tweet_id}…")
                if conversation_id:
                    replies = get_conversation_replies(conversation_id)
                    # Shuffle replies slightly to avoid always processing the same order
                    random.shuffle(replies)
                    for reply in replies[:MAX_TWEETS_PER_RUN]:
                        rid = reply.get("id")
                        rtext = reply.get("text", "")
                        if not rid or has_seen(conn, rid):
                            continue
                        mark_seen(conn, rid)
                        logger.info(f"Processing reply {rid}: {rtext[:50]}…")
                        rresult = kernel.classify(rtext)
                        if rresult:
                            rdecision = rresult["decision"].lower()
                            rcomment = rresult["comment"]
                            if rdecision == "like":
                                like_tweet(rid)
                            elif rdecision == "comment":
                                reply_to_tweet(rid, rcomment.strip() or "Interesting point!")
                            # We ignore nested dig_deeper to prevent infinite recursion.
                else:
                    logger.info("Conversation ID missing – cannot dig deeper.")
            else:
                logger.warning(f"Unknown decision '{decision}' for tweet {tweet_id}.")


def run_scheduler() -> None:
    """Set up and start the APScheduler to run the agent periodically.

    The schedule can be customised via environment variables.  By default,
    the job runs every three hours at a random offset to avoid creating
    predictable patterns.  To disable scheduling, set the `DISABLE_SCHEDULER`
    environment variable to any non‑empty value.
    """
    if os.environ.get("DISABLE_SCHEDULER"):
        logger.info("Scheduler disabled.  Exiting after a single run.")
        return
    if BackgroundScheduler is None:
        logger.error(
            "APScheduler is not installed.  Install `apscheduler` or set the "
            "RUN_FOREVER environment variable to use scheduling."
        )
        return
    scheduler = BackgroundScheduler()
    # Spread jobs evenly: run every 3 hours with a random minute offset (0–59).
    def job_wrapper() -> None:
        conn = init_db()
        kernel_agent = create_kernel_agent()
        kernel_runner = KernelRunner(kernel_agent)
        process_tweets_once(conn, kernel_runner)
        conn.close()
    # Choose minutes randomly for initial jitter
    minute = random.randint(0, 59)
    scheduler.add_job(job_wrapper, "cron", hour="*/3", minute=minute)
    scheduler.start()
    logger.info(
        f"Scheduler started – job will run every 3 hours at minute {minute}."
    )
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


def main() -> None:
    """Entry point for running the agent either once or on a schedule.

    When executed directly, this function initialises the database, creates
    the kernel agent and runs a single processing cycle.  If the environment
    variable `RUN_FOREVER` is set, the APScheduler will be started instead.
    """
    conn = init_db()
    kernel_agent = create_kernel_agent()
    kernel_runner = KernelRunner(kernel_agent)
    # Run once immediately
    process_tweets_once(conn, kernel_runner)
    conn.close()
    # Start the scheduler if requested
    if os.environ.get("RUN_FOREVER"):
        run_scheduler()


if __name__ == "__main__":
    main()