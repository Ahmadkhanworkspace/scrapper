"""
Data processing pipeline for Unified E-commerce Product Data Aggregator
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import re

from amazonscraper.items import ProductItem, AmazonProductItem, ImageItem, SpecificationItem, VariationItem
from database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and normalize scraped data"""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.curation_rules = self.load_curation_rules()
    
    def load_curation_rules(self) -> Dict[str, Any]:
        """Load curation and filtering rules"""
        return {
            'min_rating': 4.0,
            'min_review_count': 10,
            'required_fields': ['title', 'current_price', 'product_url'],
            'excluded_categories': ['adult', 'tobacco', 'alcohol', 'weapons'],
            'price_ranges': {
                'electronics': {'min': 10, 'max': 10000},
                'clothing': {'min': 5, 'max': 1000},
                'books': {'min': 1, 'max': 200},
                'home': {'min': 5, 'max': 5000},
                'default': {'min': 1, 'max': 10000}
            },
            'brand_whitelist': [],  # Empty means all brands allowed
            'brand_blacklist': ['generic', 'unbranded', 'no name']
        }
    
    def process_product(self, item: ProductItem) -> Optional[Dict[str, Any]]:
        """Process and validate a product item"""
        try:
            # Convert item to dictionary
            product_data = dict(item)
            
            # Validate required fields
            if not self.validate_required_fields(product_data):
                logger.warning(f"Product missing required fields: {product_data.get('external_id', 'unknown')}")
                return None
            
            # Apply curation rules
            if not self.apply_curation_rules(product_data):
                logger.info(f"Product filtered out by curation rules: {product_data.get('external_id', 'unknown')}")
                return None
            
            # Normalize data
            normalized_data = self.normalize_product_data(product_data)
            
            # Calculate additional fields
            normalized_data = self.calculate_additional_fields(normalized_data)
            
            return normalized_data
            
        except Exception as e:
            logger.error(f"Error processing product: {e}")
            return None
    
    def validate_required_fields(self, product_data: Dict[str, Any]) -> bool:
        """Validate that product has required fields"""
        required_fields = self.curation_rules['required_fields']
        
        for field in required_fields:
            if not product_data.get(field):
                return False
        
        return True
    
    def apply_curation_rules(self, product_data: Dict[str, Any]) -> bool:
        """Apply curation and filtering rules"""
        try:
            # Check rating
            rating = product_data.get('rating')
            if rating and rating < self.curation_rules['min_rating']:
                return False
            
            # Check review count
            review_count = product_data.get('review_count', 0)
            if review_count < self.curation_rules['min_review_count']:
                return False
            
            # Check excluded categories
            category = product_data.get('category', '').lower()
            for excluded in self.curation_rules['excluded_categories']:
                if excluded in category:
                    return False
            
            # Check price range
            current_price = product_data.get('current_price')
            if current_price:
                category = product_data.get('category', 'default')
                price_range = self.curation_rules['price_ranges'].get(category, self.curation_rules['price_ranges']['default'])
                
                if current_price < price_range['min'] or current_price > price_range['max']:
                    return False
            
            # Check brand blacklist
            brand = product_data.get('brand', '').lower()
            for blacklisted_brand in self.curation_rules['brand_blacklist']:
                if blacklisted_brand in brand:
                    return False
            
            # Check availability
            availability = product_data.get('availability_status', '').lower()
            if availability == 'out_of_stock':
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying curation rules: {e}")
            return False
    
    def normalize_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize product data to standard format"""
        normalized = {}
        
        # Basic information
        normalized['external_id'] = self.clean_text(product_data.get('external_id', ''))
        normalized['platform'] = product_data.get('platform', '').lower()
        normalized['title'] = self.clean_text(product_data.get('title', ''))
        normalized['description'] = self.clean_text(product_data.get('description', ''))
        normalized['brand'] = self.clean_text(product_data.get('brand', ''))
        normalized['model'] = self.clean_text(product_data.get('model', ''))
        
        # Pricing
        normalized['current_price'] = self.normalize_price(product_data.get('current_price'))
        normalized['original_price'] = self.normalize_price(product_data.get('original_price'))
        normalized['currency'] = product_data.get('currency', 'USD').upper()
        
        # Availability
        normalized['availability_status'] = self.normalize_availability(product_data.get('availability_status', ''))
        
        # Reviews
        normalized['rating'] = self.normalize_rating(product_data.get('rating'))
        normalized['review_count'] = self.normalize_review_count(product_data.get('review_count'))
        
        # Categorization
        normalized['category'] = self.normalize_category(product_data.get('category', ''))
        normalized['subcategory'] = self.normalize_category(product_data.get('subcategory', ''))
        
        # URLs
        normalized['product_url'] = product_data.get('product_url', '')
        
        # Images
        normalized['images'] = self.normalize_images(product_data.get('images', []))
        
        # Specifications
        normalized['specifications'] = self.normalize_specifications(product_data.get('specifications', {}))
        
        # Variations
        normalized['variations'] = self.normalize_variations(product_data.get('variations', []))
        
        # Metadata
        normalized['scraped_at'] = product_data.get('scraped_at', datetime.now().isoformat())
        normalized['spider_name'] = product_data.get('spider_name', '')
        
        return normalized
    
    def normalize_price(self, price: Any) -> Optional[float]:
        """Normalize price to float"""
        if price is None:
            return None
        
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            # Remove currency symbols and clean
            cleaned = re.sub(r'[^\d.,]', '', price)
            try:
                return float(cleaned.replace(',', ''))
            except (ValueError, TypeError):
                pass
        
        return None
    
    def normalize_availability(self, availability: str) -> str:
        """Normalize availability status"""
        if not availability:
            return 'unknown'
        
        availability_lower = availability.lower().strip()
        
        if any(word in availability_lower for word in ['in stock', 'available', 'add to cart']):
            return 'in_stock'
        elif any(word in availability_lower for word in ['out of stock', 'unavailable', 'sold out']):
            return 'out_of_stock'
        elif any(word in availability_lower for word in ['pre-order', 'preorder', 'coming soon']):
            return 'pre_order'
        elif any(word in availability_lower for word in ['limited', 'few left', 'low stock']):
            return 'limited_stock'
        else:
            return 'unknown'
    
    def normalize_rating(self, rating: Any) -> Optional[float]:
        """Normalize rating to 1-5 scale"""
        if rating is None:
            return None
        
        if isinstance(rating, (int, float)):
            rating = float(rating)
            if rating > 5:
                rating = rating / 2  # Convert from 10-point scale
            return max(0, min(5, rating))
        
        if isinstance(rating, str):
            # Extract numeric rating
            match = re.search(r'(\d+\.?\d*)', rating)
            if match:
                try:
                    rating = float(match.group(1))
                    if rating > 5:
                        rating = rating / 2
                    return max(0, min(5, rating))
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def normalize_review_count(self, review_count: Any) -> Optional[int]:
        """Normalize review count to integer"""
        if review_count is None:
            return None
        
        if isinstance(review_count, int):
            return review_count
        
        if isinstance(review_count, str):
            # Extract number from text
            match = re.search(r'([\d,]+)', review_count)
            if match:
                try:
                    return int(match.group(1).replace(',', ''))
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def normalize_category(self, category: str) -> str:
        """Normalize category name"""
        if not category:
            return ''
        
        # Clean and standardize category names
        category = self.clean_text(category)
        
        # Map common variations to standard categories
        category_mapping = {
            'electronics': ['electronic', 'electronics & photo', 'computers & electronics'],
            'clothing': ['clothes', 'apparel', 'fashion', 'clothing, shoes & jewelry'],
            'home': ['home & kitchen', 'home improvement', 'home & garden'],
            'books': ['book', 'books & media', 'books & magazines'],
            'sports': ['sport', 'sports & outdoors', 'sports & recreation'],
            'beauty': ['beauty & personal care', 'health & beauty', 'cosmetics'],
            'toys': ['toy', 'toys & games', 'children\'s toys'],
            'automotive': ['auto', 'automotive & motorcycle', 'car & motorbike']
        }
        
        category_lower = category.lower()
        for standard, variations in category_mapping.items():
            if any(var in category_lower for var in variations):
                return standard
        
        return category
    
    def normalize_images(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize image data"""
        normalized_images = []
        
        for image in images:
            if isinstance(image, dict) and image.get('url'):
                normalized_images.append({
                    'url': image['url'],
                    'type': image.get('type', 'gallery'),
                    'alt_text': image.get('alt_text', ''),
                    'width': image.get('width'),
                    'height': image.get('height'),
                    'file_size': image.get('file_size')
                })
        
        return normalized_images
    
    def normalize_specifications(self, specifications: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize specifications"""
        normalized_specs = {}
        
        for key, value in specifications.items():
            if key and value:
                # Clean key and value
                clean_key = self.clean_text(str(key))
                clean_value = self.clean_text(str(value))
                
                if clean_key and clean_value:
                    normalized_specs[clean_key] = clean_value
        
        return normalized_specs
    
    def normalize_variations(self, variations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize variations"""
        normalized_variations = []
        
        for variation in variations:
            if isinstance(variation, dict) and variation.get('type') and variation.get('value'):
                normalized_variations.append({
                    'type': variation['type'].lower(),
                    'value': self.clean_text(variation['value']),
                    'price': self.normalize_price(variation.get('price')),
                    'availability': self.normalize_availability(variation.get('availability', 'in_stock')),
                    'external_variation_id': variation.get('external_variation_id')
                })
        
        return normalized_variations
    
    def calculate_additional_fields(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate additional fields"""
        # Calculate discount percentage
        current_price = product_data.get('current_price')
        original_price = product_data.get('original_price')
        
        if current_price and original_price and original_price > current_price:
            discount = ((original_price - current_price) / original_price) * 100
            product_data['discount_percentage'] = round(discount, 2)
        else:
            product_data['discount_percentage'] = 0
        
        # Determine if product is curated
        product_data['is_curated'] = self.is_product_curated(product_data)
        
        return product_data
    
    def is_product_curated(self, product_data: Dict[str, Any]) -> bool:
        """Determine if product meets curation criteria"""
        try:
            # Check rating
            rating = product_data.get('rating', 0)
            if rating < self.curation_rules['min_rating']:
                return False
            
            # Check review count
            review_count = product_data.get('review_count', 0)
            if review_count < self.curation_rules['min_review_count']:
                return False
            
            # Check availability
            availability = product_data.get('availability_status', '')
            if availability == 'out_of_stock':
                return False
            
            # Check if has images
            images = product_data.get('images', [])
            if not images:
                return False
            
            # Check if has specifications
            specifications = product_data.get('specifications', {})
            if not specifications:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking curation status: {e}")
            return False
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ''
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common unwanted characters
        text = re.sub(r'[\r\n\t]+', ' ', text)
        
        return text.strip()
    
    def save_to_database(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Save processed product to database"""
        try:
            # Insert main product data
            product_id = self.db_manager.insert_product(product_data)
            
            if product_id:
                # Insert specifications
                if product_data.get('specifications'):
                    self.db_manager.insert_product_specifications(product_id, product_data['specifications'])
                
                # Insert images
                if product_data.get('images'):
                    self.db_manager.insert_product_images(product_id, product_data['images'])
                
                # Insert variations
                if product_data.get('variations'):
                    self.db_manager.insert_product_variations(product_id, product_data['variations'])
                
                logger.info(f"Product saved to database: {product_id}")
                return product_id
            
        except Exception as e:
            logger.error(f"Error saving product to database: {e}")
            return None
    
    def process_and_save(self, item: ProductItem) -> Optional[str]:
        """Process product item and save to database"""
        try:
            # Process the item
            processed_data = self.process_product(item)
            
            if processed_data:
                # Save to database
                product_id = self.save_to_database(processed_data)
                return product_id
            
        except Exception as e:
            logger.error(f"Error processing and saving product: {e}")
            return None
        
        return None


# Global processor instance
data_processor = DataProcessor()


