"""Data sources for social media platforms."""

# Import TweepyTwitterClient first to avoid config dependency issues
from .tweepy_client import TweepyTwitterClient

# Import TwitterClient only when needed to avoid config validation errors
def get_twitter_client():
    """Get the original TwitterClient (requests-based)."""
    from .x_client import TwitterClient
    return TwitterClient

__all__ = ["TweepyTwitterClient", "get_twitter_client"]
