"""
Base spider class with common functionality for all e-commerce platforms
"""
import scrapy
import logging
import time
import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import re

from amazonscraper.items import ProductItem, ImageItem, SpecificationItem, VariationItem
from database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


class BaseEcommerceSpider(scrapy.Spider):
    """Base spider class with common functionality for all e-commerce platforms"""
    
    # Common settings for all spiders
    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 16,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
        'AUTOTHROTTLE_DEBUG': False,
        'COOKIES_ENABLED': True,
        'TELNETCONSOLE_ENABLED': False,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_manager = get_db_manager()
        self.scraping_session_id = None
        self.start_time = datetime.now()
        self.products_scraped = 0
        self.errors_count = 0
        self.error_details = []
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        ]
    
    def start_requests(self):
        """Override in child classes to define starting URLs"""
        raise NotImplementedError("Child classes must implement start_requests method")
    
    def parse(self, response):
        """Override in child classes to define parsing logic"""
        raise NotImplementedError("Child classes must implement parse method")
    
    def parse_product(self, response):
        """Override in child classes to define product parsing logic"""
        raise NotImplementedError("Child classes must implement parse_product method")
    
    def make_request(self, url: str, callback=None, meta: Dict[str, Any] = None, **kwargs) -> scrapy.Request:
        """Create a request with anti-detection measures"""
        if meta is None:
            meta = {}
        
        # Add random user agent
        meta['user_agent'] = random.choice(self.user_agents)
        
        # Add random delay
        delay = random.uniform(0.5, 2.0)
        meta['download_delay'] = delay
        
        # Add referer if not present
        if 'referer' not in meta:
            meta['referer'] = response.url if hasattr(response, 'url') else None
        
        return scrapy.Request(
            url=url,
            callback=callback,
            meta=meta,
            headers={'User-Agent': meta['user_agent']},
            **kwargs
        )
    
    def extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not price_text:
            return None
        
        # Remove currency symbols and common text
        price_text = re.sub(r'[^\d.,]', '', str(price_text))
        
        # Handle different decimal separators
        if ',' in price_text and '.' in price_text:
            # Format like 1,234.56
            price_text = price_text.replace(',', '')
        elif ',' in price_text and len(price_text.split(',')[-1]) <= 2:
            # Format like 1234,56 (European)
            price_text = price_text.replace(',', '.')
        
        try:
            return float(price_text)
        except (ValueError, TypeError):
            logger.warning(f"Could not extract price from: {price_text}")
            return None
    
    def extract_rating(self, rating_text: str) -> Optional[float]:
        """Extract numeric rating from text"""
        if not rating_text:
            return None
        
        # Extract rating from text like "4.5 out of 5 stars"
        rating_match = re.search(r'(\d+\.?\d*)', str(rating_text))
        if rating_match:
            try:
                rating = float(rating_match.group(1))
                # Normalize to 1-5 scale if needed
                if rating > 5:
                    rating = rating / 2  # Convert from 10-point scale
                return rating
            except (ValueError, TypeError):
                pass
        
        return None
    
    def extract_review_count(self, review_text: str) -> Optional[int]:
        """Extract review count from text"""
        if not review_text:
            return None
        
        # Extract number from text like "1,234 reviews"
        review_match = re.search(r'([\d,]+)', str(review_text))
        if review_match:
            try:
                return int(review_match.group(1).replace(',', ''))
            except (ValueError, TypeError):
                pass
        
        return None
    
    def normalize_availability(self, availability_text: str) -> str:
        """Normalize availability status"""
        if not availability_text:
            return 'unknown'
        
        availability_text = availability_text.lower().strip()
        
        if any(word in availability_text for word in ['in stock', 'available', 'add to cart']):
            return 'in_stock'
        elif any(word in availability_text for word in ['out of stock', 'unavailable', 'sold out']):
            return 'out_of_stock'
        elif any(word in availability_text for word in ['pre-order', 'preorder', 'coming soon']):
            return 'pre_order'
        elif any(word in availability_text for word in ['limited', 'few left', 'low stock']):
            return 'limited_stock'
        else:
            return 'unknown'
    
    def extract_images(self, response, image_selectors: List[str]) -> List[Dict[str, Any]]:
        """Extract product images using multiple selectors"""
        images = []
        
        for selector in image_selectors:
            img_elements = response.css(selector)
            for img in img_elements:
                img_url = img.css('::attr(src)').get()
                if not img_url:
                    img_url = img.css('::attr(data-src)').get()
                
                if img_url:
                    # Convert relative URLs to absolute
                    img_url = urljoin(response.url, img_url)
                    
                    # Extract alt text
                    alt_text = img.css('::attr(alt)').get() or ''
                    
                    # Determine image type
                    image_type = 'gallery'
                    if 'primary' in img_url.lower() or 'main' in img_url.lower():
                        image_type = 'primary'
                    elif 'thumbnail' in img_url.lower() or 'thumb' in img_url.lower():
                        image_type = 'thumbnail'
                    elif 'zoom' in img_url.lower():
                        image_type = 'zoom'
                    
                    images.append({
                        'url': img_url,
                        'type': image_type,
                        'alt_text': alt_text
                    })
        
        return images
    
    def extract_specifications(self, response, spec_selectors: Dict[str, str]) -> Dict[str, Any]:
        """Extract product specifications"""
        specifications = {}
        
        for category, selector in spec_selectors.items():
            spec_elements = response.css(selector)
            for spec in spec_elements:
                name = spec.css('::text').get()
                if name:
                    name = name.strip().rstrip(':')
                    # Try to get the value from next sibling or parent
                    value = spec.css('+ *::text').get() or spec.css('parent::*::text').get()
                    if value:
                        specifications[name] = value.strip()
        
        return specifications
    
    def extract_variations(self, response, variation_selectors: Dict[str, str]) -> List[Dict[str, Any]]:
        """Extract product variations"""
        variations = []
        
        for variation_type, selector in variation_selectors.items():
            variation_elements = response.css(selector)
            for variation in variation_elements:
                value = variation.css('::text').get()
                if value:
                    variations.append({
                        'type': variation_type,
                        'value': value.strip(),
                        'price': None,  # Will be extracted separately if needed
                        'availability': 'in_stock'
                    })
        
        return variations
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ''
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common unwanted characters
        text = re.sub(r'[\r\n\t]+', ' ', text)
        
        return text.strip()
    
    def get_external_id(self, url: str) -> str:
        """Extract external product ID from URL"""
        # This should be implemented by child classes for platform-specific logic
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        return path_parts[-1] if path_parts else url
    
    def log_error(self, error: Exception, context: str = ""):
        """Log error and increment error count"""
        self.errors_count += 1
        error_msg = f"Error in {context}: {str(error)}"
        self.error_details.append(error_msg)
        logger.error(error_msg)
    
    def closed(self, reason):
        """Called when spider closes"""
        try:
            # Log scraping session
            self.db_manager.log_scraping_session(
                platform=self.name,
                spider_name=self.__class__.__name__,
                start_time=self.start_time,
                status='completed' if reason == 'finished' else 'failed',
                products_scraped=self.products_scraped,
                errors_count=self.errors_count,
                error_details='; '.join(self.error_details) if self.error_details else None
            )
            logger.info(f"Spider {self.name} closed. Reason: {reason}. Products scraped: {self.products_scraped}")
        except Exception as e:
            logger.error(f"Error closing spider: {e}")
    
    def process_product_item(self, item: ProductItem) -> ProductItem:
        """Process and validate product item before yielding"""
        try:
            # Add metadata
            item['scraped_at'] = datetime.now().isoformat()
            item['spider_name'] = self.name
            
            # Clean text fields
            if 'title' in item:
                item['title'] = self.clean_text(item['title'])
            if 'description' in item:
                item['description'] = self.clean_text(item['description'])
            
            # Validate required fields
            if not item.get('external_id'):
                item['external_id'] = self.get_external_id(item.get('product_url', ''))
            
            if not item.get('platform'):
                item['platform'] = self.name
            
            # Increment products scraped counter
            self.products_scraped += 1
            
            return item
            
        except Exception as e:
            self.log_error(e, "process_product_item")
            return None


