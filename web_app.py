"""
Flask Web Application for Unified E-commerce Product Data Aggregator
"""
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import threading
import time
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecommerce-aggregator-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables for tracking
scraping_status = {
    'is_running': False,
    'current_spider': None,
    'products_scraped': 0,
    'errors': 0,
    'start_time': None,
    'last_update': None
}

scraped_products = []
scraping_logs = []

class WebScrapingManager:
    """Manages scraping operations for the web interface"""
    
    def __init__(self):
        self.is_running = False
        self.current_spider = None
        self.products_scraped = 0
        self.errors = 0
        self.start_time = None
    
    def start_scraping(self, spider_name: str, category: str = 'electronics', max_pages: int = 5):
        """Start scraping operation"""
        try:
            self.is_running = True
            self.current_spider = spider_name
            self.products_scraped = 0
            self.errors = 0
            self.start_time = datetime.now()
            
            # Update global status
            scraping_status.update({
                'is_running': True,
                'current_spider': spider_name,
                'products_scraped': 0,
                'errors': 0,
                'start_time': self.start_time,
                'last_update': datetime.now()
            })
            
            # Emit status update
            socketio.emit('scraping_status', scraping_status)
            
            # Start scraping in background thread
            thread = threading.Thread(target=self._run_scraping, args=(spider_name, category, max_pages))
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting scraping: {e}")
            self.is_running = False
            return False
    
    def _run_scraping(self, spider_name: str, category: str, max_pages: int):
        """Run scraping operation in background"""
        try:
            # Import and run spider
            if spider_name == 'amazon':
                from amazonscraper.spiders.enhanced_amazon_spider import AmazonSpider
                spider = AmazonSpider(domain='amazon.com', category=category, max_pages=max_pages)
                
                # Simulate scraping (since we don't have database set up)
                self._simulate_scraping(spider_name, category, max_pages)
            else:
                self._simulate_scraping(spider_name, category, max_pages)
                
        except Exception as e:
            logger.error(f"Error in scraping thread: {e}")
            self.errors += 1
        finally:
            self.is_running = False
            scraping_status['is_running'] = False
            scraping_status['last_update'] = datetime.now()
            socketio.emit('scraping_complete', scraping_status)
    
    def _simulate_scraping(self, spider_name: str, category: str, max_pages: int):
        """Simulate scraping for demo purposes"""
        sample_products = [
            {
                'external_id': 'B08N5WRWNW',
                'platform': 'amazon',
                'title': 'Echo Dot (4th Gen) | Smart speaker with Alexa | Charcoal',
                'brand': 'Amazon',
                'model': 'Echo Dot 4th Gen',
                'current_price': 49.99,
                'original_price': 59.99,
                'currency': 'USD',
                'discount_percentage': 16.67,
                'availability_status': 'in_stock',
                'rating': 4.5,
                'review_count': 125000,
                'category': 'Electronics',
                'subcategory': 'Smart Speakers',
                'product_url': 'https://amazon.com/dp/B08N5WRWNW',
                'scraped_at': datetime.now().isoformat(),
                'is_curated': True
            },
            {
                'external_id': 'B08N5WRWNW',
                'platform': 'amazon',
                'title': 'Apple AirPods Pro (2nd Generation)',
                'brand': 'Apple',
                'model': 'AirPods Pro 2nd Gen',
                'current_price': 249.00,
                'original_price': 279.00,
                'currency': 'USD',
                'discount_percentage': 10.75,
                'availability_status': 'in_stock',
                'rating': 4.7,
                'review_count': 89000,
                'category': 'Electronics',
                'subcategory': 'Audio',
                'product_url': 'https://amazon.com/dp/B08N5WRWNW',
                'scraped_at': datetime.now().isoformat(),
                'is_curated': True
            },
            {
                'external_id': 'B08N5WRWNW',
                'platform': 'amazon',
                'title': 'Samsung 55" Class QLED 4K UHD Smart TV',
                'brand': 'Samsung',
                'model': 'QN55Q80CAFXZA',
                'current_price': 699.99,
                'original_price': 899.99,
                'currency': 'USD',
                'discount_percentage': 22.22,
                'availability_status': 'in_stock',
                'rating': 4.3,
                'review_count': 45000,
                'category': 'Electronics',
                'subcategory': 'TVs',
                'product_url': 'https://amazon.com/dp/B08N5WRWNW',
                'scraped_at': datetime.now().isoformat(),
                'is_curated': True
            }
        ]
        
        # Simulate scraping progress
        for i, product in enumerate(sample_products):
            if not self.is_running:
                break
                
            time.sleep(2)  # Simulate processing time
            
            self.products_scraped += 1
            scraped_products.append(product)
            
            # Update status
            scraping_status.update({
                'products_scraped': self.products_scraped,
                'last_update': datetime.now()
            })
            
            # Emit progress update
            socketio.emit('scraping_progress', {
                'product': product,
                'status': scraping_status
            })
            
            # Add to logs
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': f"Scraped product: {product['title']}",
                'spider': spider_name
            }
            scraping_logs.append(log_entry)
            
            # Emit log update
            socketio.emit('scraping_log', log_entry)
    
    def stop_scraping(self):
        """Stop current scraping operation"""
        self.is_running = False
        scraping_status['is_running'] = False
        scraping_status['last_update'] = datetime.now()
        socketio.emit('scraping_stopped', scraping_status)
    
    def get_status(self):
        """Get current scraping status"""
        return scraping_status

# Initialize scraping manager
scraping_manager = WebScrapingManager()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    """Get scraping status"""
    return jsonify(scraping_manager.get_status())

@app.route('/api/products')
def get_products():
    """Get scraped products"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    products_page = scraped_products[start_idx:end_idx]
    
    return jsonify({
        'products': products_page,
        'total': len(scraped_products),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(scraped_products) + per_page - 1) // per_page
    })

@app.route('/api/products/<product_id>')
def get_product(product_id):
    """Get specific product details"""
    product = next((p for p in scraped_products if p['external_id'] == product_id), None)
    if product:
        return jsonify(product)
    return jsonify({'error': 'Product not found'}), 404

@app.route('/api/logs')
def get_logs():
    """Get scraping logs"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    logs_page = scraping_logs[start_idx:end_idx]
    
    return jsonify({
        'logs': logs_page,
        'total': len(scraping_logs),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(scraping_logs) + per_page - 1) // per_page
    })

@app.route('/api/start-scraping', methods=['POST'])
def start_scraping():
    """Start scraping operation"""
    data = request.get_json()
    spider_name = data.get('spider', 'amazon')
    category = data.get('category', 'electronics')
    max_pages = data.get('max_pages', 5)
    
    if scraping_manager.is_running:
        return jsonify({'error': 'Scraping is already running'}), 400
    
    success = scraping_manager.start_scraping(spider_name, category, max_pages)
    
    if success:
        return jsonify({'message': 'Scraping started successfully'})
    else:
        return jsonify({'error': 'Failed to start scraping'}), 500

@app.route('/api/stop-scraping', methods=['POST'])
def stop_scraping():
    """Stop scraping operation"""
    scraping_manager.stop_scraping()
    return jsonify({'message': 'Scraping stopped'})

@app.route('/api/clear-data', methods=['POST'])
def clear_data():
    """Clear scraped data"""
    global scraped_products, scraping_logs
    scraped_products.clear()
    scraping_logs.clear()
    return jsonify({'message': 'Data cleared'})

@app.route('/api/stats')
def get_stats():
    """Get system statistics"""
    total_products = len(scraped_products)
    curated_products = len([p for p in scraped_products if p.get('is_curated', False)])
    
    # Calculate average rating
    ratings = [p.get('rating', 0) for p in scraped_products if p.get('rating')]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    # Calculate average price
    prices = [p.get('current_price', 0) for p in scraped_products if p.get('current_price')]
    avg_price = sum(prices) / len(prices) if prices else 0
    
    # Platform distribution
    platforms = {}
    for product in scraped_products:
        platform = product.get('platform', 'unknown')
        platforms[platform] = platforms.get(platform, 0) + 1
    
    # Category distribution
    categories = {}
    for product in scraped_products:
        category = product.get('category', 'unknown')
        categories[category] = categories.get(category, 0) + 1
    
    return jsonify({
        'total_products': total_products,
        'curated_products': curated_products,
        'average_rating': round(avg_rating, 2),
        'average_price': round(avg_price, 2),
        'platforms': platforms,
        'categories': categories,
        'scraping_status': scraping_manager.get_status()
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Client connected')
    emit('connected', {'message': 'Connected to scraping server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected')

@socketio.on('get_status')
def handle_get_status():
    """Handle status request"""
    emit('status_update', scraping_manager.get_status())

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    logger.info("🚀 Starting Unified E-commerce Product Data Aggregator Web Interface")
    logger.info("📊 Dashboard available at: http://localhost:5000")
    
    # Run the Flask app with SocketIO
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)


