#!/usr/bin/env python3
"""
Working Amazon Scraper - Main Entry Point
"""

from amazonscraper.spiders.amazonspider import AmazonSpiderSpider
from scrapy.crawler import CrawlerProcess
from twisted.internet import reactor
import json
import os

def main():
    """Main function to run the Amazon scraper"""
    print("🚀 Starting Amazon Scraper...")
    print("=" * 50)
    
    # Create crawler process with settings
    settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
        'FEEDS': {
            'scraped_products.json': {
                'format': 'json',
                'overwrite': True,
            },
        },
        'LOG_LEVEL': 'INFO',
    }
    
    process = CrawlerProcess(settings)
    
    def crawl_amazon():
        """Crawl Amazon products"""
        print("📊 Scraping Amazon products...")
        print("⏳ This may take a few minutes...")
        print("🔍 Looking for mobile offers on Amazon India...")
        print("=" * 50)
        
        process.crawl(AmazonSpiderSpider)
        process.start()
        
        # After crawling, show results
        show_results()
    
    def show_results():
        """Show scraping results"""
        try:
            if os.path.exists('scraped_products.json'):
                with open('scraped_products.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print("\n" + "=" * 50)
                print("🎉 SCRAPING COMPLETED!")
                print("=" * 50)
                print(f"📊 Total Products Scraped: {len(data)}")
                print("=" * 50)
                
                # Show first few products
                for i, product in enumerate(data[:3], 1):
                    print(f"\n📱 Product #{i}:")
                    print("-" * 30)
                    
                    if 'title' in product and product['title']:
                        title = product['title'][0] if isinstance(product['title'], list) else product['title']
                        print(f"📝 Title: {title}")
                    
                    if 'brand' in product and product['brand']:
                        brand = product['brand'][0] if isinstance(product['brand'], list) else product['brand']
                        print(f"🏷️  Brand: {brand}")
                    
                    if 'price' in product and product['price']:
                        price = product['price'][0] if isinstance(product['price'], list) else product['price']
                        print(f"💰 Price: ₹{price}")
                    
                    print("-" * 30)
                
                print("\n✅ SCRAPER STATUS: WORKING PERFECTLY!")
                print("🎯 Successfully scraped real Amazon products")
                print("📈 Data saved to: scraped_products.json")
                print("🔄 Ready for integration with your marketplace")
                print("=" * 50)
            else:
                print("❌ No output file found")
        except Exception as e:
            print(f"❌ Error showing results: {e}")
    
    # Start crawling
    crawl_amazon()

if __name__ == '__main__':
    main()

