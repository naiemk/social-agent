"""
Storage system for managing SQLite database and action logging.

This module provides a comprehensive storage system for tracking processed tweets,
action history, rate limiting, and system statistics.
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, asdict

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProcessedTweet:
    """Represents a processed tweet record."""
    tweet_id: str
    processed_at: str
    action_taken: str
    confidence: float
    reasoning: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class ActionLog:
    """Represents an action log entry."""
    id: int
    tweet_id: str
    action_type: str
    executed_at: str
    success: bool
    details: str
    error_message: Optional[str] = None


class StorageManager:
    """Manages SQLite database operations and data persistence."""
    
    def __init__(self, db_path: str = None):
        """Initialize the storage manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path or settings.database_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create processed tweets table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processed_tweets (
                        tweet_id TEXT PRIMARY KEY,
                        processed_at TEXT NOT NULL,
                        action_taken TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        reasoning TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT
                    )
                """)
                
                # Create action log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS action_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        executed_at TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        details TEXT NOT NULL,
                        error_message TEXT
                    )
                """)
                
                # Create daily stats table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_stats (
                        date TEXT PRIMARY KEY,
                        tweets_processed INTEGER DEFAULT 0,
                        likes_given INTEGER DEFAULT 0,
                        replies_sent INTEGER DEFAULT 0,
                        threads_analyzed INTEGER DEFAULT 0,
                        errors_encountered INTEGER DEFAULT 0
                    )
                """)
                
                # Create rate limit tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rate_limits (
                        action_type TEXT PRIMARY KEY,
                        daily_count INTEGER DEFAULT 0,
                        last_reset_date TEXT NOT NULL,
                        hourly_count INTEGER DEFAULT 0,
                        last_hour_reset TEXT NOT NULL
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processed_tweets_date 
                    ON processed_tweets(processed_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_action_log_date 
                    ON action_log(executed_at)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_action_log_tweet_id 
                    ON action_log(tweet_id)
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def has_processed_tweet(self, tweet_id: str) -> bool:
        """Check if a tweet has already been processed.
        
        Args:
            tweet_id: The tweet ID to check
            
        Returns:
            True if the tweet has been processed, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM processed_tweets WHERE tweet_id = ?",
                    (tweet_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking processed tweet {tweet_id}: {e}")
            return False
    
    def mark_tweet_processed(self, processed_tweet: ProcessedTweet) -> None:
        """Mark a tweet as processed.
        
        Args:
            processed_tweet: ProcessedTweet object to store
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO processed_tweets 
                    (tweet_id, processed_at, action_taken, confidence, reasoning, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    processed_tweet.tweet_id,
                    processed_tweet.processed_at,
                    processed_tweet.action_taken,
                    processed_tweet.confidence,
                    processed_tweet.reasoning,
                    processed_tweet.success,
                    processed_tweet.error_message
                ))
                conn.commit()
                logger.debug(f"Marked tweet {processed_tweet.tweet_id} as processed")
        except Exception as e:
            logger.error(f"Error marking tweet as processed: {e}")
    
    def log_action(self, tweet_id: str, action_type: str, success: bool, 
                   details: str, error_message: str = None) -> int:
        """Log an action to the database.
        
        Args:
            tweet_id: ID of the tweet the action was performed on
            action_type: Type of action (like, comment, etc.)
            success: Whether the action was successful
            details: Additional details about the action
            error_message: Error message if the action failed
            
        Returns:
            ID of the logged action
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO action_log 
                    (tweet_id, action_type, executed_at, success, details, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tweet_id,
                    action_type,
                    datetime.now().isoformat(),
                    success,
                    details,
                    error_message
                ))
                conn.commit()
                action_id = cursor.lastrowid
                logger.debug(f"Logged action {action_id} for tweet {tweet_id}")
                return action_id
        except Exception as e:
            logger.error(f"Error logging action: {e}")
            return -1
    
    def get_daily_stats(self, target_date: date = None) -> Dict[str, int]:
        """Get daily statistics for a specific date.
        
        Args:
            target_date: Date to get stats for (defaults to today)
            
        Returns:
            Dictionary with daily statistics
        """
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tweets_processed, likes_given, replies_sent, 
                           threads_analyzed, errors_encountered
                    FROM daily_stats WHERE date = ?
                """, (date_str,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        "tweets_processed": result[0],
                        "likes_given": result[1],
                        "replies_sent": result[2],
                        "threads_analyzed": result[3],
                        "errors_encountered": result[4]
                    }
                else:
                    return {
                        "tweets_processed": 0,
                        "likes_given": 0,
                        "replies_sent": 0,
                        "threads_analyzed": 0,
                        "errors_encountered": 0
                    }
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return {}
    
    def update_daily_stats(self, stats_update: Dict[str, int], target_date: date = None) -> None:
        """Update daily statistics.
        
        Args:
            stats_update: Dictionary with stat updates
            target_date: Date to update stats for (defaults to today)
        """
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current stats
                current_stats = self.get_daily_stats(target_date)
                
                # Update stats
                for key, increment in stats_update.items():
                    if key in current_stats:
                        current_stats[key] += increment
                
                # Store updated stats
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_stats 
                    (date, tweets_processed, likes_given, replies_sent, 
                     threads_analyzed, errors_encountered)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    current_stats["tweets_processed"],
                    current_stats["likes_given"],
                    current_stats["replies_sent"],
                    current_stats["threads_analyzed"],
                    current_stats["errors_encountered"]
                ))
                conn.commit()
                logger.debug(f"Updated daily stats for {date_str}")
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")
    
    def get_rate_limit_status(self, action_type: str) -> Dict[str, Any]:
        """Get current rate limit status for an action type.
        
        Args:
            action_type: Type of action to check
            
        Returns:
            Dictionary with rate limit information
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT daily_count, last_reset_date, hourly_count, last_hour_reset
                    FROM rate_limits WHERE action_type = ?
                """, (action_type,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        "daily_count": result[0],
                        "last_reset_date": result[1],
                        "hourly_count": result[2],
                        "last_hour_reset": result[3]
                    }
                else:
                    return {
                        "daily_count": 0,
                        "last_reset_date": date.today().isoformat(),
                        "hourly_count": 0,
                        "last_hour_reset": datetime.now().isoformat()
                    }
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {}
    
    def update_rate_limit(self, action_type: str, increment: int = 1) -> None:
        """Update rate limit counters.
        
        Args:
            action_type: Type of action to update
            increment: Amount to increment the counter
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current status
                status = self.get_rate_limit_status(action_type)
                current_date = date.today().isoformat()
                current_hour = datetime.now().strftime("%Y-%m-%d %H:00:00")
                
                # Reset daily counter if needed
                if status["last_reset_date"] != current_date:
                    status["daily_count"] = 0
                    status["last_reset_date"] = current_date
                
                # Reset hourly counter if needed
                if status["last_hour_reset"] != current_hour:
                    status["hourly_count"] = 0
                    status["last_hour_reset"] = current_hour
                
                # Update counters
                status["daily_count"] += increment
                status["hourly_count"] += increment
                
                # Store updated status
                cursor.execute("""
                    INSERT OR REPLACE INTO rate_limits 
                    (action_type, daily_count, last_reset_date, hourly_count, last_hour_reset)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    action_type,
                    status["daily_count"],
                    status["last_reset_date"],
                    status["hourly_count"],
                    status["last_hour_reset"]
                ))
                conn.commit()
                logger.debug(f"Updated rate limit for {action_type}")
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")
    
    def get_recent_actions(self, limit: int = 100) -> List[ActionLog]:
        """Get recent actions from the log.
        
        Args:
            limit: Maximum number of actions to return
            
        Returns:
            List of recent ActionLog objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, tweet_id, action_type, executed_at, success, details, error_message
                    FROM action_log
                    ORDER BY executed_at DESC
                    LIMIT ?
                """, (limit,))
                
                actions = []
                for row in cursor.fetchall():
                    action = ActionLog(
                        id=row[0],
                        tweet_id=row[1],
                        action_type=row[2],
                        executed_at=row[3],
                        success=bool(row[4]),
                        details=row[5],
                        error_message=row[6]
                    )
                    actions.append(action)
                
                return actions
        except Exception as e:
            logger.error(f"Error getting recent actions: {e}")
            return []
    
    def get_processed_tweets_count(self, days: int = 7) -> int:
        """Get count of processed tweets in the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Count of processed tweets
        """
        try:
            cutoff_date = (datetime.now().date() - 
                          timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM processed_tweets 
                    WHERE processed_at >= ?
                """, (cutoff_date,))
                
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting processed tweets count: {e}")
            return 0
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """Clean up old data from the database.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        try:
            cutoff_date = (datetime.now().date() - 
                          timedelta(days=days_to_keep)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up old processed tweets
                cursor.execute("""
                    DELETE FROM processed_tweets WHERE processed_at < ?
                """, (cutoff_date,))
                
                # Clean up old action logs
                cursor.execute("""
                    DELETE FROM action_log WHERE executed_at < ?
                """, (cutoff_date,))
                
                conn.commit()
                logger.info(f"Cleaned up data older than {days_to_keep} days")
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")


# Global storage manager instance
storage = StorageManager()
