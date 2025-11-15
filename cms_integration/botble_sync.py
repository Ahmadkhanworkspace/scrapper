"""
Botble CMS Integration Module
Handles syncing scraped products to Botble CMS backend
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BotbleCMSIntegration:
    def __init__(self, base_url: str, api_key: str, username: str = None, password: str = None):
        """
        Initialize Botble CMS integration
        
        Args:
            base_url: Botble CMS base URL (e.g., 'https://your-site.com')
            api_key: Botble CMS API key
            username: Botble CMS username (optional)
            password: Botble CMS password (optional)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}'
        })
        
        # Botble CMS endpoints
        self.endpoints = {
            'products': f'{self.base_url}/api/v1/products',
            'categories': f'{self.base_url}/api/v1/categories',
            'brands': f'{self.base_url}/api/v1/brands',
            'attributes': f'{self.base_url}/api/v1/attributes',
            'media': f'{self.base_url}/api/v1/media',
            'auth': f'{self.base_url}/api/v1/auth/login'
        }

    def authenticate(self) -> bool:
        """Authenticate with Botble CMS"""
        try:
            if not self.username or not self.password:
                logger.warning("No username/password provided for Botble CMS authentication")
                return True  # Assume API key authentication
            
            response = self.session.post(self.endpoints['auth'], json={
                'email': self.username,
                'password': self.password
            })
            
            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data:
                    self.session.headers.update({
                        'Authorization': f'Bearer {data["access_token"]}'
                    })
                    logger.info("Successfully authenticated with Botble CMS")
                    return True
            
            logger.error(f"Botble CMS authentication failed: {response.status_code}")
            return False
            
        except Exception as e:
            logger.error(f"Error authenticating with Botble CMS: {e}")
            return False

    def get_categories(self) -> List[Dict]:
        """Get all categories from Botble CMS"""
        try:
            response = self.session.get(self.endpoints['categories'])
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                logger.error(f"Failed to get categories: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []

    def get_brands(self) -> List[Dict]:
        """Get all brands from Botble CMS"""
        try:
            response = self.session.get(self.endpoints['brands'])
            if response.status_code == 200:
                return response.json().get('data', [])
            else:
                logger.error(f"Failed to get brands: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting brands: {e}")
            return []

    def create_category(self, name: str, parent_id: int = None) -> Optional[Dict]:
        """Create a new category in Botble CMS"""
        try:
            category_data = {
                'name': name,
                'description': f'Category for {name}',
                'status': 'published',
                'is_featured': False
            }
            
            if parent_id:
                category_data['parent_id'] = parent_id
            
            response = self.session.post(self.endpoints['categories'], json=category_data)
            
            if response.status_code == 201:
                logger.info(f"Created category: {name}")
                return response.json().get('data')
            else:
                logger.error(f"Failed to create category {name}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating category {name}: {e}")
            return None

    def create_brand(self, name: str) -> Optional[Dict]:
        """Create a new brand in Botble CMS"""
        try:
            brand_data = {
                'name': name,
                'description': f'Brand: {name}',
                'status': 'published',
                'is_featured': False
            }
            
            response = self.session.post(self.endpoints['brands'], json=brand_data)
            
            if response.status_code == 201:
                logger.info(f"Created brand: {name}")
                return response.json().get('data')
            else:
                logger.error(f"Failed to create brand {name}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating brand {name}: {e}")
            return None

    def upload_image(self, image_url: str, product_id: int = None) -> Optional[str]:
        """Upload image to Botble CMS"""
        try:
            # Download image from URL
            image_response = requests.get(image_url, timeout=30)
            if image_response.status_code != 200:
                logger.error(f"Failed to download image: {image_url}")
                return None
            
            # Upload to Botble CMS
            files = {
                'file': ('image.jpg', image_response.content, 'image/jpeg')
            }
            
            data = {}
            if product_id:
                data['product_id'] = product_id
            
            response = self.session.post(self.endpoints['media'], files=files, data=data)
            
            if response.status_code == 201:
                media_data = response.json().get('data')
                return media_data.get('url') if media_data else None
            else:
                logger.error(f"Failed to upload image: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            return None

    def sync_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync a single product to Botble CMS
        
        Args:
            product_data: Product data from scraper
            
        Returns:
            Dict with sync result
        """
        try:
            # Extract product information
            title = product_data.get('title', ['Unknown Product'])[0] if isinstance(product_data.get('title'), list) else product_data.get('title', 'Unknown Product')
            brand = product_data.get('brand', ['Unknown'])[0] if isinstance(product_data.get('brand'), list) else product_data.get('brand', 'Unknown')
            price = float(product_data.get('price', ['0'])[0]) if isinstance(product_data.get('price'), list) else float(product_data.get('price', 0))
            image_url = product_data.get('img_url', [''])[0] if isinstance(product_data.get('img_url'), list) else product_data.get('img_url', '')
            product_url = product_data.get('url', [''])[0] if isinstance(product_data.get('url'), list) else product_data.get('url', '')
            platform = product_data.get('platform', ['Amazon'])[0] if isinstance(product_data.get('platform'), list) else product_data.get('platform', 'Amazon')
            
            # Prepare product data for Botble CMS
            botble_product = {
                'name': title,
                'description': f'Product from {platform}: {title}',
                'content': f'<p>This product was automatically imported from {platform}.</p><p>Original URL: <a href="{product_url}">{product_url}</a></p>',
                'price': price,
                'sale_price': price,  # Assume no discount for now
                'sku': f"{platform.lower()}_{int(time.time())}",
                'status': 'published',
                'is_featured': False,
                'weight': 0,
                'length': 0,
                'width': 0,
                'height': 0,
                'stock_status': 'in_stock',
                'quantity': 999,  # Assume unlimited stock
                'meta_title': title,
                'meta_description': f'Buy {title} from {platform}',
                'meta_keywords': f'{title}, {brand}, {platform}',
                'external_url': product_url,
                'external_platform': platform
            }
            
            # Handle brand
            if brand and brand != 'Unknown':
                brands = self.get_brands()
                brand_obj = next((b for b in brands if b['name'].lower() == brand.lower()), None)
                
                if not brand_obj:
                    brand_obj = self.create_brand(brand)
                
                if brand_obj:
                    botble_product['brand_id'] = brand_obj['id']
            
            # Handle category (default to Electronics)
            categories = self.get_categories()
            category_obj = next((c for c in categories if 'electronics' in c['name'].lower()), None)
            
            if not category_obj:
                category_obj = self.create_category('Electronics')
            
            if category_obj:
                botble_product['categories'] = [category_obj['id']]
            
            # Upload image if available
            if image_url:
                uploaded_image_url = self.upload_image(image_url)
                if uploaded_image_url:
                    botble_product['images'] = [uploaded_image_url]
            
            # Create product in Botble CMS
            response = self.session.post(self.endpoints['products'], json=botble_product)
            
            if response.status_code == 201:
                created_product = response.json().get('data')
                logger.info(f"Successfully synced product: {title}")
                
                return {
                    'success': True,
                    'botble_id': created_product['id'],
                    'message': 'Product synced successfully',
                    'product_name': title,
                    'platform': platform
                }
            else:
                logger.error(f"Failed to sync product {title}: {response.status_code}")
                return {
                    'success': False,
                    'message': f'Failed to sync product: {response.status_code}',
                    'product_name': title,
                    'platform': platform
                }
                
        except Exception as e:
            logger.error(f"Error syncing product: {e}")
            return {
                'success': False,
                'message': str(e),
                'product_name': product_data.get('title', 'Unknown'),
                'platform': product_data.get('platform', 'Unknown')
            }

    def sync_multiple_products(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync multiple products to Botble CMS
        
        Args:
            products: List of product data from scraper
            
        Returns:
            Dict with sync results
        """
        results = {
            'total': len(products),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        logger.info(f"Starting sync of {len(products)} products to Botble CMS")
        
        for i, product in enumerate(products):
            try:
                result = self.sync_product(product)
                
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(result['message'])
                
                # Add delay between requests to avoid rate limiting
                if i < len(products) - 1:
                    time.sleep(1)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(str(e))
                logger.error(f"Error processing product {i}: {e}")
        
        logger.info(f"Sync completed: {results['successful']} successful, {results['failed']} failed")
        return results

    def update_product_price(self, botble_id: int, new_price: float) -> bool:
        """Update product price in Botble CMS"""
        try:
            update_data = {
                'price': new_price,
                'sale_price': new_price
            }
            
            response = self.session.put(f"{self.endpoints['products']}/{botble_id}", json=update_data)
            
            if response.status_code == 200:
                logger.info(f"Updated price for product {botble_id}: ${new_price}")
                return True
            else:
                logger.error(f"Failed to update price for product {botble_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
            return False

    def delete_product(self, botble_id: int) -> bool:
        """Delete product from Botble CMS"""
        try:
            response = self.session.delete(f"{self.endpoints['products']}/{botble_id}")
            
            if response.status_code == 200:
                logger.info(f"Deleted product {botble_id}")
                return True
            else:
                logger.error(f"Failed to delete product {botble_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False

    def get_product(self, botble_id: int) -> Optional[Dict]:
        """Get product from Botble CMS"""
        try:
            response = self.session.get(f"{self.endpoints['products']}/{botble_id}")
            
            if response.status_code == 200:
                return response.json().get('data')
            else:
                logger.error(f"Failed to get product {botble_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting product: {e}")
            return None

    def test_connection(self) -> bool:
        """Test connection to Botble CMS"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/health")
            return response.status_code == 200
        except:
            return False


# Example usage and testing
def test_botble_integration():
    """Test Botble CMS integration"""
    # Initialize with your Botble CMS details
    botble = BotbleCMSIntegration(
        base_url='https://your-botble-site.com',
        api_key='your-api-key',
        username='your-username',
        password='your-password'
    )
    
    # Test connection
    if botble.test_connection():
        print("✅ Botble CMS connection successful")
    else:
        print("❌ Botble CMS connection failed")
        return
    
    # Test authentication
    if botble.authenticate():
        print("✅ Botble CMS authentication successful")
    else:
        print("❌ Botble CMS authentication failed")
        return
    
    # Test product sync
    sample_product = {
        'title': ['Test Product from Scraper'],
        'brand': ['Test Brand'],
        'price': ['99.99'],
        'img_url': ['https://example.com/image.jpg'],
        'url': ['https://example.com/product'],
        'platform': ['Amazon']
    }
    
    result = botble.sync_product(sample_product)
    print(f"Product sync result: {result}")


if __name__ == '__main__':
    test_botble_integration()