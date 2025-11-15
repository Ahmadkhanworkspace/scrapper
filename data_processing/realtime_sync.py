"""
Real-Time Syncing System for Unified E-commerce Product Data Aggregator
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
import threading
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class SyncTask:
    """Represents a sync task for a product or category"""
    task_id: str
    task_type: str  # 'product', 'category', 'platform'
    target_id: str
    priority: int = 1  # 1=high, 2=medium, 3=low
    created_at: datetime = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    interval_minutes: int = 60
    max_retries: int = 3
    retry_count: int = 0
    status: str = 'pending'  # pending, running, completed, failed, paused
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.next_run is None:
            self.next_run = self.created_at + timedelta(minutes=self.interval_minutes)

class RealTimeSyncManager:
    """
    Manages real-time syncing of product data across platforms.
    Detects and updates price changes within specified intervals.
    """
    
    def __init__(self, db_manager, scraping_manager):
        self.db_manager = db_manager
        self.scraping_manager = scraping_manager
        self.sync_tasks: Dict[str, SyncTask] = {}
        self.is_running = False
        self.sync_thread = None
        self.price_change_threshold = 0.05  # 5% price change threshold
        self.sync_callbacks: List[Callable] = []
        
    def start_sync_manager(self):
        """Start the real-time sync manager"""
        if self.is_running:
            logger.warning("Sync manager is already running")
            return
        
        self.is_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("Real-time sync manager started")
    
    def stop_sync_manager(self):
        """Stop the real-time sync manager"""
        self.is_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        logger.info("Real-time sync manager stopped")
    
    def add_sync_task(self, task: SyncTask):
        """Add a new sync task"""
        self.sync_tasks[task.task_id] = task
        logger.info(f"Added sync task: {task.task_id} for {task.task_type}:{task.target_id}")
    
    def remove_sync_task(self, task_id: str):
        """Remove a sync task"""
        if task_id in self.sync_tasks:
            del self.sync_tasks[task_id]
            logger.info(f"Removed sync task: {task_id}")
    
    def update_sync_task(self, task_id: str, **kwargs):
        """Update sync task parameters"""
        if task_id in self.sync_tasks:
            task = self.sync_tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            logger.info(f"Updated sync task: {task_id}")
    
    def add_sync_callback(self, callback: Callable):
        """Add a callback function to be called on sync events"""
        self.sync_callbacks.append(callback)
    
    def _sync_loop(self):
        """Main sync loop that runs continuously"""
        while self.is_running:
            try:
                current_time = datetime.now()
                tasks_to_run = []
                
                # Find tasks that need to run
                for task in self.sync_tasks.values():
                    if (task.status in ['pending', 'completed'] and 
                        task.next_run <= current_time):
                        tasks_to_run.append(task)
                
                # Sort by priority
                tasks_to_run.sort(key=lambda t: t.priority)
                
                # Execute tasks
                for task in tasks_to_run:
                    if not self.is_running:
                        break
                    self._execute_sync_task(task)
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _execute_sync_task(self, task: SyncTask):
        """Execute a single sync task"""
        try:
            task.status = 'running'
            task.last_run = datetime.now()
            
            logger.info(f"Executing sync task: {task.task_id}")
            
            if task.task_type == 'product':
                result = self._sync_product(task.target_id)
            elif task.task_type == 'category':
                result = self._sync_category(task.target_id)
            elif task.task_type == 'platform':
                result = self._sync_platform(task.target_id)
            else:
                logger.error(f"Unknown task type: {task.task_type}")
                task.status = 'failed'
                return
            
            if result['success']:
                task.status = 'completed'
                task.retry_count = 0
                task.next_run = datetime.now() + timedelta(minutes=task.interval_minutes)
                
                # Notify callbacks
                self._notify_callbacks('task_completed', task, result)
                
                logger.info(f"Sync task completed: {task.task_id}")
            else:
                task.retry_count += 1
                if task.retry_count >= task.max_retries:
                    task.status = 'failed'
                    logger.error(f"Sync task failed permanently: {task.task_id}")
                    self._notify_callbacks('task_failed', task, result)
                else:
                    task.status = 'pending'
                    # Exponential backoff
                    delay_minutes = task.interval_minutes * (2 ** task.retry_count)
                    task.next_run = datetime.now() + timedelta(minutes=delay_minutes)
                    logger.warning(f"Sync task failed, retrying in {delay_minutes} minutes: {task.task_id}")
                
        except Exception as e:
            logger.error(f"Error executing sync task {task.task_id}: {e}")
            task.status = 'failed'
            task.retry_count += 1
    
    def _sync_product(self, product_id: str) -> Dict[str, Any]:
        """Sync a single product"""
        try:
            # Get current product data
            current_product = self.db_manager.get_product_by_id(product_id)
            if not current_product:
                return {'success': False, 'error': 'Product not found'}
            
            # Get fresh data from source
            fresh_data = self._scrape_product_fresh(current_product)
            if not fresh_data:
                return {'success': False, 'error': 'Failed to scrape fresh data'}
            
            # Compare and update if needed
            changes = self._detect_changes(current_product, fresh_data)
            
            if changes:
                # Update database
                self.db_manager.update_product(product_id, fresh_data)
                
                # Log price changes
                if 'price_changed' in changes:
                    self._log_price_change(product_id, changes['price_changed'])
                
                return {
                    'success': True,
                    'changes': changes,
                    'updated': True
                }
            else:
                return {
                    'success': True,
                    'changes': {},
                    'updated': False
                }
                
        except Exception as e:
            logger.error(f"Error syncing product {product_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _sync_category(self, category: str) -> Dict[str, Any]:
        """Sync all products in a category"""
        try:
            products = self.db_manager.get_products_by_category(category)
            if not products:
                return {'success': False, 'error': 'No products found in category'}
            
            results = {
                'success': True,
                'products_checked': len(products),
                'products_updated': 0,
                'errors': 0
            }
            
            for product in products:
                try:
                    result = self._sync_product(product['product_id'])
                    if result['success'] and result.get('updated'):
                        results['products_updated'] += 1
                except Exception as e:
                    logger.error(f"Error syncing product {product['product_id']}: {e}")
                    results['errors'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing category {category}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _sync_platform(self, platform: str) -> Dict[str, Any]:
        """Sync all products from a platform"""
        try:
            products = self.db_manager.get_products_by_platform(platform)
            if not products:
                return {'success': False, 'error': 'No products found for platform'}
            
            results = {
                'success': True,
                'products_checked': len(products),
                'products_updated': 0,
                'errors': 0
            }
            
            for product in products:
                try:
                    result = self._sync_product(product['product_id'])
                    if result['success'] and result.get('updated'):
                        results['products_updated'] += 1
                except Exception as e:
                    logger.error(f"Error syncing product {product['product_id']}: {e}")
                    results['errors'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error syncing platform {platform}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _scrape_product_fresh(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scrape fresh data for a product"""
        try:
            # This would integrate with the scraping manager
            # For now, return a mock implementation
            platform = product['platform']
            external_id = product['external_id']
            
            # Simulate fresh scraping
            fresh_data = {
                'current_price': product['current_price'] + (0.01 if platform == 'amazon' else -0.01),
                'availability_status': product['availability_status'],
                'last_updated': datetime.now().isoformat()
            }
            
            return fresh_data
            
        except Exception as e:
            logger.error(f"Error scraping fresh data: {e}")
            return None
    
    def _detect_changes(self, current: Dict[str, Any], fresh: Dict[str, Any]) -> Dict[str, Any]:
        """Detect changes between current and fresh data"""
        changes = {}
        
        # Check price changes
        current_price = current.get('current_price')
        fresh_price = fresh.get('current_price')
        
        if current_price and fresh_price:
            price_change = abs(fresh_price - current_price) / current_price
            if price_change >= self.price_change_threshold:
                changes['price_changed'] = {
                    'old_price': current_price,
                    'new_price': fresh_price,
                    'change_percentage': price_change * 100
                }
        
        # Check availability changes
        if current.get('availability_status') != fresh.get('availability_status'):
            changes['availability_changed'] = {
                'old_status': current.get('availability_status'),
                'new_status': fresh.get('availability_status')
            }
        
        return changes
    
    def _log_price_change(self, product_id: str, price_change: Dict[str, Any]):
        """Log significant price changes"""
        try:
            self.db_manager.log_price_change(
                product_id=product_id,
                old_price=price_change['old_price'],
                new_price=price_change['new_price'],
                change_percentage=price_change['change_percentage']
            )
            
            # Notify callbacks
            self._notify_callbacks('price_changed', product_id, price_change)
            
        except Exception as e:
            logger.error(f"Error logging price change: {e}")
    
    def _notify_callbacks(self, event_type: str, *args, **kwargs):
        """Notify all registered callbacks"""
        for callback in self.sync_callbacks:
            try:
                callback(event_type, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in sync callback: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            'is_running': self.is_running,
            'total_tasks': len(self.sync_tasks),
            'pending_tasks': len([t for t in self.sync_tasks.values() if t.status == 'pending']),
            'running_tasks': len([t for t in self.sync_tasks.values() if t.status == 'running']),
            'completed_tasks': len([t for t in self.sync_tasks.values() if t.status == 'completed']),
            'failed_tasks': len([t for t in self.sync_tasks.values() if t.status == 'failed']),
            'tasks': [
                {
                    'task_id': task.task_id,
                    'task_type': task.task_type,
                    'target_id': task.target_id,
                    'status': task.status,
                    'next_run': task.next_run.isoformat() if task.next_run else None,
                    'retry_count': task.retry_count
                }
                for task in self.sync_tasks.values()
            ]
        }
    
    def create_product_sync_task(self, product_id: str, interval_minutes: int = 60, priority: int = 1) -> str:
        """Create a sync task for a specific product"""
        task_id = f"product_{product_id}_{int(time.time())}"
        task = SyncTask(
            task_id=task_id,
            task_type='product',
            target_id=product_id,
            interval_minutes=interval_minutes,
            priority=priority
        )
        self.add_sync_task(task)
        return task_id
    
    def create_category_sync_task(self, category: str, interval_minutes: int = 240, priority: int = 2) -> str:
        """Create a sync task for a category"""
        task_id = f"category_{category}_{int(time.time())}"
        task = SyncTask(
            task_id=task_id,
            task_type='category',
            target_id=category,
            interval_minutes=interval_minutes,
            priority=priority
        )
        self.add_sync_task(task)
        return task_id
    
    def create_platform_sync_task(self, platform: str, interval_minutes: int = 480, priority: int = 3) -> str:
        """Create a sync task for a platform"""
        task_id = f"platform_{platform}_{int(time.time())}"
        task = SyncTask(
            task_id=task_id,
            task_type='platform',
            target_id=platform,
            interval_minutes=interval_minutes,
            priority=priority
        )
        self.add_sync_task(task)
        return task_id

# Global sync manager instance
sync_manager = None

def get_sync_manager(db_manager=None, scraping_manager=None):
    """Get or create the global sync manager instance"""
    global sync_manager
    if sync_manager is None and db_manager and scraping_manager:
        sync_manager = RealTimeSyncManager(db_manager, scraping_manager)
    return sync_manager


