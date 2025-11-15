"""
Enhanced Amazon spider with comprehensive data extraction
"""
import scrapy
import re
import json
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, Any, List, Optional
from datetime import datetime

from amazonscraper.spiders.base_spider import BaseEcommerceSpider
from amazonscraper.items import AmazonProductItem, ProductItem


class AmazonSpider(BaseEcommerceSpider):
    """Enhanced Amazon spider with comprehensive data extraction"""
    
    name = 'amazon'
    allowed_domains = ['amazon.com', 'amazon.co.uk', 'amazon.ca', 'amazon.in']
    
    # Amazon-specific settings
    custom_settings = {
        **BaseEcommerceSpider.custom_settings,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = kwargs.get('domain', 'amazon.com')
        self.category = kwargs.get('category', 'electronics')
        self.max_pages = int(kwargs.get('max_pages', 20))
        self.current_page = 1
        
        # Amazon-specific selectors
        self.selectors = {
            'product_links': [
                'div[data-component-type="s-search-result"] h2 a::attr(href)',
                'div.s-result-item h2 a::attr(href)',
                'div[data-asin] h2 a::attr(href)'
            ],
            'next_page': [
                'a[aria-label="Next Page"]::attr(href)',
                'a.s-pagination-next::attr(href)'
            ],
            'product_title': [
                '#productTitle::text',
                'h1.a-size-large::text',
                'span.a-size-large::text'
            ],
            'product_price': [
                '.a-price-whole::text',
                '.a-price .a-offscreen::text',
                '#priceblock_dealprice::text',
                '#priceblock_ourprice::text',
                '.a-price-range .a-offscreen::text'
            ],
            'original_price': [
                '.a-price.a-text-price .a-offscreen::text',
                '.a-price-was .a-offscreen::text'
            ],
            'product_images': [
                '#landingImage::attr(src)',
                '#imgBlkFront::attr(src)',
                '.a-dynamic-image::attr(src)',
                '.a-dynamic-image::attr(data-src)'
            ],
            'product_description': [
                '#feature-bullets ul li span::text',
                '.a-unordered-list .a-list-item::text'
            ],
            'product_specifications': [
                '#prodDetails .a-size-base::text',
                '.a-section .a-size-base::text'
            ],
            'product_rating': [
                '.a-icon-alt::text',
                '.a-icon-star .a-icon-alt::text',
                '[data-hook="rating-out-of-text"]::text'
            ],
            'review_count': [
                '#acrCustomerReviewText::text',
                '[data-hook="total-review-count"]::text',
                '.a-size-base::text'
            ],
            'availability': [
                '#availability span::text',
                '.a-size-medium.a-color-success::text',
                '.a-size-medium.a-color-price::text'
            ],
            'variations': [
                '.a-button-text::text',
                '.a-button-toggle-text::text'
            ]
        }
    
    def start_requests(self):
        """Generate initial requests for different Amazon categories"""
        categories = {
            'electronics': 'Electronics',
            'computers': 'Computers & Tablets',
            'home': 'Home & Kitchen',
            'fashion': 'Clothing, Shoes & Jewelry',
            'books': 'Books',
            'sports': 'Sports & Outdoors',
            'automotive': 'Automotive',
            'beauty': 'Beauty & Personal Care',
            'toys': 'Toys & Games',
            'garden': 'Garden & Outdoor'
        }
        
        if self.category in categories:
            search_term = categories[self.category]
        else:
            search_term = self.category
        
        # Generate search URLs for different Amazon domains
        search_urls = [
            f"https://www.{self.domain}/s?k={search_term}&ref=sr_pg_1",
            f"https://www.{self.domain}/s?k={search_term}&i=electronics&ref=sr_pg_1",
            f"https://www.{self.domain}/s?k={search_term}&i=computers&ref=sr_pg_1"
        ]
        
        for url in search_urls:
            yield self.make_request(url, callback=self.parse)
    
    def parse(self, response):
        """Parse search results page"""
        try:
            # Extract product links
            product_links = []
            for selector in self.selectors['product_links']:
                links = response.css(selector).getall()
                product_links.extend(links)
            
            # Remove duplicates and convert to absolute URLs
            unique_links = list(set(product_links))
            for link in unique_links:
                if link and '/dp/' in link:
                    product_url = urljoin(response.url, link)
                    yield self.make_request(
                        product_url, 
                        callback=self.parse_product,
                        meta={'category': self.category}
                    )
            
            # Follow next page if available
            if self.current_page < self.max_pages:
                next_page_url = None
                for selector in self.selectors['next_page']:
                    next_link = response.css(selector).get()
                    if next_link:
                        next_page_url = urljoin(response.url, next_link)
                        break
                
                if next_page_url:
                    self.current_page += 1
                    yield self.make_request(next_page_url, callback=self.parse)
                    
        except Exception as e:
            self.log_error(e, "parse")
    
    def parse_product(self, response):
        """Parse individual product page"""
        try:
            item = AmazonProductItem()
            
            # Extract basic information
            item['platform'] = 'amazon'
            item['external_id'] = self.get_external_id(response.url)
            item['product_url'] = response.url
            
            # Extract title
            title = self.extract_text(response, self.selectors['product_title'])
            item['title'] = title
            
            # Extract brand and model from title
            if title:
                item['brand'], item['model'] = self.extract_brand_model(title)
            
            # Extract pricing information
            current_price = self.extract_price_from_selectors(response, self.selectors['product_price'])
            original_price = self.extract_price_from_selectors(response, self.selectors['original_price'])
            
            item['current_price'] = current_price
            item['original_price'] = original_price
            item['currency'] = self.extract_currency(response)
            
            if current_price and original_price and original_price > current_price:
                discount = ((original_price - current_price) / original_price) * 100
                item['discount_percentage'] = round(discount, 2)
            
            # Extract availability
            availability_text = self.extract_text(response, self.selectors['availability'])
            item['availability_status'] = self.normalize_availability(availability_text)
            
            # Extract rating and review count
            rating_text = self.extract_text(response, self.selectors['product_rating'])
            item['rating'] = self.extract_rating(rating_text)
            
            review_text = self.extract_text(response, self.selectors['review_count'])
            item['review_count'] = self.extract_review_count(review_text)
            
            # Extract description and bullet points
            description = self.extract_text(response, ['#productDescription p::text'])
            item['description'] = description
            
            bullet_points = self.extract_bullet_points(response)
            item['bullet_points'] = bullet_points
            
            # Extract images
            images = self.extract_images(response, self.selectors['product_images'])
            item['images'] = images
            
            # Extract specifications
            specifications = self.extract_amazon_specifications(response)
            item['specifications'] = specifications
            
            # Extract variations
            variations = self.extract_amazon_variations(response)
            item['variations'] = variations
            
            # Extract Amazon-specific information
            item['asin'] = self.extract_asin(response.url)
            item['seller_name'] = self.extract_seller_info(response)
            item['prime_eligible'] = self.check_prime_eligibility(response)
            item['fulfillment'] = self.extract_fulfillment_info(response)
            
            # Extract category information
            item['category'] = self.extract_category(response)
            item['subcategory'] = response.meta.get('category', 'electronics')
            
            # Process and yield item
            processed_item = self.process_product_item(item)
            if processed_item:
                yield processed_item
                
        except Exception as e:
            self.log_error(e, f"parse_product - {response.url}")
    
    def extract_text(self, response, selectors: List[str]) -> Optional[str]:
        """Extract text using multiple selectors"""
        for selector in selectors:
            text = response.css(selector).get()
            if text:
                return self.clean_text(text)
        return None
    
    def extract_price_from_selectors(self, response, selectors: List[str]) -> Optional[float]:
        """Extract price using multiple selectors"""
        for selector in selectors:
            price_text = response.css(selector).get()
            if price_text:
                price = self.extract_price(price_text)
                if price:
                    return price
        return None
    
    def extract_brand_model(self, title: str) -> tuple:
        """Extract brand and model from product title"""
        if not title:
            return None, None
        
        # Common brand patterns
        brands = [
            'Apple', 'Samsung', 'Sony', 'Microsoft', 'Google', 'Amazon', 'Dell', 'HP', 'Lenovo',
            'Asus', 'Acer', 'LG', 'Panasonic', 'Canon', 'Nikon', 'Bose', 'JBL', 'Beats',
            'Nike', 'Adidas', 'Puma', 'Under Armour', 'Calvin Klein', 'Levi\'s', 'Gap'
        ]
        
        title_lower = title.lower()
        brand = None
        model = None
        
        for b in brands:
            if b.lower() in title_lower:
                brand = b
                break
        
        # Extract model (usually after brand)
        if brand:
            brand_index = title_lower.find(brand.lower())
            if brand_index != -1:
                after_brand = title[brand_index + len(brand):].strip()
                # Take first few words as model
                model_words = after_brand.split()[:3]
                model = ' '.join(model_words) if model_words else None
        
        return brand, model
    
    def extract_currency(self, response) -> str:
        """Extract currency from response"""
        # Check for currency symbols in price elements
        currency_text = response.css('.a-price-symbol::text').get()
        if currency_text:
            currency_map = {
                '$': 'USD',
                '€': 'EUR',
                '£': 'GBP',
                '₹': 'INR',
                '¥': 'JPY',
                'C$': 'CAD'
            }
            return currency_map.get(currency_text.strip(), 'USD')
        
        # Default based on domain
        domain_currency = {
            'amazon.com': 'USD',
            'amazon.co.uk': 'GBP',
            'amazon.ca': 'CAD',
            'amazon.in': 'INR'
        }
        return domain_currency.get(self.domain, 'USD')
    
    def extract_bullet_points(self, response) -> List[str]:
        """Extract bullet points from product description"""
        bullet_points = []
        
        # Try different selectors for bullet points
        selectors = [
            '#feature-bullets ul li span::text',
            '.a-unordered-list .a-list-item::text',
            '#feature-bullets ul li::text'
        ]
        
        for selector in selectors:
            points = response.css(selector).getall()
            for point in points:
                cleaned_point = self.clean_text(point)
                if cleaned_point and len(cleaned_point) > 10:  # Filter out short/empty points
                    bullet_points.append(cleaned_point)
        
        return bullet_points[:10]  # Limit to 10 bullet points
    
    def extract_amazon_specifications(self, response) -> Dict[str, Any]:
        """Extract Amazon-specific product specifications"""
        specifications = {}
        
        # Try to extract from technical details table
        tech_details = response.css('#prodDetails .a-size-base')
        for detail in tech_details:
            text = detail.css('::text').get()
            if text and ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    specifications[key] = value
        
        # Extract from additional details
        additional_details = response.css('#detailBulletsWrapper_feature_div .a-list-item')
        for detail in additional_details:
            text = detail.css('::text').get()
            if text and ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    specifications[key] = value
        
        return specifications
    
    def extract_amazon_variations(self, response) -> List[Dict[str, Any]]:
        """Extract Amazon product variations"""
        variations = []
        
        # Extract color variations
        color_selectors = [
            '#variation_color_name .a-button-text::text',
            '.a-button-toggle-text::text'
        ]
        
        for selector in color_selectors:
            colors = response.css(selector).getall()
            for color in colors:
                if color and color.strip():
                    variations.append({
                        'type': 'color',
                        'value': color.strip(),
                        'price': None,
                        'availability': 'in_stock'
                    })
        
        # Extract size variations
        size_selectors = [
            '#variation_size_name .a-button-text::text',
            '.a-button-toggle-text::text'
        ]
        
        for selector in size_selectors:
            sizes = response.css(selector).getall()
            for size in sizes:
                if size and size.strip():
                    variations.append({
                        'type': 'size',
                        'value': size.strip(),
                        'price': None,
                        'availability': 'in_stock'
                    })
        
        return variations
    
    def extract_asin(self, url: str) -> Optional[str]:
        """Extract ASIN from Amazon URL"""
        # ASIN is usually in the URL path after /dp/
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)
        return None
    
    def extract_seller_info(self, response) -> Optional[str]:
        """Extract seller information"""
        seller_selectors = [
            '#merchant-info .a-size-small::text',
            '.a-size-small::text'
        ]
        
        for selector in seller_selectors:
            seller_text = response.css(selector).get()
            if seller_text and 'sold by' in seller_text.lower():
                return seller_text.strip()
        
        return None
    
    def check_prime_eligibility(self, response) -> bool:
        """Check if product is Prime eligible"""
        prime_indicators = [
            '.a-icon-prime',
            '[data-hook="prime-badge"]',
            '.a-icon-prime::text'
        ]
        
        for indicator in prime_indicators:
            if response.css(indicator).get():
                return True
        
        return False
    
    def extract_fulfillment_info(self, response) -> Optional[str]:
        """Extract fulfillment information"""
        fulfillment_text = response.css('#merchant-info .a-size-small::text').get()
        if fulfillment_text:
            if 'fulfilled by amazon' in fulfillment_text.lower():
                return 'amazon'
            elif 'sold and shipped' in fulfillment_text.lower():
                return 'seller'
        
        return None
    
    def extract_category(self, response) -> Optional[str]:
        """Extract product category from breadcrumbs"""
        breadcrumb_selectors = [
            '#wayfinding-breadcrumbs_feature_div .a-link-normal::text',
            '.a-breadcrumb .a-link-normal::text'
        ]
        
        categories = []
        for selector in breadcrumb_selectors:
            breadcrumbs = response.css(selector).getall()
            categories.extend(breadcrumbs)
        
        if categories:
            # Return the main category (usually the second breadcrumb)
            return categories[1] if len(categories) > 1 else categories[0]
        
        return None
    
    def get_external_id(self, url: str) -> str:
        """Extract external product ID from Amazon URL"""
        # Try to extract ASIN first
        asin = self.extract_asin(url)
        if asin:
            return asin
        
        # Fallback to URL path
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        return path_parts[-1] if path_parts else url


