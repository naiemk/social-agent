"""
Scheduler system for running the social media agent periodically.

This module provides a robust scheduling system using APScheduler with
jitter, rate limiting, and error handling.
"""

import logging
import random
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    BackgroundScheduler = None
    CronTrigger = None

from agents.supervisor import SupervisorAgent
from storage import storage
from config import settings

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Scheduler for running the social media agent with proper error handling."""
    
    def __init__(self, supervisor_agent: SupervisorAgent = None):
        """Initialize the scheduler.
        
        Args:
            supervisor_agent: SupervisorAgent instance to run
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError("APScheduler is required for scheduling functionality")
        
        self.supervisor = supervisor_agent or SupervisorAgent()
        self.scheduler = BackgroundScheduler()
        self.job_id = "social_media_agent_job"
        self.is_running = False
        
        # Set up event listeners
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        logger.info("Agent scheduler initialized")
    
    def _job_executed_listener(self, event):
        """Handle successful job execution."""
        logger.info(f"Job {event.job_id} executed successfully")
        
        # Update daily stats
        storage.update_daily_stats({
            "tweets_processed": 1,
            "errors_encountered": 0
        })
    
    def _job_error_listener(self, event):
        """Handle job execution errors."""
        logger.error(f"Job {event.job_id} failed with error: {event.exception}")
        
        # Update daily stats
        storage.update_daily_stats({
            "errors_encountered": 1
        })
    
    def _run_agent_cycle(self) -> Dict[str, Any]:
        """Run a single cycle of the agent and return results."""
        logger.info("Starting scheduled agent cycle")
        cycle_start = datetime.now()
        
        try:
            # Run the supervisor cycle
            results = self.supervisor.run_cycle()
            
            # Log the cycle completion
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"Agent cycle completed in {cycle_duration:.2f} seconds")
            
            # Update storage with cycle results
            if "summary" in results:
                summary = results["summary"]
                stats_update = {
                    "tweets_processed": summary.get("total_tweets_found", 0),
                    "likes_given": summary.get("actions_executed", 0),
                    "replies_sent": summary.get("thread_actions_executed", 0)
                }
                storage.update_daily_stats(stats_update)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in scheduled agent cycle: {e}")
            
            # Update error stats
            storage.update_daily_stats({
                "errors_encountered": 1
            })
            
            return {"error": str(e)}
    
    def _generate_jitter(self, base_minute: int = 0) -> int:
        """Generate pixel jitter to avoid predictable patterns.
        
        Args:
            base_minute: Base minute for scheduling
            
        Returns:
            Jittered minute value
        """
        # Add random jitter of ±10 minutes
        jitter = random.randint(-10, 10)
        jittered_minute = base_minute + jitter
        
        # Ensure minute is within valid range (0-59)
        return max(0, min(59, jittered_minute))
    
    def start_scheduler(self, schedule_hours: str = None, schedule_minutes: str = None) -> None:
        """Start the scheduler with the specified schedule.
        
        Args:
            schedule_hours: Cron expression for hours (e.g., "*/3" for every 3 hours)
            schedule_minutes: Specific minutes or None for random jitter
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        schedule_hours = schedule_hours or settings.schedule_hours
        
        # Generate jittered minute if not specified
        if schedule_minutes is None:
            jittered_minute = self._generate_jitter()
            logger.info(f"Generated jittered minute: {jittered_minute}")
        else:
            jittered_minute = schedule_minutes
        
        # Create cron trigger
        trigger = CronTrigger(
            hour=schedule_hours,
            minute=jittered_minute,
            second=0
        )
        
        # Add the job
        self.scheduler.add_job(
            func=self._run_agent_cycle,
            trigger=trigger,
            id=self.job_id,
            name="Social Media Agent Cycle",
            max_instances=1,  # Prevent overlapping executions
            coalesce=True,    # Skip missed executions
            misfire_grace_time=300  # 5 minutes grace time
        )
        
        # Start the scheduler
        self.scheduler.start()
        self.is_running = True
        
        logger.info(f"Scheduler started with schedule: every {schedule_hours} hours at minute {jittered_minute}")
        
        # Log next run time
        next_run = self.scheduler.get_job(self.job_id).next_run_time
        logger.info(f"Next scheduled run: {next_run}")
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Scheduler stopped")
    
    def run_once(self) -> Dict[str, Any]:
        """Run the agent once immediately (for testing or manual execution)."""
        logger.info("Running agent cycle once")
        return self._run_agent_cycle()
    
    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        if not self.is_running:
            return None
        
        job = self.scheduler.get_job(self.job_id)
        return job.next_run_time if job else None
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        if not self.is_running:
            return {
                "running": False,
                "next_run": None,
                "job_count": 0
            }
        
        job = self.scheduler.get_job(self.job_id)
        return {
            "running": True,
            "next_run": job.next_run_time if job else None,
            "job_count": len(self.scheduler.get_jobs()),
            "job_id": self.job_id
        }
    
    def update_schedule(self, schedule_hours: str, schedule_minutes: str = None) -> None:
        """Update the scheduler with a new schedule.
        
        Args:
            schedule_hours: New cron expression for hours
            schedule_minutes: New minutes or None for random jitter
        """
        if not self.is_running:
            logger.warning("Cannot update schedule - scheduler is not running")
            return
        
        # Remove existing job
        self.scheduler.remove_job(self.job_id)
        
        # Generate new jittered minute if not specified
        if schedule_minutes is None:
            jittered_minute = self._generate_jitter()
        else:
            jittered_minute = schedule_minutes
        
        # Create new trigger
        trigger = CronTrigger(
            hour=schedule_hours,
            minute=jittered_minute,
            second=0
        )
        
        # Add updated job
        self.scheduler.add_job(
            func=self._run_agent_cycle,
            trigger=trigger,
            id=self.job_id,
            name="Social Media Agent Cycle",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300
        )
        
        logger.info(f"Schedule updated: every {schedule_hours} hours at minute {jittered_minute}")
        
        # Log next run time
        next_run = self.scheduler.get_job(self.job_id).next_run_time
        logger.info(f"Next scheduled run: {next_run}")


def run_scheduler_forever(schedule_hours: str = None, schedule_minutes: str = None) -> None:
    """Run the scheduler indefinitely with the specified schedule.
    
    Args:
        schedule_hours: Cron expression for hours
        schedule_minutes: Specific minutes or None for random jitter
    """
    if not APSCHEDULER_AVAILABLE:
        logger.error("APScheduler is not available. Cannot run scheduler.")
        return
    
    try:
        scheduler = AgentScheduler()
        scheduler.start_scheduler(schedule_hours, schedule_minutes)
        
        logger.info("Scheduler running. Press Ctrl+C to stop.")
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Stopping scheduler...")
            scheduler.stop_scheduler()
            
    except Exception as e:
        logger.error(f"Error running scheduler: {e}")
        raise


def run_agent_once() -> Dict[str, Any]:
    """Run the agent once immediately.
    
    Returns:
        Results from the agent cycle
    """
    try:
        scheduler = AgentScheduler()
        return scheduler.run_once()
    except Exception as e:
        logger.error(f"Error running agent once: {e}")
        return {"error": str(e)}
