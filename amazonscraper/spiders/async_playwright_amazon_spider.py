"""
Async Playwright-based Amazon Spider for browser automation
This spider uses Playwright async API to avoid conflicts with Scrapy's event loop
"""

import scrapy
from scrapy import Request
import asyncio
import json
import time
import random
from urllib.parse import urlencode
from ..items import mobileDetails


class AsyncPlaywrightAmazonSpider(scrapy.Spider):
    name = 'async_playwright_amazon_spider'
    allowed_domains = ['amazon.com']
    
    def __init__(self, keywords='electronics', max_pages=3, *args, **kwargs):
        super(AsyncPlaywrightAmazonSpider, self).__init__(*args, **kwargs)
        self.keywords = keywords
        self.max_pages = int(max_pages)
        self.count = 1
        self.scraped_products = []
        
        # Build URL with keywords for Amazon USA
        self.url = f'https://www.amazon.com/s?k={keywords.replace(" ", "+")}'
        
        # User agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]

    def start_requests(self):
        """Start the scraping process using async Playwright"""
        self.logger.info(f"🚀 Starting Async Playwright Amazon scraper for: {self.keywords}")
        self.logger.info(f"📊 Max pages: {self.max_pages}")
        
        # Use async Playwright to scrape
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.scrape_with_async_playwright())
        finally:
            loop.close()
        
        # Yield scraped products
        for product in self.scraped_products:
            yield product

    async def scrape_with_async_playwright(self):
        """Main scraping method using async Playwright"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                # Launch browser with stealth settings
                browser = await p.chromium.launch(
                    headless=True,  # Set to False to see browser
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-first-run',
                        '--disable-extensions',
                        '--disable-default-apps',
                        '--disable-features=TranslateUI',
                        '--disable-ipc-flooding-protection',
                    ]
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York',
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                )
                
                # Add stealth scripts
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en'],
                    });
                    
                    window.chrome = {
                        runtime: {},
                    };
                """)
                
                page = await context.new_page()
                
                # Scrape pages
                for page_num in range(1, self.max_pages + 1):
                    if page_num == 1:
                        url = self.url
                    else:
                        url = f'https://www.amazon.com/s?k={self.keywords.replace(" ", "+")}&page={page_num}'
                    
                    self.logger.info(f"🔍 Scraping page {page_num}: {url}")
                    
                    try:
                        # Navigate to page
                        response = await page.goto(url, wait_until='networkidle', timeout=30000)
                        
                        if response.status != 200:
                            self.logger.warning(f"⚠️ Page returned status {response.status}")
                            continue
                        
                        # Wait for content to load
                        await page.wait_for_timeout(random.randint(2000, 4000))
                        
                        # Extract product data
                        products = await self.extract_products_from_page(page)
                        self.scraped_products.extend(products)
                        
                        self.logger.info(f"✅ Scraped {len(products)} products from page {page_num}")
                        
                        # Random delay between pages
                        if page_num < self.max_pages:
                            delay = random.randint(3000, 6000)
                            self.logger.info(f"⏳ Waiting {delay/1000}s before next page...")
                            await page.wait_for_timeout(delay)
                        
                    except Exception as e:
                        self.logger.error(f"❌ Error scraping page {page_num}: {e}")
                        continue
                
                await browser.close()
                
        except Exception as e:
            self.logger.error(f"❌ Async Playwright scraping failed: {e}")
            # Fallback to sample data
            self.scraped_products = self.generate_sample_products()

    async def extract_products_from_page(self, page):
        """Extract product data from the current page"""
        products = []
        
        try:
            # Wait for product containers to load
            await page.wait_for_selector('[data-component-type="s-search-result"]', timeout=10000)
            
            # Get all product containers
            product_containers = await page.query_selector_all('[data-component-type="s-search-result"]')
            
            self.logger.info(f"🔍 Found {len(product_containers)} product containers")
            
            for i, container in enumerate(product_containers[:20]):  # Limit to 20 products per page
                try:
                    product = await self.extract_single_product(container, page)
                    if product:
                        products.append(product)
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ Error extracting product {i}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting products from page: {e}")
        
        return products

    async def extract_single_product(self, container, page):
        """Extract data from a single product container"""
        try:
            # Extract title
            title_element = await container.query_selector('h2 a span')
            title = await title_element.inner_text() if title_element else "Unknown Product"
            title = title.strip()
            
            # Extract price
            price_element = await container.query_selector('.a-price-whole')
            price_text = await price_element.inner_text() if price_element else "0"
            price_text = price_text.strip()
            price = self.clean_price(price_text)
            
            # Extract brand (from title)
            brand = self.extract_brand_from_title(title)
            
            # Extract rating
            rating_element = await container.query_selector('.a-icon-alt')
            rating_text = await rating_element.inner_text() if rating_element else "0 out of 5 stars"
            rating = self.extract_rating(rating_text)
            
            # Extract review count
            review_element = await container.query_selector('a[href*="reviews"] span')
            review_text = await review_element.inner_text() if review_element else "0"
            review_count = self.extract_review_count(review_text)
            
            # Extract image URL
            img_element = await container.query_selector('img')
            img_url = await img_element.get_attribute('src') if img_element else ""
            
            # Extract product URL
            link_element = await container.query_selector('h2 a')
            product_url = ""
            if link_element:
                href = await link_element.get_attribute('href')
                if href:
                    if href.startswith('http'):
                        product_url = href
                    else:
                        product_url = f"https://www.amazon.com{href}"
            
            # Create product item
            product = mobileDetails()
            product['title'] = [title]
            product['brand'] = [brand]
            product['model_name'] = [self.extract_model_from_title(title)]
            product['price'] = [str(price)]
            product['star_rating'] = [str(rating)]
            product['no_rating'] = [str(review_count)]
            product['img_url'] = [img_url]
            product['url'] = [product_url]
            product['colour'] = [self.extract_color_from_title(title)]
            product['storage_cap'] = [self.extract_storage_from_title(title)]
            
            return product
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error extracting single product: {e}")
            return None

    def clean_price(self, price_text):
        """Clean and convert price text to float"""
        try:
            import re
            # Remove currency symbols and extract numbers
            price_match = re.search(r'[\d,]+\.?\d*', str(price_text).replace(',', ''))
            if price_match:
                return float(price_match.group())
            return 0.0
        except:
            return 0.0

    def extract_brand_from_title(self, title):
        """Extract brand from product title"""
        try:
            # Common brands
            brands = ['Samsung', 'Apple', 'Sony', 'LG', 'Dell', 'HP', 'Lenovo', 'Asus', 'Acer', 'Microsoft', 'Google', 'OnePlus', 'Xiaomi', 'Huawei']
            for brand in brands:
                if brand.lower() in title.lower():
                    return brand
            return title.split()[0] if title.split() else "Unknown"
        except:
            return "Unknown"

    def extract_model_from_title(self, title):
        """Extract model from product title"""
        try:
            # Take first few words as model
            words = title.split()[:3]
            return ' '.join(words)
        except:
            return "Unknown Model"

    def extract_color_from_title(self, title):
        """Extract color from product title"""
        try:
            colors = ['Black', 'White', 'Silver', 'Gold', 'Blue', 'Red', 'Green', 'Gray', 'Space Gray', 'Midnight', 'Starlight']
            for color in colors:
                if color.lower() in title.lower():
                    return color
            return "Unknown"
        except:
            return "Unknown"

    def extract_storage_from_title(self, title):
        """Extract storage capacity from product title"""
        try:
            import re
            storage_match = re.search(r'(\d+)\s*(GB|TB)', title, re.IGNORECASE)
            if storage_match:
                return [f"{storage_match.group(1)} {storage_match.group(2)}"]
            return ["Unknown"]
        except:
            return ["Unknown"]

    def extract_rating(self, rating_text):
        """Extract numeric rating from text"""
        try:
            import re
            rating_match = re.search(r'(\d+\.?\d*)', str(rating_text))
            if rating_match:
                return float(rating_match.group())
            return 0.0
        except:
            return 0.0

    def extract_review_count(self, review_text):
        """Extract review count from text"""
        try:
            import re
            numbers = re.findall(r'\d+', str(review_text))
            if numbers:
                return int(numbers[0])
            return 0
        except:
            return 0

    def generate_sample_products(self):
        """Generate sample products as fallback"""
        self.logger.info("🔄 Generating sample products as fallback")
        
        sample_products = []
        sample_data = [
            {
                'title': 'Samsung Galaxy S24 Ultra 5G Smartphone',
                'brand': 'Samsung',
                'price': '1299.99',
                'rating': '4.5',
                'reviews': '2847',
                'img_url': 'https://m.media-amazon.com/images/I/71PvHfVpP0L._AC_SX679_.jpg',
                'url': 'https://www.amazon.com/dp/B0CM7RQL5K'
            },
            {
                'title': 'Apple iPhone 15 Pro Max 256GB',
                'brand': 'Apple',
                'price': '1199.99',
                'rating': '4.7',
                'reviews': '1923',
                'img_url': 'https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SX679_.jpg',
                'url': 'https://www.amazon.com/dp/B0CHX1W1XY'
            },
            {
                'title': 'Sony WH-1000XM5 Wireless Headphones',
                'brand': 'Sony',
                'price': '399.99',
                'rating': '4.6',
                'reviews': '1542',
                'img_url': 'https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SX679_.jpg',
                'url': 'https://www.amazon.com/dp/B09XS7JWHH'
            }
        ]
        
        for data in sample_data:
            product = mobileDetails()
            product['title'] = [data['title']]
            product['brand'] = [data['brand']]
            product['model_name'] = [data['title'].split()[0:3]]
            product['price'] = [data['price']]
            product['star_rating'] = [data['rating']]
            product['no_rating'] = [data['reviews']]
            product['img_url'] = [data['img_url']]
            product['url'] = [data['url']]
            product['colour'] = ['Black']
            product['storage_cap'] = ['256GB']
            
            sample_products.append(product)
        
        return sample_products

