"""
Scheduling System for Unified E-commerce Product Data Aggregator
"""
import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
import json
import os
from dataclasses import dataclass, asdict
import subprocess
import platform

logger = logging.getLogger(__name__)

@dataclass
class ScheduledJob:
    """Represents a scheduled job"""
    job_id: str
    name: str
    job_type: str  # 'scraping', 'deduplication', 'sync', 'maintenance'
    target: str  # platform, category, or specific identifier
    schedule_type: str  # 'hourly', 'daily', 'weekly', 'cron'
    schedule_value: str  # cron expression or time specification
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = None
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.config is None:
            self.config = {}

class JobScheduler:
    """
    Advanced job scheduler with cron job capability for cloud VM deployment.
    Manages scheduled scraping, deduplication, and maintenance tasks.
    """
    
    def __init__(self, db_manager, scraping_manager, sync_manager):
        self.db_manager = db_manager
        self.scraping_manager = scraping_manager
        self.sync_manager = sync_manager
        self.scheduled_jobs: Dict[str, ScheduledJob] = {}
        self.is_running = False
        self.scheduler_thread = None
        self.job_callbacks: List[Callable] = []
        self.jobs_file = 'scheduled_jobs.json'
        
        # Load existing jobs
        self._load_jobs()
    
    def start_scheduler(self):
        """Start the job scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Job scheduler started")
    
    def stop_scheduler(self):
        """Stop the job scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Job scheduler stopped")
    
    def add_job(self, job: ScheduledJob):
        """Add a new scheduled job"""
        self.scheduled_jobs[job.job_id] = job
        self._schedule_job(job)
        self._save_jobs()
        logger.info(f"Added scheduled job: {job.name} ({job.job_id})")
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        if job_id in self.scheduled_jobs:
            job = self.scheduled_jobs[job_id]
            schedule.clear(job.name)
            del self.scheduled_jobs[job_id]
            self._save_jobs()
            logger.info(f"Removed scheduled job: {job_id}")
    
    def update_job(self, job_id: str, **kwargs):
        """Update a scheduled job"""
        if job_id in self.scheduled_jobs:
            job = self.scheduled_jobs[job_id]
            
            # Clear existing schedule
            schedule.clear(job.name)
            
            # Update job properties
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            
            # Re-schedule if enabled
            if job.enabled:
                self._schedule_job(job)
            
            self._save_jobs()
            logger.info(f"Updated scheduled job: {job_id}")
    
    def _schedule_job(self, job: ScheduledJob):
        """Schedule a job using the schedule library"""
        if not job.enabled:
            return
        
        try:
            if job.schedule_type == 'hourly':
                schedule.every(job.schedule_value).hours.do(
                    self._execute_job, job.job_id
                ).tag(job.name)
            
            elif job.schedule_type == 'daily':
                schedule.every().day.at(job.schedule_value).do(
                    self._execute_job, job.job_id
                ).tag(job.name)
            
            elif job.schedule_type == 'weekly':
                day, time_str = job.schedule_value.split(' ')
                getattr(schedule.every(), day.lower()).at(time_str).do(
                    self._execute_job, job.job_id
                ).tag(job.name)
            
            elif job.schedule_type == 'cron':
                # For cron expressions, we'll use a custom handler
                self._schedule_cron_job(job)
            
            logger.info(f"Scheduled job: {job.name} ({job.schedule_type}: {job.schedule_value})")
            
        except Exception as e:
            logger.error(f"Error scheduling job {job.name}: {e}")
    
    def _schedule_cron_job(self, job: ScheduledJob):
        """Schedule a job using cron expression"""
        # This is a simplified cron parser
        # In production, you might want to use a more robust cron library
        cron_parts = job.schedule_value.split()
        
        if len(cron_parts) >= 5:
            minute, hour, day, month, weekday = cron_parts[:5]
            
            # Schedule based on cron expression
            if minute != '*' and hour != '*':
                # Specific time
                schedule.every().day.at(f"{hour.zfill(2)}:{minute.zfill(2)}").do(
                    self._execute_job, job.job_id
                ).tag(job.name)
            elif minute == '*' and hour != '*':
                # Every minute at specific hour
                schedule.every().day.at(f"{hour.zfill(2)}:00").do(
                    self._execute_job, job.job_id
                ).tag(job.name)
            else:
                # Default to hourly
                schedule.every().hour.do(
                    self._execute_job, job.job_id
                ).tag(job.name)
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)
    
    def _execute_job(self, job_id: str):
        """Execute a scheduled job"""
        if job_id not in self.scheduled_jobs:
            logger.error(f"Job not found: {job_id}")
            return
        
        job = self.scheduled_jobs[job_id]
        
        try:
            logger.info(f"Executing scheduled job: {job.name}")
            job.last_run = datetime.now()
            
            # Execute based on job type
            if job.job_type == 'scraping':
                result = self._execute_scraping_job(job)
            elif job.job_type == 'deduplication':
                result = self._execute_deduplication_job(job)
            elif job.job_type == 'sync':
                result = self._execute_sync_job(job)
            elif job.job_type == 'maintenance':
                result = self._execute_maintenance_job(job)
            else:
                logger.error(f"Unknown job type: {job.job_type}")
                return
            
            # Update next run time
            job.next_run = self._calculate_next_run(job)
            
            # Notify callbacks
            self._notify_callbacks('job_completed', job, result)
            
            logger.info(f"Scheduled job completed: {job.name}")
            
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")
            self._notify_callbacks('job_failed', job, {'error': str(e)})
    
    def _execute_scraping_job(self, job: ScheduledJob) -> Dict[str, Any]:
        """Execute a scraping job"""
        try:
            config = job.config
            
            if job.target == 'all_platforms':
                # Scrape all platforms
                platforms = ['amazon', 'walmart', 'target', 'bestbuy']
                results = {}
                
                for platform in platforms:
                    result = self.scraping_manager.start_scraping(
                        platform=platform,
                        category=config.get('category', 'electronics'),
                        max_pages=config.get('max_pages', 10)
                    )
                    results[platform] = result
                
                return {'success': True, 'results': results}
            
            else:
                # Scrape specific platform
                result = self.scraping_manager.start_scraping(
                    platform=job.target,
                    category=config.get('category', 'electronics'),
                    max_pages=config.get('max_pages', 10)
                )
                
                return {'success': True, 'result': result}
                
        except Exception as e:
            logger.error(f"Error executing scraping job: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_deduplication_job(self, job: ScheduledJob) -> Dict[str, Any]:
        """Execute a deduplication job"""
        try:
            from data_processing.deduplication import deduplicator
            
            result = deduplicator.deduplicate_database(self.db_manager)
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            logger.error(f"Error executing deduplication job: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_sync_job(self, job: ScheduledJob) -> Dict[str, Any]:
        """Execute a sync job"""
        try:
            if self.sync_manager:
                if job.target == 'all_products':
                    # Sync all products
                    result = self.sync_manager.sync_all_products()
                else:
                    # Sync specific target
                    result = self.sync_manager.sync_target(job.target)
                
                return {'success': True, 'result': result}
            else:
                return {'success': False, 'error': 'Sync manager not available'}
                
        except Exception as e:
            logger.error(f"Error executing sync job: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_maintenance_job(self, job: ScheduledJob) -> Dict[str, Any]:
        """Execute a maintenance job"""
        try:
            config = job.config
            maintenance_type = config.get('type', 'cleanup')
            
            if maintenance_type == 'cleanup':
                # Clean up old data
                days_to_keep = config.get('days_to_keep', 30)
                result = self.db_manager.cleanup_old_data(days_to_keep)
                
            elif maintenance_type == 'backup':
                # Create database backup
                backup_path = config.get('backup_path', 'backups/')
                result = self.db_manager.create_backup(backup_path)
                
            elif maintenance_type == 'optimize':
                # Optimize database
                result = self.db_manager.optimize_database()
                
            else:
                return {'success': False, 'error': f'Unknown maintenance type: {maintenance_type}'}
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            logger.error(f"Error executing maintenance job: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_next_run(self, job: ScheduledJob) -> datetime:
        """Calculate next run time for a job"""
        now = datetime.now()
        
        if job.schedule_type == 'hourly':
            return now + timedelta(hours=int(job.schedule_value))
        elif job.schedule_type == 'daily':
            # Parse time string (e.g., "14:30")
            hour, minute = map(int, job.schedule_value.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        elif job.schedule_type == 'weekly':
            # Parse day and time (e.g., "monday 14:30")
            day_str, time_str = job.schedule_value.split(' ')
            hour, minute = map(int, time_str.split(':'))
            
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            target_day = days.index(day_str.lower())
            current_day = now.weekday()
            
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        return now + timedelta(hours=1)  # Default to 1 hour
    
    def _notify_callbacks(self, event_type: str, job: ScheduledJob, result: Dict[str, Any]):
        """Notify all registered callbacks"""
        for callback in self.job_callbacks:
            try:
                callback(event_type, job, result)
            except Exception as e:
                logger.error(f"Error in job callback: {e}")
    
    def add_job_callback(self, callback: Callable):
        """Add a callback function to be called on job events"""
        self.job_callbacks.append(callback)
    
    def _save_jobs(self):
        """Save scheduled jobs to file"""
        try:
            jobs_data = {
                job_id: {
                    'job_id': job.job_id,
                    'name': job.name,
                    'job_type': job.job_type,
                    'target': job.target,
                    'schedule_type': job.schedule_type,
                    'schedule_value': job.schedule_value,
                    'enabled': job.enabled,
                    'last_run': job.last_run.isoformat() if job.last_run else None,
                    'next_run': job.next_run.isoformat() if job.next_run else None,
                    'created_at': job.created_at.isoformat(),
                    'config': job.config
                }
                for job_id, job in self.scheduled_jobs.items()
            }
            
            with open(self.jobs_file, 'w') as f:
                json.dump(jobs_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving jobs: {e}")
    
    def _load_jobs(self):
        """Load scheduled jobs from file"""
        try:
            if os.path.exists(self.jobs_file):
                with open(self.jobs_file, 'r') as f:
                    jobs_data = json.load(f)
                
                for job_id, job_data in jobs_data.items():
                    job = ScheduledJob(
                        job_id=job_data['job_id'],
                        name=job_data['name'],
                        job_type=job_data['job_type'],
                        target=job_data['target'],
                        schedule_type=job_data['schedule_type'],
                        schedule_value=job_data['schedule_value'],
                        enabled=job_data['enabled'],
                        last_run=datetime.fromisoformat(job_data['last_run']) if job_data['last_run'] else None,
                        next_run=datetime.fromisoformat(job_data['next_run']) if job_data['next_run'] else None,
                        created_at=datetime.fromisoformat(job_data['created_at']),
                        config=job_data['config']
                    )
                    
                    self.scheduled_jobs[job_id] = job
                    
                    if job.enabled:
                        self._schedule_job(job)
                
                logger.info(f"Loaded {len(self.scheduled_jobs)} scheduled jobs")
                
        except Exception as e:
            logger.error(f"Error loading jobs: {e}")
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'is_running': self.is_running,
            'total_jobs': len(self.scheduled_jobs),
            'enabled_jobs': len([j for j in self.scheduled_jobs.values() if j.enabled]),
            'disabled_jobs': len([j for j in self.scheduled_jobs.values() if not j.enabled]),
            'jobs': [
                {
                    'job_id': job.job_id,
                    'name': job.name,
                    'job_type': job.job_type,
                    'target': job.target,
                    'schedule_type': job.schedule_type,
                    'schedule_value': job.schedule_value,
                    'enabled': job.enabled,
                    'last_run': job.last_run.isoformat() if job.last_run else None,
                    'next_run': job.next_run.isoformat() if job.next_run else None
                }
                for job in self.scheduled_jobs.values()
            ]
        }
    
    def create_cron_job_file(self) -> str:
        """Create a cron job file for cloud VM deployment"""
        cron_content = []
        
        # Add shebang
        cron_content.append("#!/bin/bash")
        cron_content.append("")
        
        # Add environment setup
        cron_content.append("# Environment setup")
        cron_content.append(f"cd {os.getcwd()}")
        cron_content.append("export PYTHONPATH=$PYTHONPATH:$(pwd)")
        cron_content.append("")
        
        # Add scheduled jobs
        for job in self.scheduled_jobs.values():
            if job.enabled and job.schedule_type == 'cron':
                cron_content.append(f"# {job.name}")
                cron_content.append(f"{job.schedule_value} python -m scheduler.execute_job {job.job_id}")
                cron_content.append("")
        
        # Write cron file
        cron_file = 'cron_jobs.sh'
        with open(cron_file, 'w') as f:
            f.write('\n'.join(cron_content))
        
        # Make executable
        os.chmod(cron_file, 0o755)
        
        logger.info(f"Created cron job file: {cron_file}")
        return cron_file

# Global scheduler instance
job_scheduler = None

def get_job_scheduler(db_manager=None, scraping_manager=None, sync_manager=None):
    """Get or create the global job scheduler instance"""
    global job_scheduler
    if job_scheduler is None and db_manager and scraping_manager:
        job_scheduler = JobScheduler(db_manager, scraping_manager, sync_manager)
    return job_scheduler


