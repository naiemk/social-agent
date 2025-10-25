#!/usr/bin/env python3
"""
Main entry point for the social media agent.

This script provides a command-line interface for running the agent
either once or on a schedule.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings, validate_required_credentials
from scheduler import run_scheduler_forever, run_agent_once
from storage import storage

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = None):
    """Set up logging configuration."""
    log_level = log_level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/agent.log", mode="a")
        ]
    )


def run_once():
    """Run the agent once."""
    logger.info("Running agent once")
    try:
        results = run_agent_once()
        
        if "error" in results:
            logger.error(f"Agent run failed: {results['error']}")
            return 1
        
        logger.info("Agent run completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return 1


def run_scheduled():
    """Run the agent on a schedule."""
    logger.info("Starting scheduled agent")
    try:
        run_scheduler_forever()
        return 0
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error running scheduled agent: {e}")
        return 1


def validate_setup():
    """Validate the setup and configuration."""
    logger.info("Validating setup...")
    
    try:
        validate_required_credentials()
        logger.info("✓ Configuration validation passed")
    except ValueError as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        return False
    
    # Test database connection
    try:
        storage.get_daily_stats()
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False
    
    # Test Twitter API connection
    try:
        from sources.tweepy_client import TweepyTwitterClient
        client = TweepyTwitterClient()
        if client.validate_credentials():
            logger.info("✓ Twitter API connection successful")
        else:
            logger.error("✗ Twitter API connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ Twitter API connection failed: {e}")
        return False
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Social Media Agent")
    parser.add_argument(
        "--schedule", 
        action="store_true", 
        help="Run the agent on a schedule"
    )
    parser.add_argument(
        "--validate", 
        action="store_true", 
        help="Validate setup and exit"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        help="Set logging level"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    logger.info("Starting Social Media Agent")
    
    # Validate setup if requested
    if args.validate:
        if validate_setup():
            logger.info("Setup validation passed")
            return 0
        else:
            logger.error("Setup validation failed")
            return 1
    
    # Validate setup before running
    if not validate_setup():
        logger.error("Setup validation failed. Please check your configuration.")
        return 1
    
    # Run based on arguments
    if args.schedule:
        return run_scheduled()
    else:
        return run_once()


if __name__ == "__main__":
    sys.exit(main())
