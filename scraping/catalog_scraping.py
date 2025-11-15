"""
Initial Catalog Scraping and Incremental Scraping for Unified E-commerce Product Data Aggregator
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ScrapingSession:
    """Represents a scraping session"""
    session_id: str
    session_type: str  # 'initial', 'incremental', 'realtime'
    platform: str
    category: Optional[str] = None
    start_time: datetime = None
    end_time: Optional[datetime] = None
    products_scraped: int = 0
    products_updated: int = 0
    errors: int = 0
    status: str = 'running'  # running, completed, failed, paused
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()

class CatalogScrapingManager:
    """
    Manages initial catalog scraping (deep scraping to discover new products)
    and incremental scraping (lightweight updates for price/availability).
    """
    
    def __init__(self, db_manager, scraping_manager):
        self.db_manager = db_manager
        self.scraping_manager = scraping_manager
        self.active_sessions: Dict[str, ScrapingSession] = {}
        
    def start_initial_catalog_scraping(self, platform: str, category: str = None, 
                                     max_pages: int = 100) -> str:
        """
        Start initial catalog scraping to discover and add new products.
        This is a deep scraping process that explores entire categories.
        """
        session_id = f"initial_{platform}_{int(time.time())}"
        
        session = ScrapingSession(
            session_id=session_id,
            session_type='initial',
            platform=platform,
            category=category
        )
        
        self.active_sessions[session_id] = session
        
        # Start scraping in background
        import threading
        thread = threading.Thread(
            target=self._run_initial_scraping,
            args=(session, max_pages),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Started initial catalog scraping: {session_id}")
        return session_id
    
    def start_incremental_scraping(self, platform: str, category: str = None,
                                 max_pages: int = 20) -> str:
        """
        Start incremental scraping for lightweight updates.
        Focuses on price and availability updates for existing products.
        """
        session_id = f"incremental_{platform}_{int(time.time())}"
        
        session = ScrapingSession(
            session_id=session_id,
            session_type='incremental',
            platform=platform,
            category=category
        )
        
        self.active_sessions[session_id] = session
        
        # Start scraping in background
        import threading
        thread = threading.Thread(
            target=self._run_incremental_scraping,
            args=(session, max_pages),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Started incremental scraping: {session_id}")
        return session_id
    
    def _run_initial_scraping(self, session: ScrapingSession, max_pages: int):
        """Run initial catalog scraping"""
        try:
            logger.info(f"Starting initial catalog scraping for {session.platform}")
            
            # Get existing products to avoid duplicates
            existing_products = self.db_manager.get_products_by_platform(session.platform)
            existing_ids = {p['external_id'] for p in existing_products}
            
            # Start URLs for deep scraping
            start_urls = self._get_catalog_start_urls(session.platform, session.category)
            
            for url in start_urls:
                if session.status != 'running':
                    break
                
                # Scrape category pages
                products = self._scrape_category_deep(url, max_pages)
                
                for product in products:
                    if session.status != 'running':
                        break
                    
                    # Check if product already exists
                    if product['external_id'] in existing_ids:
                        continue
                    
                    # Process and store new product
                    processed_product = self._process_new_product(product)
                    if processed_product:
                        self.db_manager.insert_product(processed_product)
                        session.products_scraped += 1
                        
                        logger.debug(f"Added new product: {product['external_id']}")
                    
                    # Add delay to avoid rate limiting
                    time.sleep(2)
            
            session.status = 'completed'
            session.end_time = datetime.now()
            
            logger.info(f"Initial catalog scraping completed: {session.products_scraped} products scraped")
            
        except Exception as e:
            logger.error(f"Error in initial catalog scraping: {e}")
            session.status = 'failed'
            session.end_time = datetime.now()
    
    def _run_incremental_scraping(self, session: ScrapingSession, max_pages: int):
        """Run incremental scraping for updates"""
        try:
            logger.info(f"Starting incremental scraping for {session.platform}")
            
            # Get existing products that need updates
            existing_products = self.db_manager.get_products_by_platform(session.platform)
            
            # Filter products that need updates (older than 24 hours)
            cutoff_time = datetime.now() - timedelta(hours=24)
            products_to_update = [
                p for p in existing_products 
                if p.get('last_updated') and 
                datetime.fromisoformat(p['last_updated']) < cutoff_time
            ]
            
            logger.info(f"Found {len(products_to_update)} products needing updates")
            
            for product in products_to_update[:max_pages * 10]:  # Limit for incremental
                if session.status != 'running':
                    break
                
                try:
                    # Get fresh data for the product
                    fresh_data = self._scrape_product_fresh(product)
                    
                    if fresh_data:
                        # Compare and update if changed
                        changes = self._detect_product_changes(product, fresh_data)
                        
                        if changes:
                            # Update product in database
                            updated_product = {**product, **fresh_data}
                            updated_product['last_updated'] = datetime.now().isoformat()
                            
                            self.db_manager.update_product(product['product_id'], updated_product)
                            session.products_updated += 1
                            
                            logger.debug(f"Updated product: {product['external_id']}")
                        
                        session.products_scraped += 1
                    
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error updating product {product['external_id']}: {e}")
                    session.errors += 1
            
            session.status = 'completed'
            session.end_time = datetime.now()
            
            logger.info(f"Incremental scraping completed: {session.products_scraped} checked, {session.products_updated} updated")
            
        except Exception as e:
            logger.error(f"Error in incremental scraping: {e}")
            session.status = 'failed'
            session.end_time = datetime.now()
    
    def _get_catalog_start_urls(self, platform: str, category: str = None) -> List[str]:
        """Get start URLs for catalog scraping"""
        urls = []
        
        if platform == 'amazon':
            if category:
                urls.append(f'https://www.amazon.com/s?k={category}')
            else:
                # Multiple categories for deep scraping
                categories = ['electronics', 'computers', 'home', 'fashion', 'books', 'sports']
                urls.extend([f'https://www.amazon.com/s?k={cat}' for cat in categories])
        
        elif platform == 'walmart':
            if category:
                urls.append(f'https://www.walmart.com/browse/{category}')
            else:
                categories = ['electronics', 'home', 'fashion', 'toys', 'automotive']
                urls.extend([f'https://www.walmart.com/browse/{cat}' for cat in categories])
        
        elif platform == 'target':
            if category:
                urls.append(f'https://www.target.com/c/{category}')
            else:
                categories = ['electronics', 'home', 'clothing', 'toys', 'beauty']
                urls.extend([f'https://www.target.com/c/{cat}' for cat in categories])
        
        elif platform == 'bestbuy':
            if category:
                urls.append(f'https://www.bestbuy.com/site/{category}')
            else:
                categories = ['electronics', 'computers-tablets', 'home-appliances', 'health-fitness-beauty']
                urls.extend([f'https://www.bestbuy.com/site/{cat}' for cat in categories])
        
        return urls
    
    def _scrape_category_deep(self, url: str, max_pages: int) -> List[Dict[str, Any]]:
        """Scrape a category deeply to discover products"""
        products = []
        
        try:
            # This would integrate with the actual scraping spiders
            # For now, return mock data
            for page in range(min(max_pages, 10)):
                # Simulate scraping products from each page
                page_products = self._simulate_category_scraping(url, page)
                products.extend(page_products)
                
                # Add delay between pages
                time.sleep(3)
        
        except Exception as e:
            logger.error(f"Error scraping category {url}: {e}")
        
        return products
    
    def _simulate_category_scraping(self, url: str, page: int) -> List[Dict[str, Any]]:
        """Simulate category scraping (replace with actual spider integration)"""
        products = []
        
        # Generate mock products
        for i in range(20):  # 20 products per page
            product_id = f"MOCK_{page}_{i}_{int(time.time())}"
            
            product = {
                'external_id': product_id,
                'platform': url.split('//')[1].split('.')[0],  # Extract platform from URL
                'title': f'Mock Product {page}-{i}',
                'brand': 'Mock Brand',
                'current_price': 99.99 + (page * 10) + i,
                'availability_status': 'in_stock',
                'rating': 4.0 + (i % 5) * 0.2,
                'review_count': 100 + (i * 10),
                'category': 'electronics',
                'product_url': f'{url}?page={page}&product={i}',
                'scraped_at': datetime.now().isoformat(),
                'is_curated': True
            }
            
            products.append(product)
        
        return products
    
    def _scrape_product_fresh(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Scrape fresh data for a specific product"""
        try:
            # This would integrate with the actual product spiders
            # For now, return mock updated data
            
            # Simulate price changes
            current_price = product.get('current_price', 0)
            price_change = (time.time() % 10) - 5  # Random price change between -5 and +5
            new_price = max(0.01, current_price + price_change)
            
            # Simulate availability changes
            availability_options = ['in_stock', 'out_of_stock', 'limited_stock']
            new_availability = availability_options[int(time.time()) % len(availability_options)]
            
            fresh_data = {
                'current_price': new_price,
                'availability_status': new_availability,
                'last_updated': datetime.now().isoformat()
            }
            
            return fresh_data
            
        except Exception as e:
            logger.error(f"Error scraping fresh data for product {product['external_id']}: {e}")
            return None
    
    def _detect_product_changes(self, current: Dict[str, Any], fresh: Dict[str, Any]) -> Dict[str, Any]:
        """Detect changes between current and fresh product data"""
        changes = {}
        
        # Check price changes
        current_price = current.get('current_price')
        fresh_price = fresh.get('current_price')
        
        if current_price and fresh_price and abs(current_price - fresh_price) > 0.01:
            changes['price_changed'] = {
                'old_price': current_price,
                'new_price': fresh_price,
                'change': fresh_price - current_price
            }
        
        # Check availability changes
        if current.get('availability_status') != fresh.get('availability_status'):
            changes['availability_changed'] = {
                'old_status': current.get('availability_status'),
                'new_status': fresh.get('availability_status')
            }
        
        return changes
    
    def _process_new_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a new product before storing"""
        try:
            # Apply data processing and curation rules
            from data_processing.processor import data_processor
            
            processed_product = data_processor.process_product(product)
            
            if processed_product:
                # Add additional metadata
                processed_product['discovered_at'] = datetime.now().isoformat()
                processed_product['is_new'] = True
                
                return processed_product
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing new product: {e}")
            return None
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a scraping session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            return {
                'session_id': session.session_id,
                'session_type': session.session_type,
                'platform': session.platform,
                'category': session.category,
                'status': session.status,
                'start_time': session.start_time.isoformat(),
                'end_time': session.end_time.isoformat() if session.end_time else None,
                'products_scraped': session.products_scraped,
                'products_updated': session.products_updated,
                'errors': session.errors,
                'duration': (session.end_time - session.start_time).total_seconds() if session.end_time else None
            }
        return None
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get status of all active sessions"""
        return [self.get_session_status(session_id) for session_id in self.active_sessions.keys()]
    
    def stop_session(self, session_id: str):
        """Stop a running session"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = 'paused'
            logger.info(f"Stopped session: {session_id}")
    
    def cleanup_completed_sessions(self):
        """Clean up completed sessions older than 24 hours"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        sessions_to_remove = []
        for session_id, session in self.active_sessions.items():
            if (session.status in ['completed', 'failed'] and 
                session.end_time and session.end_time < cutoff_time):
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} completed sessions")

# Global catalog scraping manager instance
catalog_manager = None

def get_catalog_manager(db_manager=None, scraping_manager=None):
    """Get or create the global catalog scraping manager instance"""
    global catalog_manager
    if catalog_manager is None and db_manager and scraping_manager:
        catalog_manager = CatalogScrapingManager(db_manager, scraping_manager)
    return catalog_manager


