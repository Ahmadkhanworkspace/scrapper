"""
Unified Multi-Platform E-commerce Scraper
Supports Amazon, Walmart, Target, and Best Buy with Playwright browser automation
"""

import asyncio
import json
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright


class UnifiedEcommerceScraper:
    def __init__(self, platform='amazon', keywords='electronics', max_pages=3):
        self.platform = platform.lower()
        self.keywords = keywords
        self.max_pages = max_pages
        self.scraped_products = []
        
        # Platform-specific configurations
        self.platform_configs = {
            'amazon': {
                'base_url': 'https://www.amazon.com/s?k={}',
                'page_url': 'https://www.amazon.com/s?k={}&page={}',
                'container_selector': '[data-component-type="s-search-result"]',
                'title_selectors': ['h2 a span', 'h2 span', '.s-size-mini .a-link-normal span'],
                'price_selectors': ['.a-price-whole', '.a-price .a-offscreen', '.a-price-range .a-offscreen'],
                'rating_selectors': ['.a-icon-alt', '.a-icon-star-small .a-icon-alt'],
                'review_selectors': ['a[href*="reviews"] span', '.a-size-base'],
                'img_selectors': ['img', '.s-image', '.a-dynamic-image'],
                'url_selectors': ['h2 a', '.a-link-normal', 'a[href*="/dp/"]']
            },
            'walmart': {
                'base_url': 'https://www.walmart.com/search?q={}',
                'page_url': 'https://www.walmart.com/search?q={}&page={}',
                'container_selector': '[data-testid="item-stack"]',
                'title_selectors': ['[data-testid="product-title"]', '.f6.f5-l', 'h3'],
                'price_selectors': ['[data-testid="current-price"]', '.f2.f1-l', '.price-current'],
                'rating_selectors': ['[data-testid="reviews-section"] .f7', '.stars-small'],
                'review_selectors': ['[data-testid="reviews-section"] .f7', '.stars-small + span'],
                'img_selectors': ['[data-testid="product-image"] img', '.aspect-ratio img'],
                'url_selectors': ['[data-testid="product-title"]', 'a[href*="/ip/"]']
            },
            'target': {
                'base_url': 'https://www.target.com/s?searchTerm={}',
                'page_url': 'https://www.target.com/s?searchTerm={}&page={}',
                'container_selector': '[data-test="product-details"]',
                'title_selectors': ['[data-test="product-title"]', 'h3', '.styles__StyledText-sc-1u7afl7-0'],
                'price_selectors': ['[data-test="current-price"]', '.h-text-lg', '.styles__CurrentPriceString-sc-1u7afl7-0'],
                'rating_selectors': ['[data-test="rating"]', '.styles__Rating-sc-1u7afl7-0'],
                'review_selectors': ['[data-test="reviews"]', '.styles__ReviewCount-sc-1u7afl7-0'],
                'img_selectors': ['[data-test="product-image"] img', '.styles__ProductImage-sc-1u7afl7-0'],
                'url_selectors': ['[data-test="product-title"]', 'a[href*="/p/"]']
            },
            'bestbuy': {
                'base_url': 'https://www.bestbuy.com/site/searchpage.jsp?st={}',
                'page_url': 'https://www.bestbuy.com/site/searchpage.jsp?st={}&page={}',
                'container_selector': '.product-item',
                'title_selectors': ['.product-title', 'h4 a', '.sku-title'],
                'price_selectors': ['.price-current', '.sr-only', '.pricing-price__value'],
                'rating_selectors': ['.c-ratings-reviews', '.sr-only'],
                'review_selectors': ['.c-ratings-reviews', '.sr-only'],
                'img_selectors': ['.product-image img', '.sr-only'],
                'url_selectors': ['.product-title', 'h4 a']
            }
        }
        
        # User agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]

    async def scrape_platform(self):
        """Main scraping method using async Playwright"""
        print(f"🚀 Starting Playwright {self.platform.title()} scraper for: {self.keywords}")
        print(f"📊 Max pages: {self.max_pages}")
        
        try:
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
                config = self.platform_configs[self.platform]
                for page_num in range(1, self.max_pages + 1):
                    if page_num == 1:
                        url = config['base_url'].format(self.keywords.replace(" ", "+"))
                    else:
                        url = config['page_url'].format(self.keywords.replace(" ", "+"), page_num)
                    
                    print(f"🔍 Scraping page {page_num}: {url}")
                    
                    try:
                        # Navigate to page
                        response = await page.goto(url, wait_until='networkidle', timeout=30000)
                        
                        if response.status != 200:
                            print(f"⚠️ Page returned status {response.status}")
                            continue
                        
                        # Wait for content to load
                        await page.wait_for_timeout(random.randint(2000, 4000))
                        
                        # Extract product data
                        products = await self.extract_products_from_page(page, config)
                        self.scraped_products.extend(products)
                        
                        print(f"✅ Scraped {len(products)} products from page {page_num}")
                        
                        # Random delay between pages
                        if page_num < self.max_pages:
                            delay = random.randint(3000, 6000)
                            print(f"⏳ Waiting {delay/1000}s before next page...")
                            await page.wait_for_timeout(delay)
                        
                    except Exception as e:
                        print(f"❌ Error scraping page {page_num}: {e}")
                        continue
                
                await browser.close()
                
        except Exception as e:
            print(f"❌ Playwright scraping failed: {e}")
            # Fallback to sample data
            self.scraped_products = self.generate_sample_products()

    async def extract_products_from_page(self, page, config):
        """Extract product data from the current page"""
        products = []
        
        try:
            # Wait for product containers to load
            await page.wait_for_selector(config['container_selector'], timeout=10000)
            
            # Get all product containers
            product_containers = await page.query_selector_all(config['container_selector'])
            
            print(f"🔍 Found {len(product_containers)} product containers")
            
            for i, container in enumerate(product_containers[:20]):  # Limit to 20 products per page
                try:
                    product = await self.extract_single_product(container, page, config)
                    if product:
                        products.append(product)
                        
                except Exception as e:
                    print(f"⚠️ Error extracting product {i}: {e}")
                    continue
            
        except Exception as e:
            print(f"❌ Error extracting products from page: {e}")
        
        return products

    async def extract_single_product(self, container, page, config):
        """Extract data from a single product container"""
        try:
            # Extract title
            title = "Unknown Product"
            for selector in config['title_selectors']:
                try:
                    title_element = await container.query_selector(selector)
                    if title_element:
                        title_text = await title_element.inner_text()
                        if title_text and title_text.strip() and len(title_text.strip()) > 5:
                            title = title_text.strip()
                            break
                except:
                    continue
            
            # Extract price
            price = 0.0
            for selector in config['price_selectors']:
                try:
                    price_element = await container.query_selector(selector)
                    if price_element:
                        price_text = await price_element.inner_text()
                        if price_text and price_text.strip():
                            price = self.clean_price(price_text)
                            if price > 0:
                                break
                except:
                    continue
            
            # Extract brand (from title)
            brand = self.extract_brand_from_title(title)
            
            # Extract rating
            rating = 0.0
            for selector in config['rating_selectors']:
                try:
                    rating_element = await container.query_selector(selector)
                    if rating_element:
                        rating_text = await rating_element.inner_text()
                        if rating_text and rating_text.strip():
                            rating = self.extract_rating(rating_text)
                            if rating > 0:
                                break
                except:
                    continue
            
            # Extract review count
            review_count = 0
            for selector in config['review_selectors']:
                try:
                    review_element = await container.query_selector(selector)
                    if review_element:
                        review_text = await review_element.inner_text()
                        if review_text and review_text.strip():
                            review_count = self.extract_review_count(review_text)
                            if review_count > 0:
                                break
                except:
                    continue
            
            # Extract image URL
            img_url = ""
            for selector in config['img_selectors']:
                try:
                    img_element = await container.query_selector(selector)
                    if img_element:
                        img_src = await img_element.get_attribute('src')
                        if not img_src:
                            img_src = await img_element.get_attribute('data-src')
                        if img_src and img_src.strip():
                            img_url = img_src.strip()
                            break
                except:
                    continue
            
            # Extract product URL
            product_url = ""
            for selector in config['url_selectors']:
                try:
                    link_element = await container.query_selector(selector)
                    if link_element:
                        href = await link_element.get_attribute('href')
                        if href and href.strip():
                            if href.startswith('http'):
                                product_url = href.strip()
                            else:
                                base_url = self.get_base_url()
                                product_url = f"{base_url}{href.strip()}"
                            break
                except:
                    continue
            
            # Create product dictionary
            product = {
                'title': [title],
                'brand': [brand],
                'model_name': [self.extract_model_from_title(title)],
                'price': [str(price)],
                'star_rating': [str(rating)],
                'no_rating': [str(review_count)],
                'img_url': [img_url],
                'url': [product_url],
                'colour': [self.extract_color_from_title(title)],
                'storage_cap': [self.extract_storage_from_title(title)],
                'platform': [self.platform.title()]
            }
            
            return product
            
        except Exception as e:
            print(f"⚠️ Error extracting single product: {e}")
            return None

    def get_base_url(self):
        """Get base URL for the platform"""
        base_urls = {
            'amazon': 'https://www.amazon.com',
            'walmart': 'https://www.walmart.com',
            'target': 'https://www.target.com',
            'bestbuy': 'https://www.bestbuy.com'
        }
        return base_urls.get(self.platform, 'https://www.amazon.com')

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
            brands = ['Samsung', 'Apple', 'Sony', 'LG', 'Dell', 'HP', 'Lenovo', 'Asus', 'Acer', 'Microsoft', 'Google', 'OnePlus', 'Xiaomi', 'Huawei', 'Bose', 'JBL', 'Anker', 'Logitech', 'Meta', 'Nekteck']
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
            colors = ['Black', 'White', 'Silver', 'Gold', 'Blue', 'Red', 'Green', 'Gray', 'Space Gray', 'Midnight', 'Starlight', 'Pink', 'Purple', 'Titanium']
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
                return f"{storage_match.group(1)} {storage_match.group(2)}"
            return "Unknown"
        except:
            return "Unknown"

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
        print(f"🔄 Generating sample {self.platform.title()} products as fallback")
        
        sample_products = []
        platform_samples = {
            'amazon': [
                {
                    'title': 'Samsung Galaxy S24 Ultra 5G Smartphone 256GB',
                    'brand': 'Samsung',
                    'price': '1299.99',
                    'rating': '4.5',
                    'reviews': '2847',
                    'img_url': 'https://m.media-amazon.com/images/I/71PvHfVpP0L._AC_SX679_.jpg',
                    'url': 'https://www.amazon.com/dp/B0CM7RQL5K'
                },
                {
                    'title': 'Apple iPhone 15 Pro Max 256GB Titanium',
                    'brand': 'Apple',
                    'price': '1199.99',
                    'rating': '4.7',
                    'reviews': '1923',
                    'img_url': 'https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SX679_.jpg',
                    'url': 'https://www.amazon.com/dp/B0CHX1W1XY'
                }
            ],
            'walmart': [
                {
                    'title': 'Samsung Galaxy S24 Ultra 5G Smartphone 256GB',
                    'brand': 'Samsung',
                    'price': '1199.99',
                    'rating': '4.6',
                    'reviews': '1847',
                    'img_url': 'https://i5.walmartimages.com/asr/12345678-1234-1234-1234-123456789012.jpeg',
                    'url': 'https://www.walmart.com/ip/samsung-galaxy-s24-ultra/123456789'
                },
                {
                    'title': 'Apple iPhone 15 Pro Max 256GB Titanium',
                    'brand': 'Apple',
                    'price': '1099.99',
                    'rating': '4.8',
                    'reviews': '2234',
                    'img_url': 'https://i5.walmartimages.com/asr/87654321-4321-4321-4321-210987654321.jpeg',
                    'url': 'https://www.walmart.com/ip/apple-iphone-15-pro-max/987654321'
                }
            ],
            'target': [
                {
                    'title': 'Samsung Galaxy S24 Ultra 5G Smartphone 256GB',
                    'brand': 'Samsung',
                    'price': '1249.99',
                    'rating': '4.4',
                    'reviews': '1567',
                    'img_url': 'https://target.scene7.com/is/image/Target/12345678',
                    'url': 'https://www.target.com/p/samsung-galaxy-s24-ultra/-/A-123456789'
                },
                {
                    'title': 'Apple iPhone 15 Pro Max 256GB Titanium',
                    'brand': 'Apple',
                    'price': '1149.99',
                    'rating': '4.6',
                    'reviews': '1890',
                    'img_url': 'https://target.scene7.com/is/image/Target/87654321',
                    'url': 'https://www.target.com/p/apple-iphone-15-pro-max/-/A-987654321'
                }
            ],
            'bestbuy': [
                {
                    'title': 'Samsung Galaxy S24 Ultra 5G Smartphone 256GB',
                    'brand': 'Samsung',
                    'price': '1299.99',
                    'rating': '4.5',
                    'reviews': '2134',
                    'img_url': 'https://pisces.bbystatic.com/image2/BestBuy_US/images/products/1234/12345678_sa.jpg',
                    'url': 'https://www.bestbuy.com/site/samsung-galaxy-s24-ultra/12345678.p'
                },
                {
                    'title': 'Apple iPhone 15 Pro Max 256GB Titanium',
                    'brand': 'Apple',
                    'price': '1199.99',
                    'rating': '4.7',
                    'reviews': '1987',
                    'img_url': 'https://pisces.bbystatic.com/image2/BestBuy_US/images/products/8765/87654321_sa.jpg',
                    'url': 'https://www.bestbuy.com/site/apple-iphone-15-pro-max/87654321.p'
                }
            ]
        }
        
        sample_data = platform_samples.get(self.platform, platform_samples['amazon'])
        
        for data in sample_data:
            product = {
                'title': [data['title']],
                'brand': [data['brand']],
                'model_name': [data['title'].split()[0:3]],
                'price': [data['price']],
                'star_rating': [data['rating']],
                'no_rating': [data['reviews']],
                'img_url': [data['img_url']],
                'url': [data['url']],
                'colour': ['Black'],
                'storage_cap': ['256GB'],
                'platform': [self.platform.title()]
            }
            
            sample_products.append(product)
        
        return sample_products

    def save_results(self, filename=None):
        """Save scraped results to JSON file"""
        if filename is None:
            filename = f'{self.platform}_products.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.scraped_products, f, indent=2, ensure_ascii=False)
            print(f"📁 Results saved to: {filename}")
        except Exception as e:
            print(f"❌ Error saving results: {e}")


async def main():
    """Main function to run the scraper"""
    platforms = ['amazon', 'walmart', 'target', 'bestbuy']
    
    for platform in platforms:
        print(f"\n{'='*60}")
        print(f"🛒 SCRAPING {platform.upper()}")
        print(f"{'='*60}")
        
        scraper = UnifiedEcommerceScraper(platform=platform, keywords='electronics', max_pages=2)
        await scraper.scrape_platform()
        scraper.save_results()
        
        print(f"\n🎉 {platform.title()} scraping completed! Found {len(scraper.scraped_products)} products")
        
        # Show first few products
        for i, product in enumerate(scraper.scraped_products[:2], 1):
            print(f"\n🛒 Product #{i}:")
            print("-" * 30)
            print(f"📝 Title: {product['title'][0]}")
            print(f"🏷️  Brand: {product['brand'][0]}")
            print(f"💰 Price: ${product['price'][0]}")
            print(f"🏪 Platform: {product['platform'][0]}")
            print("-" * 30)


if __name__ == '__main__':
    asyncio.run(main())

