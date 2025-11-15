# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import logging
from typing import Dict, Any, Optional
import json
from datetime import datetime

from data_processing.processor import data_processor
from database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


class DataProcessingPipeline:
    """Pipeline for processing and normalizing scraped data"""
    
    def __init__(self):
        self.processor = data_processor
        self.processed_count = 0
        self.filtered_count = 0
    
    def process_item(self, item, spider):
        """Process item through data processing pipeline"""
        try:
            # Process the item
            processed_data = self.processor.process_product(item)
            
            if processed_data:
                # Update item with processed data
                adapter = ItemAdapter(item)
                for key, value in processed_data.items():
                    adapter[key] = value
                
                self.processed_count += 1
                logger.info(f"Processed item {self.processed_count}: {processed_data.get('external_id', 'unknown')}")
                return item
            else:
                self.filtered_count += 1
                logger.info(f"Item filtered out by curation rules. Total filtered: {self.filtered_count}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing item: {e}")
            return None
    
    def close_spider(self, spider):
        """Called when spider closes"""
        logger.info(f"Data processing pipeline closed. Processed: {self.processed_count}, Filtered: {self.filtered_count}")


class DatabasePipeline:
    """Pipeline for saving items to database"""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.saved_count = 0
        self.error_count = 0
    
    def process_item(self, item, spider):
        """Save item to database"""
        try:
            adapter = ItemAdapter(item)
            product_data = dict(adapter)
            
            # Save to database
            product_id = self.db_manager.insert_product(product_data)
            
            if product_id:
                self.saved_count += 1
                logger.info(f"Saved item to database: {product_id}")
                
                # Save related data
                self.save_related_data(product_id, product_data)
                
                return item
            else:
                self.error_count += 1
                logger.error(f"Failed to save item to database")
                return None
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error saving item to database: {e}")
            return None
    
    def save_related_data(self, product_id: str, product_data: Dict[str, Any]):
        """Save related data (specifications, images, variations)"""
        try:
            # Save specifications
            if product_data.get('specifications'):
                self.db_manager.insert_product_specifications(product_id, product_data['specifications'])
            
            # Save images
            if product_data.get('images'):
                self.db_manager.insert_product_images(product_id, product_data['images'])
            
            # Save variations
            if product_data.get('variations'):
                self.db_manager.insert_product_variations(product_id, product_data['variations'])
                
        except Exception as e:
            logger.error(f"Error saving related data: {e}")
    
    def close_spider(self, spider):
        """Called when spider closes"""
        logger.info(f"Database pipeline closed. Saved: {self.saved_count}, Errors: {self.error_count}")


class JsonWriterPipeline:
    """Pipeline for writing items to JSON file"""
    
    def __init__(self):
        self.file = None
        self.items = []
    
    def open_spider(self, spider):
        """Open file when spider starts"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_data_{spider.name}_{timestamp}.json"
        self.file = open(filename, 'w', encoding='utf-8')
        self.file.write('[\n')
        logger.info(f"Opened JSON file: {filename}")
    
    def process_item(self, item, spider):
        """Add item to JSON file"""
        try:
            adapter = ItemAdapter(item)
            item_dict = dict(adapter)
            
            # Add to items list
            self.items.append(item_dict)
            
            return item
            
        except Exception as e:
            logger.error(f"Error processing item for JSON: {e}")
            return item
    
    def close_spider(self, spider):
        """Write all items to JSON file and close"""
        try:
            if self.file:
                # Write all items
                for i, item in enumerate(self.items):
                    if i > 0:
                        self.file.write(',\n')
                    json.dump(item, self.file, indent=2, ensure_ascii=False)
                
                self.file.write('\n]')
                self.file.close()
                logger.info(f"Wrote {len(self.items)} items to JSON file")
                
        except Exception as e:
            logger.error(f"Error closing JSON file: {e}")


class DuplicatesPipeline:
    """Pipeline for detecting and handling duplicate items"""
    
    def __init__(self):
        self.seen_items = set()
        self.duplicate_count = 0
    
    def process_item(self, item, spider):
        """Check for duplicates"""
        try:
            adapter = ItemAdapter(item)
            
            # Create a unique identifier for the item
            external_id = adapter.get('external_id', '')
            platform = adapter.get('platform', '')
            title = adapter.get('title', '')
            
            item_id = f"{platform}_{external_id}_{hash(title)}"
            
            if item_id in self.seen_items:
                self.duplicate_count += 1
                logger.info(f"Duplicate item detected: {item_id}")
                return None
            else:
                self.seen_items.add(item_id)
                return item
                
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return item
    
    def close_spider(self, spider):
        """Called when spider closes"""
        logger.info(f"Duplicates pipeline closed. Duplicates found: {self.duplicate_count}")


class ValidationPipeline:
    """Pipeline for validating item data"""
    
    def __init__(self):
        self.valid_count = 0
        self.invalid_count = 0
        self.required_fields = ['external_id', 'platform', 'title', 'current_price', 'product_url']
    
    def process_item(self, item, spider):
        """Validate item data"""
        try:
            adapter = ItemAdapter(item)
            
            # Check required fields
            for field in self.required_fields:
                if not adapter.get(field):
                    self.invalid_count += 1
                    logger.warning(f"Item missing required field '{field}': {adapter.get('external_id', 'unknown')}")
                    return None
            
            # Validate data types and ranges
            if not self.validate_data_types(adapter):
                self.invalid_count += 1
                return None
            
            self.valid_count += 1
            return item
            
        except Exception as e:
            logger.error(f"Error validating item: {e}")
            return None
    
    def validate_data_types(self, adapter) -> bool:
        """Validate data types and ranges"""
        try:
            # Validate price
            current_price = adapter.get('current_price')
            if current_price is not None:
                if not isinstance(current_price, (int, float)) or current_price < 0:
                    logger.warning(f"Invalid price: {current_price}")
                    return False
            
            # Validate rating
            rating = adapter.get('rating')
            if rating is not None:
                if not isinstance(rating, (int, float)) or rating < 0 or rating > 5:
                    logger.warning(f"Invalid rating: {rating}")
                    return False
            
            # Validate review count
            review_count = adapter.get('review_count')
            if review_count is not None:
                if not isinstance(review_count, int) or review_count < 0:
                    logger.warning(f"Invalid review count: {review_count}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating data types: {e}")
            return False
    
    def close_spider(self, spider):
        """Called when spider closes"""
        logger.info(f"Validation pipeline closed. Valid: {self.valid_count}, Invalid: {self.invalid_count}")


class ImageDownloadPipeline:
    """Pipeline for downloading product images"""
    
    def __init__(self):
        self.downloaded_count = 0
        self.failed_count = 0
        self.images_dir = "downloaded_images"
        import os
        os.makedirs(self.images_dir, exist_ok=True)
    
    def process_item(self, item, spider):
        """Download images for item"""
        try:
            adapter = ItemAdapter(item)
            images = adapter.get('images', [])
            
            if not images:
                return item
            
            downloaded_images = []
            for image in images:
                try:
                    # Download image (simplified - in production use proper image downloading)
                    image_url = image.get('url')
                    if image_url:
                        # For now, just keep the URL
                        # In production, you would download and save the image
                        downloaded_images.append({
                            'url': image_url,
                            'type': image.get('type', 'gallery'),
                            'alt_text': image.get('alt_text', ''),
                            'downloaded': False  # Set to True when actually downloaded
                        })
                        
                except Exception as e:
                    logger.error(f"Error downloading image {image_url}: {e}")
                    self.failed_count += 1
            
            # Update item with downloaded images info
            adapter['images'] = downloaded_images
            self.downloaded_count += len(downloaded_images)
            
            return item
            
        except Exception as e:
            logger.error(f"Error in image download pipeline: {e}")
            return item
    
    def close_spider(self, spider):
        """Called when spider closes"""
        logger.info(f"Image download pipeline closed. Downloaded: {self.downloaded_count}, Failed: {self.failed_count}")


class StatisticsPipeline:
    """Pipeline for collecting statistics"""
    
    def __init__(self):
        self.stats = {
            'total_items': 0,
            'platforms': {},
            'categories': {},
            'price_ranges': {},
            'ratings': {},
            'availability': {}
        }
    
    def process_item(self, item, spider):
        """Collect statistics from item"""
        try:
            adapter = ItemAdapter(item)
            
            self.stats['total_items'] += 1
            
            # Platform statistics
            platform = adapter.get('platform', 'unknown')
            self.stats['platforms'][platform] = self.stats['platforms'].get(platform, 0) + 1
            
            # Category statistics
            category = adapter.get('category', 'unknown')
            self.stats['categories'][category] = self.stats['categories'].get(category, 0) + 1
            
            # Price range statistics
            price = adapter.get('current_price')
            if price:
                price_range = self.get_price_range(price)
                self.stats['price_ranges'][price_range] = self.stats['price_ranges'].get(price_range, 0) + 1
            
            # Rating statistics
            rating = adapter.get('rating')
            if rating:
                rating_range = self.get_rating_range(rating)
                self.stats['ratings'][rating_range] = self.stats['ratings'].get(rating_range, 0) + 1
            
            # Availability statistics
            availability = adapter.get('availability_status', 'unknown')
            self.stats['availability'][availability] = self.stats['availability'].get(availability, 0) + 1
            
            return item
            
        except Exception as e:
            logger.error(f"Error collecting statistics: {e}")
            return item
    
    def get_price_range(self, price: float) -> str:
        """Get price range category"""
        if price < 10:
            return 'under_10'
        elif price < 50:
            return '10_50'
        elif price < 100:
            return '50_100'
        elif price < 500:
            return '100_500'
        elif price < 1000:
            return '500_1000'
        else:
            return 'over_1000'
    
    def get_rating_range(self, rating: float) -> str:
        """Get rating range category"""
        if rating < 2:
            return 'under_2'
        elif rating < 3:
            return '2_3'
        elif rating < 4:
            return '3_4'
        elif rating < 4.5:
            return '4_4.5'
        else:
            return '4.5_5'
    
    def close_spider(self, spider):
        """Print statistics when spider closes"""
        logger.info("=== SCRAPING STATISTICS ===")
        logger.info(f"Total items scraped: {self.stats['total_items']}")
        logger.info(f"Platforms: {self.stats['platforms']}")
        logger.info(f"Categories: {self.stats['categories']}")
        logger.info(f"Price ranges: {self.stats['price_ranges']}")
        logger.info(f"Ratings: {self.stats['ratings']}")
        logger.info(f"Availability: {self.stats['availability']}")
        logger.info("===========================")


class EcommercescraperPipeline:
    """Legacy pipeline for backward compatibility"""
    
    def process_item(self, item, spider):
        return item
