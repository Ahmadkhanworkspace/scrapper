"""
Data Deduplication System for Unified E-commerce Product Data Aggregator
"""
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
import re
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ProductDeduplicator:
    """
    Advanced product deduplication system that identifies and prevents duplicate products
    across different e-commerce platforms.
    """
    
    def __init__(self):
        self.similarity_threshold = 0.85  # 85% similarity threshold
        self.title_weight = 0.4
        self.brand_weight = 0.3
        self.price_weight = 0.2
        self.specs_weight = 0.1
        
    def find_duplicates(self, products: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Find duplicate products in a list of products.
        Returns a list of duplicate groups, where each group contains product IDs.
        """
        duplicate_groups = []
        processed_products = set()
        
        for i, product1 in enumerate(products):
            if product1['external_id'] in processed_products:
                continue
                
            duplicate_group = [product1['external_id']]
            
            for j, product2 in enumerate(products[i+1:], i+1):
                if product2['external_id'] in processed_products:
                    continue
                    
                if self._are_duplicates(product1, product2):
                    duplicate_group.append(product2['external_id'])
                    processed_products.add(product2['external_id'])
            
            if len(duplicate_group) > 1:
                duplicate_groups.append(duplicate_group)
                for product_id in duplicate_group:
                    processed_products.add(product_id)
        
        return duplicate_groups
    
    def _are_duplicates(self, product1: Dict[str, Any], product2: Dict[str, Any]) -> bool:
        """
        Determine if two products are duplicates based on multiple criteria.
        """
        # Skip if same platform and external_id
        if (product1['platform'] == product2['platform'] and 
            product1['external_id'] == product2['external_id']):
            return True
        
        # Calculate similarity score
        similarity_score = self._calculate_similarity(product1, product2)
        
        return similarity_score >= self.similarity_threshold
    
    def _calculate_similarity(self, product1: Dict[str, Any], product2: Dict[str, Any]) -> float:
        """
        Calculate similarity score between two products.
        """
        scores = []
        
        # Title similarity
        title_sim = self._text_similarity(
            product1.get('title', ''),
            product2.get('title', '')
        )
        scores.append(title_sim * self.title_weight)
        
        # Brand similarity
        brand_sim = self._text_similarity(
            product1.get('brand', ''),
            product2.get('brand', '')
        )
        scores.append(brand_sim * self.brand_weight)
        
        # Price similarity
        price_sim = self._price_similarity(
            product1.get('current_price'),
            product2.get('current_price')
        )
        scores.append(price_sim * self.price_weight)
        
        # Specifications similarity
        specs_sim = self._specifications_similarity(
            product1.get('specifications', []),
            product2.get('specifications', [])
        )
        scores.append(specs_sim * self.specs_weight)
        
        return sum(scores)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using multiple methods.
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize text
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)
        
        if text1 == text2:
            return 1.0
        
        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, text1, text2).ratio()
        
        # Check for partial matches (e.g., "iPhone 13" vs "Apple iPhone 13")
        if similarity < 0.8:
            similarity = max(similarity, self._partial_text_match(text1, text2))
        
        return similarity
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and extra spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = text.split()
        words = [word for word in words if word not in common_words]
        
        return ' '.join(words).strip()
    
    def _partial_text_match(self, text1: str, text2: str) -> float:
        """
        Check for partial text matches.
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _price_similarity(self, price1: Optional[float], price2: Optional[float]) -> float:
        """
        Calculate price similarity.
        """
        if price1 is None or price2 is None:
            return 0.0
        
        if price1 == price2:
            return 1.0
        
        # Allow for small price differences (within 10%)
        price_diff = abs(price1 - price2)
        avg_price = (price1 + price2) / 2
        
        if avg_price == 0:
            return 0.0
        
        price_ratio = price_diff / avg_price
        
        # Return similarity based on price difference
        if price_ratio <= 0.1:  # Within 10%
            return 1.0 - price_ratio
        elif price_ratio <= 0.2:  # Within 20%
            return 0.8 - (price_ratio - 0.1) * 2
        else:
            return max(0.0, 0.6 - (price_ratio - 0.2) * 2)
    
    def _specifications_similarity(self, specs1: List[Dict[str, Any]], specs2: List[Dict[str, Any]]) -> float:
        """
        Calculate specifications similarity.
        """
        if not specs1 or not specs2:
            return 0.0
        
        # Convert specs to dictionaries for easier comparison
        specs_dict1 = {spec.get('spec_name', '').lower(): spec.get('spec_value', '').lower() 
                      for spec in specs1 if spec.get('spec_name')}
        specs_dict2 = {spec.get('spec_name', '').lower(): spec.get('spec_value', '').lower() 
                      for spec in specs2 if spec.get('spec_name')}
        
        if not specs_dict1 or not specs_dict2:
            return 0.0
        
        # Find common specifications
        common_specs = set(specs_dict1.keys()).intersection(set(specs_dict2.keys()))
        
        if not common_specs:
            return 0.0
        
        # Calculate similarity for common specs
        total_similarity = 0.0
        for spec_name in common_specs:
            spec_similarity = self._text_similarity(specs_dict1[spec_name], specs_dict2[spec_name])
            total_similarity += spec_similarity
        
        return total_similarity / len(common_specs)
    
    def generate_fingerprint(self, product: Dict[str, Any]) -> str:
        """
        Generate a unique fingerprint for a product to aid in deduplication.
        """
        fingerprint_data = {
            'title': self._normalize_text(product.get('title', '')),
            'brand': self._normalize_text(product.get('brand', '')),
            'category': self._normalize_text(product.get('category', '')),
            'price_range': self._get_price_range(product.get('current_price')),
            'key_specs': self._extract_key_specs(product.get('specifications', []))
        }
        
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(fingerprint_string.encode()).hexdigest()
    
    def _get_price_range(self, price: Optional[float]) -> str:
        """
        Get price range category for fingerprinting.
        """
        if price is None:
            return 'unknown'
        
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
    
    def _extract_key_specs(self, specifications: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Extract key specifications for fingerprinting.
        """
        key_specs = {}
        important_specs = ['color', 'size', 'model', 'capacity', 'storage', 'memory', 'screen size', 'weight']
        
        for spec in specifications:
            spec_name = spec.get('spec_name', '').lower()
            spec_value = spec.get('spec_value', '').lower()
            
            for important_spec in important_specs:
                if important_spec in spec_name:
                    key_specs[important_spec] = spec_value
                    break
        
        return key_specs
    
    def resolve_duplicates(self, duplicate_groups: List[List[str]], products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Resolve duplicate groups by keeping the best product from each group.
        """
        product_dict = {product['external_id']: product for product in products}
        resolved_products = []
        processed_ids = set()
        
        # Process duplicate groups
        for group in duplicate_groups:
            best_product = self._select_best_product([product_dict[pid] for pid in group])
            resolved_products.append(best_product)
            processed_ids.update(group)
        
        # Add non-duplicate products
        for product in products:
            if product['external_id'] not in processed_ids:
                resolved_products.append(product)
        
        return resolved_products
    
    def _select_best_product(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the best product from a group of duplicates.
        """
        if len(products) == 1:
            return products[0]
        
        # Scoring criteria
        best_product = products[0]
        best_score = self._calculate_product_score(best_product)
        
        for product in products[1:]:
            score = self._calculate_product_score(product)
            if score > best_score:
                best_product = product
                best_score = score
        
        return best_product
    
    def _calculate_product_score(self, product: Dict[str, Any]) -> float:
        """
        Calculate a quality score for a product.
        """
        score = 0.0
        
        # Completeness score
        required_fields = ['title', 'brand', 'current_price', 'description']
        completeness = sum(1 for field in required_fields if product.get(field)) / len(required_fields)
        score += completeness * 0.3
        
        # Rating score
        rating = product.get('rating', 0)
        if rating:
            score += (rating / 5.0) * 0.3
        
        # Review count score
        review_count = product.get('review_count', 0)
        if review_count > 0:
            score += min(review_count / 1000.0, 1.0) * 0.2
        
        # Image count score
        images = product.get('images', [])
        if images:
            score += min(len(images) / 5.0, 1.0) * 0.1
        
        # Specifications score
        specs = product.get('specifications', [])
        if specs:
            score += min(len(specs) / 10.0, 1.0) * 0.1
        
        return score
    
    def deduplicate_database(self, db_manager) -> Dict[str, Any]:
        """
        Perform deduplication on the entire database.
        """
        logger.info("Starting database deduplication process...")
        
        # Get all products from database
        products = db_manager.get_all_products()
        
        if not products:
            logger.info("No products found in database for deduplication.")
            return {'duplicates_found': 0, 'products_removed': 0}
        
        logger.info(f"Found {len(products)} products for deduplication analysis.")
        
        # Find duplicates
        duplicate_groups = self.find_duplicates(products)
        
        logger.info(f"Found {len(duplicate_groups)} duplicate groups.")
        
        # Resolve duplicates
        resolved_products = self.resolve_duplicates(duplicate_groups, products)
        
        # Calculate statistics
        duplicates_found = sum(len(group) - 1 for group in duplicate_groups)
        products_removed = len(products) - len(resolved_products)
        
        logger.info(f"Deduplication complete: {duplicates_found} duplicates found, {products_removed} products removed.")
        
        return {
            'duplicates_found': duplicates_found,
            'products_removed': products_removed,
            'duplicate_groups': duplicate_groups,
            'final_count': len(resolved_products)
        }

# Global deduplicator instance
deduplicator = ProductDeduplicator()


