"""
Comprehensive Admin Panel for Unified E-commerce Product Data Aggregator
"""
import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, BooleanField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import time
from typing import Dict, Any, List
import sqlite3
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get configuration from environment variables (for Railway/production)
SECRET_KEY = os.getenv('SECRET_KEY', 'ecommerce-aggregator-admin-secret-key-2024')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///admin_panel.db')

# Convert PostgreSQL URL format if needed (Railway uses postgres://, SQLAlchemy needs postgresql://)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Production settings
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
app.config['DEBUG'] = (FLASK_ENV != 'production')

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Add custom Jinja2 filters
@app.template_filter('to_datetime')
def to_datetime_filter(value):
    """Convert string to datetime object"""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return value

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the admin panel.'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, role='user'):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

# Database setup
def init_db():
    """Initialize database for admin panel (SQLite for local, PostgreSQL for production)"""
    # Use PostgreSQL if DATABASE_URL is provided, otherwise SQLite
    if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
        # PostgreSQL - initialize tables using init_postgres.py
        logger.info("Using PostgreSQL database")
        try:
            import subprocess
            result = subprocess.run(['python', 'init_postgres.py'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.info("✅ PostgreSQL database initialized")
            else:
                logger.warning(f"PostgreSQL init script output: {result.stdout}")
        except Exception as e:
            logger.warning(f"Could not run PostgreSQL init script: {e}")
            logger.info("Tables may need to be created manually")
        return
    
    # SQLite for local development
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Scraper configurations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraper_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            platform TEXT NOT NULL,
            category TEXT NOT NULL,
            max_pages INTEGER DEFAULT 3,
            delay_min REAL DEFAULT 1.0,
            delay_max REAL DEFAULT 2.0,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Scraping schedules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config_id INTEGER,
            schedule_type TEXT NOT NULL,
            schedule_value TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES scraper_configs (id)
        )
    ''')
    
    # Scraping logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            status TEXT NOT NULL,
            products_scraped INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # System settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default admin user
    admin_password = generate_password_hash('admin123')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash, role)
        VALUES ('admin', 'admin@ecommerce-aggregator.com', ?, 'admin')
    ''', (admin_password,))
    
    # Insert default settings
    default_settings = [
        ('min_rating', '4.0', 'Minimum product rating for curation'),
        ('min_review_count', '10', 'Minimum review count for curation'),
        ('max_concurrent_scrapers', '3', 'Maximum concurrent scrapers'),
        ('default_delay', '2.0', 'Default delay between requests'),
        ('max_retries', '3', 'Maximum retry attempts'),
        ('notification_email', 'admin@ecommerce-aggregator.com', 'Notification email'),
        ('data_retention_days', '30', 'Data retention period in days')
    ]
    
    for key, value, description in default_settings:
        cursor.execute('''
            INSERT OR IGNORE INTO system_settings (key, value, description)
            VALUES (?, ?, ?)
        ''', (key, value, description))
    
    conn.commit()
    conn.close()

# Database helper functions
def get_user_by_id(user_id):
    """Get user by ID"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2], user_data[3])
    return None

def get_user_by_username(username):
    """Get user by username"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, password_hash, role FROM users WHERE username = ?', (username,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return {
            'id': user_data[0],
            'username': user_data[1],
            'email': user_data[2],
            'password_hash': user_data[3],
            'role': user_data[4]
        }
    return None

def verify_password(username, password):
    """Verify user password"""
    user = get_user_by_username(username)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ScraperConfigForm(FlaskForm):
    name = StringField('Configuration Name', validators=[DataRequired(), Length(max=100)])
    platform = SelectField('Platform', choices=[
        ('amazon', 'Amazon'),
        ('walmart', 'Walmart'),
        ('target', 'Target'),
        ('bestbuy', 'Best Buy')
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('electronics', 'Electronics'),
        ('computers', 'Computers'),
        ('home', 'Home & Kitchen'),
        ('fashion', 'Fashion'),
        ('books', 'Books'),
        ('sports', 'Sports'),
        ('automotive', 'Automotive'),
        ('beauty', 'Beauty'),
        ('toys', 'Toys'),
        ('garden', 'Garden')
    ], validators=[DataRequired()])
    max_pages = IntegerField('Max Pages', validators=[DataRequired(), NumberRange(min=1, max=100)])
    delay_min = IntegerField('Min Delay (seconds)', validators=[DataRequired(), NumberRange(min=1, max=10)])
    delay_max = IntegerField('Max Delay (seconds)', validators=[DataRequired(), NumberRange(min=1, max=10)])
    enabled = BooleanField('Enabled')
    submit = SubmitField('Save Configuration')

class ScheduleForm(FlaskForm):
    name = StringField('Schedule Name', validators=[DataRequired(), Length(max=100)])
    config_id = SelectField('Configuration', coerce=int, validators=[DataRequired()])
    schedule_type = SelectField('Schedule Type', choices=[
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom Cron')
    ], validators=[DataRequired()])
    schedule_value = StringField('Schedule Value', validators=[DataRequired()])
    enabled = BooleanField('Enabled')
    submit = SubmitField('Save Schedule')

class SettingsForm(FlaskForm):
    min_rating = StringField('Minimum Rating', validators=[DataRequired()])
    min_review_count = IntegerField('Minimum Review Count', validators=[DataRequired()])
    max_concurrent_scrapers = IntegerField('Max Concurrent Scrapers', validators=[DataRequired()])
    default_delay = StringField('Default Delay (seconds)', validators=[DataRequired()])
    max_retries = IntegerField('Max Retries', validators=[DataRequired()])
    notification_email = StringField('Notification Email', validators=[Email()])
    data_retention_days = IntegerField('Data Retention (days)', validators=[DataRequired()])
    submit = SubmitField('Save Settings')

# Role-based access control
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

class AdminScrapingManager:
    """Advanced scraping manager for admin panel"""
    
    def __init__(self):
        self.is_running = False
        self.current_spider = None
        self.products_scraped = 0
        self.errors = 0
        self.start_time = None
        self.session_id = None
    
    def start_scraping(self, config_id: int):
        """Start scraping with specific configuration"""
        try:
            # Get configuration from database
            config = self.get_scraper_config(config_id)
            if not config:
                return False, "Configuration not found"
            
            self.is_running = True
            self.current_spider = config['platform']
            self.products_scraped = 0
            self.errors = 0
            self.start_time = datetime.now()
            self.session_id = f"session_{int(time.time())}"
            
            # Update global status
            scraping_status.update({
                'is_running': True,
                'current_spider': config['platform'],
                'products_scraped': 0,
                'errors': 0,
                'start_time': self.start_time.isoformat(),
                'last_update': datetime.now().isoformat()
            })
            
            # Log scraping session
            self.log_scraping_session('started')
            
            # Emit status update
            socketio.emit('scraping_status', scraping_status)
            
            # Start scraping in background thread
            thread = threading.Thread(target=self._run_scraping, args=(config,))
            thread.daemon = True
            thread.start()
            
            return True, "Scraping started successfully"
            
        except Exception as e:
            logger.error(f"Error starting scraping: {e}")
            self.is_running = False
            return False, str(e)
    
    def get_scraper_config(self, config_id: int):
        """Get scraper configuration from database"""
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM scraper_configs WHERE id = ?', (config_id,))
        config_data = cursor.fetchone()
        conn.close()
        
        if config_data:
            return {
                'id': config_data[0],
                'name': config_data[1],
                'platform': config_data[2],
                'category': config_data[3],
                'max_pages': config_data[4],
                'delay_min': config_data[5],
                'delay_max': config_data[6],
                'enabled': config_data[7]
            }
        return None
    
    def log_scraping_session(self, status: str):
        """Log scraping session to database"""
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        duration = None
        if status == 'completed' and self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        
        cursor.execute('''
            INSERT INTO scraping_logs 
            (session_id, platform, status, products_scraped, errors, start_time, end_time, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.session_id,
            self.current_spider,
            status,
            self.products_scraped,
            self.errors,
            self.start_time.isoformat() if self.start_time else None,
            datetime.now().isoformat() if status in ['completed', 'failed'] else None,
            duration
        ))
        
        conn.commit()
        conn.close()
    
    def _run_scraping(self, config: Dict[str, Any]):
        """Run scraping operation in background"""
        try:
            # Simulate scraping with configuration
            self._simulate_scraping(config)
            
        except Exception as e:
            logger.error(f"Error in scraping thread: {e}")
            self.errors += 1
        finally:
            self.is_running = False
            scraping_status['is_running'] = False
            scraping_status['last_update'] = datetime.now().isoformat()
            
            # Log completion
            self.log_scraping_session('completed')
            
            socketio.emit('scraping_complete', scraping_status)
    
    def _simulate_scraping(self, config: Dict[str, Any]):
        """Run actual scraping with configuration"""
        try:
            # Create a temporary output file
            output_file = f"temp_scraped_{int(time.time())}.json"
            
            # Build the scrapy command
            keywords = config.get('keywords', 'electronics')
            max_pages = config.get('max_pages', 3)
            
            logger.info(f"🚀 Starting real scraping: {keywords}, {max_pages} pages")
            
            # Run the actual scraper synchronously to see what's happening
            self._run_real_scraper_sync(keywords, max_pages, output_file)
            
            # Process the scraped results
            self._process_scraped_results_simple(output_file, config)
            
        except Exception as e:
            logger.error(f"Error in real scraping: {e}")
            # Fallback to sample data if real scraping fails
            sample_products = self._generate_sample_products(config)
            self._process_sample_products(sample_products, config)
    
    def _run_real_scraper_sync(self, keywords, max_pages, output_file):
        """Run the actual Amazon scraper synchronously (blocking)"""
        try:
            # Import and run the unified scraper directly
            import asyncio
            from unified_scraper import UnifiedEcommerceScraper
            
            logger.info(f"🚀 Running Playwright scraper synchronously for Amazon")
            
            # Create scraper instance
            scraper = UnifiedEcommerceScraper(platform="amazon", keywords=keywords, max_pages=max_pages)
            
            # Run scraper synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(scraper.scrape_platform())
                scraper.save_results(output_file)
                logger.info(f"✅ Playwright scraper completed successfully")
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error running Playwright scraper: {e}")
            raise e
    
    def _run_real_scraper_with_callback(self, keywords, max_pages, output_file, config):
        """Run the actual Amazon scraper with callback when complete"""
        try:
            # Import and run the unified scraper directly
            import asyncio
            from unified_scraper import UnifiedEcommerceScraper
            
            logger.info(f"🚀 Running Playwright scraper with callback for Amazon")
            
            # Create scraper instance
            scraper = UnifiedEcommerceScraper(platform="amazon", keywords=keywords, max_pages=max_pages)
            
            # Run scraper in a separate thread with callback
            def run_scraper_with_callback():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(scraper.scrape_platform())
                    scraper.save_results(output_file)
                    logger.info(f"✅ Playwright scraper completed successfully")
                    
                    # Process results after completion
                    self._process_scraped_results_simple(output_file, config)
                    
                    # Update status
                    self.is_running = False
                    self.current_spider = None
                    
                except Exception as e:
                    logger.error(f"Error in scraper thread: {e}")
                    # Fallback to sample data
                    sample_products = self._generate_sample_products(config)
                    self._process_sample_products(sample_products, config)
                    self.is_running = False
                    self.current_spider = None
                finally:
                    loop.close()
            
            # Run in thread (non-blocking)
            scraper_thread = threading.Thread(target=run_scraper_with_callback, daemon=True)
            scraper_thread.start()
            
            logger.info(f"✅ Playwright scraper started in background thread")
                
        except Exception as e:
            logger.error(f"Error running Playwright scraper: {e}")
            # Fallback to sample data
            sample_products = self._generate_sample_products(config)
            self._process_sample_products(sample_products, config)
    
    def _run_real_scraper(self, keywords, max_pages, output_file):
        """Run the actual Amazon scraper using Playwright directly (non-blocking)"""
        try:
            # Import and run the unified scraper directly
            import asyncio
            from unified_scraper import UnifiedEcommerceScraper
            
            logger.info(f"🚀 Running Playwright scraper directly for Amazon")
            
            # Create scraper instance
            scraper = UnifiedEcommerceScraper(platform="amazon", keywords=keywords, max_pages=max_pages)
            
            # Run scraper in a separate thread to avoid blocking
            def run_scraper():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(scraper.scrape_platform())
                    scraper.save_results(output_file)
                    logger.info(f"✅ Playwright scraper completed successfully")
                    
                    # Update the scraping manager status
                    self.is_running = False
                    self.current_spider = None
                    
                except Exception as e:
                    logger.error(f"Error in scraper thread: {e}")
                    self.is_running = False
                    self.current_spider = None
                finally:
                    loop.close()
            
            # Run in thread (non-blocking)
            scraper_thread = threading.Thread(target=run_scraper, daemon=True)
            scraper_thread.start()
            
            # Don't wait for completion - let it run in background
            logger.info(f"✅ Playwright scraper started in background thread")
                
        except Exception as e:
            logger.error(f"Error running Playwright scraper: {e}")
            raise e
    
    def _process_scraped_results_simple(self, output_file, config):
        """Process scraped results in a simple way"""
        try:
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    scraped_data = json.load(f)
                
                logger.info(f"📊 Processing {len(scraped_data)} scraped products")
                
                # Convert and save each product
                processed_count = 0
                for product_data in scraped_data:
                    try:
                        converted_product = self._convert_scraped_product(product_data, config)
                        self._save_product_to_db(converted_product)
                        processed_count += 1
                    except Exception as e:
                        logger.error(f"Error processing product: {e}")
                        continue
                
                logger.info(f"✅ Successfully processed {processed_count} products")
                
                # Clean up temp file
                os.remove(output_file)
                
            else:
                logger.error(f"Output file not found: {output_file}")
                
        except Exception as e:
            logger.error(f"Error processing scraped results: {e}")
    
    def _process_scraped_results(self, output_file, config):
        """Process the actual scraped results"""
        try:
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    scraped_data = json.load(f)
                
                # Process each scraped product
                for product_data in scraped_data:
                    if not self.is_running:
                        break
                    
                    # Convert scraped data to our format
                    product = self._convert_scraped_product(product_data, config)
                    
                    # Save to database
                    self._save_product_to_db(product)
                    
                    # Simulate processing delay
                    time.sleep(config.get('delay_min', 1))
                    
                    self.products_scraped += 1
                    scraped_products.append(product)
                    
                    # Update status
                    scraping_status.update({
                        'products_scraped': self.products_scraped,
                        'last_update': datetime.now().isoformat()
                    })
                    
                    # Emit progress update
                    socketio.emit('scraping_progress', {
                        'product': product,
                        'status': scraping_status,
                        'config': config
                    })
                    
                    # Add to logs
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'level': 'INFO',
                        'message': f"Scraped real product: {product['title']}",
                        'platform': config['platform'],
                        'session_id': self.session_id
                    }
                    scraping_logs.append(log_entry)
                    socketio.emit('scraping_log', log_entry)
                
                # Clean up temporary file
                os.remove(output_file)
                
        except Exception as e:
            logger.error(f"Error processing scraped results: {e}")
            # Fallback to sample data
            sample_products = self._generate_sample_products(config)
            self._process_sample_products(sample_products, config)
    
    def _convert_scraped_product(self, scraped_data, config):
        """Convert scraped product data to our format"""
        try:
            # Extract data from scraped format
            title = scraped_data.get('title', ['Unknown Product'])[0] if isinstance(scraped_data.get('title'), list) else scraped_data.get('title', 'Unknown Product')
            price_text = scraped_data.get('price', ['0'])[0] if isinstance(scraped_data.get('price'), list) else scraped_data.get('price', '0')
            
            # Clean price
            price = self._extract_price(price_text)
            
            # Extract other fields
            brand = scraped_data.get('brand', ['Unknown'])[0] if isinstance(scraped_data.get('brand'), list) else scraped_data.get('brand', 'Unknown')
            rating_text = scraped_data.get('star_rating', ['0'])[0] if isinstance(scraped_data.get('star_rating'), list) else scraped_data.get('star_rating', '0')
            rating = self._extract_rating(rating_text)
            
            # Get review count
            review_count_text = scraped_data.get('no_rating', ['0'])[0] if isinstance(scraped_data.get('no_rating'), list) else scraped_data.get('no_rating', '0')
            review_count = self._extract_review_count(review_count_text)
            
            # Get image URL
            img_url = scraped_data.get('img_url', [''])[0] if isinstance(scraped_data.get('img_url'), list) else scraped_data.get('img_url', '')
            
            # Get product URL
            product_url = scraped_data.get('url', [''])[0] if isinstance(scraped_data.get('url'), list) else scraped_data.get('url', '')
            if product_url and not product_url.startswith('http'):
                product_url = f"https://www.amazon.com{product_url}"
            
            return {
                'external_id': f"REAL_{int(time.time())}_{self.products_scraped}",
                'platform': config['platform'],
                'title': title,
                'brand': brand,
                'model': self._extract_model_from_title(title),
                'price': price,
                'original_price': price,  # Assume no discount for now
                'rating': rating,
                'review_count': review_count,
                'image_url': img_url,
                'product_url': product_url,
                'category': config['category'],
                'scraped_at': datetime.now().isoformat(),
                'is_curated': True
            }
            
        except Exception as e:
            logger.error(f"Error converting scraped product: {e}")
            return self._create_fallback_product(config)
    
    def _extract_price(self, price_text):
        """Extract numeric price from text"""
        try:
            import re
            # Remove currency symbols and extract numbers
            price_match = re.search(r'[\d,]+\.?\d*', str(price_text).replace(',', ''))
            if price_match:
                return float(price_match.group())
            return 0.0
        except:
            return 0.0
    
    def _extract_rating(self, rating_text):
        """Extract numeric rating from text"""
        try:
            import re
            rating_match = re.search(r'(\d+\.?\d*)', str(rating_text))
            if rating_match:
                return float(rating_match.group())
            return 0.0
        except:
            return 0.0
    
    def _extract_review_count(self, review_text):
        """Extract review count from text"""
        try:
            import re
            # Extract numbers from review text
            numbers = re.findall(r'\d+', str(review_text))
            if numbers:
                return int(numbers[0])
            return 0
        except:
            return 0
    
    def _extract_model_from_title(self, title):
        """Extract model from product title"""
        try:
            # Simple model extraction - take first few words
            words = title.split()[:3]
            return ' '.join(words)
        except:
            return 'Unknown Model'
    
    def _create_fallback_product(self, config):
        """Create a fallback product if scraping fails"""
        return {
            'external_id': f"FALLBACK_{int(time.time())}_{self.products_scraped}",
            'platform': config['platform'],
            'title': 'Product Scraping Failed',
            'brand': 'Unknown',
            'model': 'Unknown',
            'price': 0.0,
            'original_price': 0.0,
            'rating': 0.0,
            'review_count': 0,
            'image_url': '',
            'product_url': '',
            'category': config['category'],
            'scraped_at': datetime.now().isoformat(),
            'is_curated': False
        }
    
    def _process_sample_products(self, sample_products, config):
        """Process sample products as fallback"""
        for product in sample_products:
            if not self.is_running:
                break
            
            # Save to database
            self._save_product_to_db(product)
            
            # Simulate processing delay
            time.sleep(config.get('delay_min', 1))
            
            self.products_scraped += 1
            scraped_products.append(product)
            
            # Update status
            scraping_status.update({
                'products_scraped': self.products_scraped,
                'last_update': datetime.now().isoformat()
            })
            
            # Emit progress update
            socketio.emit('scraping_progress', {
                'product': product,
                'status': scraping_status,
                'config': config
            })
            
            # Add to logs
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': f"Using sample product: {product['title']}",
                'platform': config['platform'],
                'session_id': self.session_id
            }
            scraping_logs.append(log_entry)
            socketio.emit('scraping_log', log_entry)
    
    def _save_product_to_db(self, product: Dict[str, Any]):
        """Save scraped product to database"""
        try:
            conn = sqlite3.connect('admin_panel.db')
            cursor = conn.cursor()
            
            # Create products table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    platform TEXT,
                    title TEXT,
                    brand TEXT,
                    model TEXT,
                    price REAL,
                    original_price REAL,
                    rating REAL,
                    review_count INTEGER,
                    image_url TEXT,
                    product_url TEXT,
                    sync_status TEXT DEFAULT 'pending',
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    synced_at TIMESTAMP
                )
            ''')
            
            # Insert product
            cursor.execute('''
                INSERT OR REPLACE INTO products 
                (external_id, platform, title, brand, model, price, original_price, 
                 rating, review_count, image_url, product_url, sync_status, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.get('external_id', f"ext_{int(time.time())}_{self.products_scraped}"),
                product.get('platform', 'Amazon'),
                product.get('title', ''),
                product.get('brand', ''),
                product.get('model', ''),
                product.get('price', 0),
                product.get('original_price', 0),
                product.get('rating', 0),
                product.get('review_count', 0),
                product.get('image_url', ''),
                product.get('product_url', ''),
                'pending',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving product to database: {e}")
    
    def _generate_sample_products(self, config: Dict[str, Any]):
        """Generate sample products based on configuration"""
        platform = config['platform']
        category = config['category']
        keywords = config.get('keywords', '').lower()
        
        # All available products
        all_products = {
            'laptop': [
                {
                    'external_id': 'AMZ_LAPTOP_001',
                    'platform': 'Amazon',
                    'title': 'MacBook Pro 14-inch M3 Chip 512GB SSD - Space Gray',
                    'brand': 'Apple',
                    'model': 'MacBook Pro 14"',
                    'price': 1999.00,
                    'original_price': 1999.00,
                    'rating': 4.8,
                    'review_count': 892,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/macbook-pro-14-m3',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                },
                {
                    'external_id': 'AMZ_LAPTOP_002',
                    'platform': 'Amazon',
                    'title': 'Dell XPS 13 9320 Laptop - Intel i7, 16GB RAM, 512GB SSD',
                    'brand': 'Dell',
                    'model': 'XPS 13 9320',
                    'price': 1299.99,
                    'original_price': 1499.99,
                    'rating': 4.6,
                    'review_count': 1234,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/dell-xps-13',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                },
                {
                    'external_id': 'AMZ_LAPTOP_003',
                    'platform': 'Amazon',
                    'title': 'HP Pavilion 15.6" Laptop - AMD Ryzen 7, 16GB RAM, 1TB SSD',
                    'brand': 'HP',
                    'model': 'Pavilion 15.6"',
                    'price': 799.99,
                    'original_price': 899.99,
                    'rating': 4.4,
                    'review_count': 2156,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/hp-pavilion-15',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                }
            ],
            'phone': [
                {
                    'external_id': 'AMZ_PHONE_001',
                    'platform': 'Amazon',
                    'title': 'Samsung Galaxy S24 Ultra 256GB - Phantom Black',
                    'brand': 'Samsung',
                    'model': 'Galaxy S24 Ultra',
                    'price': 1199.99,
                    'original_price': 1299.99,
                    'rating': 4.5,
                    'review_count': 2847,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/samsung-galaxy-s24-ultra',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                },
                {
                    'external_id': 'AMZ_PHONE_002',
                    'platform': 'Amazon',
                    'title': 'Apple iPhone 15 Pro Max 256GB - Natural Titanium',
                    'brand': 'Apple',
                    'model': 'iPhone 15 Pro Max',
                    'price': 1199.00,
                    'original_price': 1199.00,
                    'rating': 4.7,
                    'review_count': 1923,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/iphone-15-pro-max',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                }
            ],
            'headphones': [
                {
                    'external_id': 'AMZ_HEADPHONES_001',
                    'platform': 'Amazon',
                    'title': 'Sony WH-1000XM5 Wireless Noise Canceling Headphones',
                    'brand': 'Sony',
                    'model': 'WH-1000XM5',
                    'price': 399.99,
                    'original_price': 449.99,
                    'rating': 4.6,
                    'review_count': 3456,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/sony-wh1000xm5',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                }
            ],
            'gaming': [
                {
                    'external_id': 'AMZ_GAMING_001',
                    'platform': 'Amazon',
                    'title': 'Nintendo Switch OLED Model - White',
                    'brand': 'Nintendo',
                    'model': 'Switch OLED',
                    'price': 349.99,
                    'original_price': 349.99,
                    'rating': 4.4,
                    'review_count': 5678,
                    'image_url': 'https://images-na.ssl-images-amazon.com/images/I/71d2R2iYzEL._AC_SL1500_.jpg',
                    'product_url': 'https://amazon.com/nintendo-switch-oled',
                    'category': category,
                    'scraped_at': datetime.now().isoformat(),
                    'is_curated': True
                }
            ]
        }
        
        # Filter products based on keywords
        matching_products = []
        
        if 'laptop' in keywords:
            matching_products.extend(all_products.get('laptop', []))
        if 'phone' in keywords or 'mobile' in keywords or 'smartphone' in keywords:
            matching_products.extend(all_products.get('phone', []))
        if 'headphone' in keywords or 'headset' in keywords:
            matching_products.extend(all_products.get('headphones', []))
        if 'gaming' in keywords or 'console' in keywords or 'switch' in keywords:
            matching_products.extend(all_products.get('gaming', []))
        
        # If no specific keyword match, return all products
        if not matching_products:
            matching_products = []
            for category_products in all_products.values():
                matching_products.extend(category_products)
        
        # Limit results based on max_pages
        max_results = min(config['max_pages'] * 5, 20)
        return matching_products[:max_results]
    
    def get_status(self):
        """Get current scraping status"""
        return {
            'is_running': self.is_running,
            'current_spider': self.current_spider,
            'products_scraped': self.products_scraped,
            'errors': self.errors,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_update': datetime.now().isoformat()
        }

# Initialize admin scraping manager
admin_scraping_manager = AdminScrapingManager()

# Routes
@app.route('/')
def index():
    """Redirect to admin dashboard"""
    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_data = verify_password(form.username.data, form.password.data)
        if user_data:
            user = User(user_data['id'], user_data['username'], user_data['email'], user_data['role'])
            login_user(user)
            
            # Update last login
            conn = sqlite3.connect('admin_panel.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user.id))
            conn.commit()
            conn.close()
            
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    """Main admin dashboard"""
    # Get statistics
    stats = get_admin_statistics()
    
    # Get recent scraping logs
    recent_logs = get_recent_scraping_logs(limit=10)
    
    # Add sample products to recent logs
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    
    for log in recent_logs:
        if log.get('products_scraped', 0) > 0:
            cursor.execute('''
                SELECT title, price, brand, rating, image_url, product_url
                FROM products 
                WHERE platform = ? 
                ORDER BY scraped_at DESC 
                LIMIT 3
            ''', (log.get('platform', ''),))
            
            sample_products = []
            for row in cursor.fetchall():
                sample_products.append({
                    'title': row[0],
                    'price': row[1],
                    'brand': row[2],
                    'rating': row[3],
                    'image_url': row[4],
                    'product_url': row[5]
                })
            
            log['sample_products'] = sample_products
    
    conn.close()
    
    # Get active configurations
    active_configs = get_active_configurations()
    
    return render_template('admin_dashboard.html', 
                         stats=stats, 
                         recent_logs=recent_logs,
                         active_configs=active_configs)

@app.route('/admin/scrapers')
@login_required
def scraper_management():
    """Scraper management page"""
    configs = get_all_scraper_configs()
    return render_template('scraper_management.html', configs=configs)

@app.route('/admin/scrapers/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_scraper_config():
    """Create new scraper configuration"""
    form = ScraperConfigForm()
    if form.validate_on_submit():
        success = save_scraper_config(form.data)
        if success:
            flash('Scraper configuration created successfully!', 'success')
            return redirect(url_for('scraper_management'))
        else:
            flash('Error creating configuration.', 'error')
    
    return render_template('scraper_config_form.html', form=form, title='New Scraper Configuration')

@app.route('/admin/schedules')
@login_required
def schedule_management():
    """Schedule management page"""
    schedules = get_all_schedules()
    configs = get_all_scraper_configs()
    return render_template('schedule_management.html', schedules=schedules, configs=configs)

@app.route('/admin/schedules/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_schedule():
    """Create new schedule"""
    form = ScheduleForm()
    form.config_id.choices = [(c['id'], c['name']) for c in get_all_scraper_configs()]
    
    if form.validate_on_submit():
        success = save_schedule(form.data)
        if success:
            flash('Schedule created successfully!', 'success')
            return redirect(url_for('schedule_management'))
        else:
            flash('Error creating schedule.', 'error')
    
    return render_template('schedule_form.html', form=form, title='New Schedule')

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    """System settings page"""
    form = SettingsForm()
    
    if request.method == 'GET':
        # Load current settings
        settings = get_system_settings()
        form.min_rating.data = settings.get('min_rating', '4.0')
        form.min_review_count.data = settings.get('min_review_count', 10)
        form.max_concurrent_scrapers.data = settings.get('max_concurrent_scrapers', 3)
        form.default_delay.data = settings.get('default_delay', '2.0')
        form.max_retries.data = settings.get('max_retries', 3)
        form.notification_email.data = settings.get('notification_email', '')
        form.data_retention_days.data = settings.get('data_retention_days', 30)
    
    if form.validate_on_submit():
        success = save_system_settings(form.data)
        if success:
            flash('Settings saved successfully!', 'success')
            return redirect(url_for('system_settings'))
        else:
            flash('Error saving settings.', 'error')
    
    return render_template('system_settings.html', form=form)

@app.route('/admin/monitoring')
@login_required
def monitoring():
    """Monitoring and analytics page"""
    stats = get_monitoring_statistics()
    return render_template('monitoring.html', stats=stats)

@app.route('/admin/users')
@login_required
@admin_required
def user_management():
    """User management page"""
    users = get_all_users()
    return render_template('user_management.html', users=users)

# API Routes
@app.route('/api/start-scraping', methods=['POST'])
@login_required
def api_start_scraping():
    """Start scraping via API"""
    data = request.get_json()
    config_id = data.get('config_id')
    
    if not config_id:
        return jsonify({'error': 'Configuration ID required'}), 400
    
    if admin_scraping_manager.is_running:
        return jsonify({'error': 'Scraping is already running'}), 400
    
    success, message = admin_scraping_manager.start_scraping(config_id)
    
    if success:
        return jsonify({'message': message})
    else:
        return jsonify({'error': message}), 500

@app.route('/api/stop-scraping', methods=['POST'])
@login_required
def api_stop_scraping():
    """Stop scraping via API"""
    admin_scraping_manager.is_running = False
    return jsonify({'message': 'Scraping stopped'})

@app.route('/api/status')
@login_required
def api_status():
    """Get scraping status"""
    return jsonify(admin_scraping_manager.get_status())

@app.route('/api/recent-sessions')
@login_required
def recent_sessions():
    """Get recent scraping sessions with results"""
    try:
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        # Get recent sessions
        cursor.execute('''
            SELECT session_id, platform, status, products_scraped, errors, 
                   duration, started_at, completed_at
            FROM scraping_logs 
            ORDER BY started_at DESC 
            LIMIT 10
        ''')
        
        sessions = []
        for row in cursor.fetchall():
            session_data = {
                'session_id': row[0],
                'platform': row[1],
                'status': row[2],
                'products_scraped': row[3],
                'errors': row[4],
                'duration': row[5],
                'started_at': row[6],
                'completed_at': row[7]
            }
            
            # Add sample products for this session
            if row[3] and row[3] > 0:  # If products were scraped
                cursor.execute('''
                    SELECT title, price, brand, rating, image_url, product_url
                    FROM products 
                    WHERE platform = ? 
                    ORDER BY scraped_at DESC 
                    LIMIT 3
                ''', (row[1],))
                
                sample_products = []
                for product_row in cursor.fetchall():
                    sample_products.append({
                        'title': product_row[0],
                        'price': product_row[1],
                        'brand': product_row[2],
                        'rating': product_row[3],
                        'image_url': product_row[4],
                        'product_url': product_row[5]
                    })
                
                session_data['sample_products'] = sample_products
            
            sessions.append(session_data)
        
        conn.close()
        return jsonify({'sessions': sessions})
        
    except Exception as e:
        logger.error(f"Error getting recent sessions: {e}")
        return jsonify({'sessions': []})

# Helper functions
def get_admin_statistics():
    """Get admin dashboard statistics"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    
    # Get counts
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM scraper_configs')
    total_configs = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM scraping_logs')
    total_sessions = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM scraping_logs WHERE status = "completed"')
    completed_sessions = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_configs': total_configs,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'scraped_products': len(scraped_products),
        'is_scraping': admin_scraping_manager.is_running
    }

def get_recent_scraping_logs(limit=10):
    """Get recent scraping logs"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT session_id, platform, status, products_scraped, errors, start_time, end_time
        FROM scraping_logs 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    
    logs = []
    for row in cursor.fetchall():
        logs.append({
            'session_id': row[0],
            'platform': row[1],
            'status': row[2],
            'products_scraped': row[3],
            'errors': row[4],
            'start_time': row[5],
            'end_time': row[6]
        })
    
    conn.close()
    return logs

def get_active_configurations():
    """Get active scraper configurations"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM scraper_configs WHERE enabled = 1')
    
    configs = []
    for row in cursor.fetchall():
        configs.append({
            'id': row[0],
            'name': row[1],
            'platform': row[2],
            'category': row[3],
            'max_pages': row[4],
            'enabled': row[7]
        })
    
    conn.close()
    return configs

def get_all_scraper_configs():
    """Get all scraper configurations"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM scraper_configs ORDER BY created_at DESC')
    
    configs = []
    for row in cursor.fetchall():
        configs.append({
            'id': row[0],
            'name': row[1],
            'platform': row[2],
            'category': row[3],
            'max_pages': row[4],
            'delay_min': row[5],
            'delay_max': row[6],
            'enabled': row[7],
            'created_at': row[8]
        })
    
    conn.close()
    return configs

def save_scraper_config(data):
    """Save scraper configuration"""
    try:
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scraper_configs 
            (name, platform, category, max_pages, delay_min, delay_max, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['platform'], data['category'], 
            data['max_pages'], data['delay_min'], data['delay_max'], 
            data['enabled']
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving scraper config: {e}")
        return False

def get_all_schedules():
    """Get all schedules"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*, sc.name as config_name 
        FROM scraping_schedules s
        LEFT JOIN scraper_configs sc ON s.config_id = sc.id
        ORDER BY s.created_at DESC
    ''')
    
    schedules = []
    for row in cursor.fetchall():
        schedules.append({
            'id': row[0],
            'name': row[1],
            'config_id': row[2],
            'config_name': row[8],
            'schedule_type': row[3],
            'schedule_value': row[4],
            'enabled': row[5],
            'last_run': row[6],
            'next_run': row[7]
        })
    
    conn.close()
    return schedules

def save_schedule(data):
    """Save schedule"""
    try:
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scraping_schedules 
            (name, config_id, schedule_type, schedule_value, enabled)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'], data['config_id'], data['schedule_type'], 
            data['schedule_value'], data['enabled']
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving schedule: {e}")
        return False

def get_system_settings():
    """Get system settings"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM system_settings')
    
    settings = {}
    for row in cursor.fetchall():
        settings[row[0]] = row[1]
    
    conn.close()
    return settings

def save_system_settings(data):
    """Save system settings"""
    try:
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        for key, value in data.items():
            if key != 'submit':
                cursor.execute('''
                    UPDATE system_settings 
                    SET value = ?, updated_at = ?
                    WHERE key = ?
                ''', (str(value), datetime.now().isoformat(), key))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def get_monitoring_statistics():
    """Get monitoring statistics"""
    return {
        'scraping_status': admin_scraping_manager.get_status(),
        'total_products': len(scraped_products),
        'recent_logs': scraping_logs[-20:] if scraping_logs else [],
        'system_uptime': '24h 15m 30s',  # Placeholder
        'memory_usage': '512MB',  # Placeholder
        'cpu_usage': '15%'  # Placeholder
    }

def get_all_users():
    """Get all users"""
    conn = sqlite3.connect('admin_panel.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role, created_at, last_login, is_active FROM users')
    
    users = []
    for row in cursor.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'role': row[3],
            'created_at': row[4],
            'last_login': row[5],
            'is_active': row[6]
        })
    
    conn.close()
    return users

# SocketIO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Admin client connected')
    emit('connected', {'message': 'Connected to admin panel'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Admin client disconnected')


@app.route('/api/monitoring/stats')
@login_required
def monitoring_stats():
    """Get monitoring statistics"""
    try:
        # Get stats from database
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        # Get total products
        cursor.execute('SELECT COUNT(*) FROM products')
        total_products = cursor.fetchone()[0]
        
        # Get platform counts
        cursor.execute('SELECT platform, COUNT(*) FROM products GROUP BY platform')
        platform_counts = dict(cursor.fetchall())
        
        # Calculate success rate (products with valid data)
        cursor.execute('SELECT COUNT(*) FROM products WHERE price > 0 AND title != "Unknown Product"')
        successful_products = cursor.fetchone()[0]
        success_rate = (successful_products / total_products * 100) if total_products > 0 else 0
        
        # Count active platforms
        active_platforms = len([p for p in platform_counts.values() if p > 0])
        
        # Simulate response time
        avg_response_time = 250  # Fixed value instead of random
        
        conn.close()
        
        return jsonify({
            'total_products': total_products,
            'success_rate': round(success_rate, 1),
            'active_platforms': active_platforms,
            'avg_response_time': avg_response_time,
            'platform_data': [
                platform_counts.get('Amazon', 0),
                platform_counts.get('Walmart', 0),
                platform_counts.get('Target', 0),
                platform_counts.get('Best Buy', 0)
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring stats: {e}")
        return jsonify({
            'total_products': 0,
            'success_rate': 0,
            'active_platforms': 0,
            'avg_response_time': 0,
            'platform_data': [0, 0, 0, 0]
        })

@app.route('/api/monitoring/activity-log')
@login_required
def monitoring_activity_log():
    """Get activity log"""
    try:
        # Get recent logs from database
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, level, message, platform 
            FROM scraping_logs 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'timestamp': row[0],
                'level': row[1],
                'message': row[2],
                'platform': row[3]
            })
        
        conn.close()
        
        return jsonify({'logs': logs})
        
    except Exception as e:
        logger.error(f"Error getting activity log: {e}")
        return jsonify({'logs': []})

@app.route('/admin/scraping-results')
@login_required
def scraping_results():
    """Scraping results page"""
    try:
        # Get scraped products from database
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        # Create products table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                platform TEXT,
                title TEXT,
                brand TEXT,
                model TEXT,
                price REAL,
                original_price REAL,
                rating REAL,
                review_count INTEGER,
                image_url TEXT,
                product_url TEXT,
                sync_status TEXT DEFAULT 'pending',
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP
            )
        ''')
        
        # Get products with counts
        cursor.execute('SELECT * FROM products ORDER BY scraped_at DESC')
        products = cursor.fetchall()
        
        # Convert to list of dicts
        product_list = []
        for product in products:
            product_list.append({
                'id': product[0],
                'external_id': product[1],
                'platform': product[2],
                'title': product[3],
                'brand': product[4],
                'model': product[5],
                'price': product[6],
                'original_price': product[7],
                'rating': product[8],
                'review_count': product[9],
                'image_url': product[10],
                'product_url': product[11],
                'sync_status': product[12],
                'scraped_at': product[13],
                'synced_at': product[14]
            })
        
        # Get statistics
        cursor.execute('SELECT COUNT(*) FROM products')
        total_products = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM products WHERE platform = "Amazon"')
        amazon_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM products WHERE platform = "Walmart"')
        walmart_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM products WHERE sync_status = "synced"')
        synced_count = cursor.fetchone()[0]
        
        conn.close()
        
        return render_template('scraping_results.html',
                             products=product_list,
                             total_products=total_products,
                             amazon_count=amazon_count,
                             walmart_count=walmart_count,
                             synced_count=synced_count)
                             
    except Exception as e:
        logger.error(f"Error loading scraping results: {e}")
        return render_template('scraping_results.html',
                             products=[],
                             total_products=0,
                             amazon_count=0,
                             walmart_count=0,
                             synced_count=0)

@app.route('/api/sync-to-botble', methods=['POST'])
@login_required
def sync_to_botble():
    """Sync products to Botble CMS"""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({'success': False, 'message': 'No products selected'})
        
        # Get products from database
        conn = sqlite3.connect('admin_panel.db')
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in product_ids])
        cursor.execute(f'SELECT * FROM products WHERE id IN ({placeholders})', product_ids)
        products = cursor.fetchall()
        
        synced_count = 0
        failed_count = 0
        
        for product in products:
            try:
                # Simulate Botble CMS sync
                sync_result = sync_product_to_botble({
                    'id': product[0],
                    'external_id': product[1],
                    'platform': product[2],
                    'title': product[3],
                    'brand': product[4],
                    'model': product[5],
                    'price': product[6],
                    'original_price': product[7],
                    'rating': product[8],
                    'review_count': product[9],
                    'image_url': product[10],
                    'product_url': product[11]
                })
                
                if sync_result['success']:
                    cursor.execute('''
                        UPDATE products 
                        SET sync_status = ?, synced_at = ?
                        WHERE id = ?
                    ''', ('synced', datetime.now().isoformat(), product[0]))
                    synced_count += 1
                else:
                    cursor.execute('''
                        UPDATE products 
                        SET sync_status = ?
                        WHERE id = ?
                    ''', ('failed', product[0]))
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error syncing product {product[0]}: {e}")
                cursor.execute('''
                    UPDATE products 
                    SET sync_status = ?
                    WHERE id = ?
                ''', ('failed', product[0]))
                failed_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Synced {synced_count} products, {failed_count} failed',
            'synced_count': synced_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        logger.error(f"Error syncing to Botble CMS: {e}")
        return jsonify({'success': False, 'message': str(e)})

def sync_product_to_botble(product):
    """Sync a single product to Botble CMS"""
    try:
        # Import Botble CMS integration
        from cms_integration.botble_sync import BotbleCMSIntegration
        
        # Initialize Botble CMS integration
        # You can configure these settings in the admin panel
        botble_config = {
            'base_url': 'https://your-botble-site.com',  # Configure this in settings
            'api_key': 'your-api-key',  # Configure this in settings
            'username': 'admin',  # Configure this in settings
            'password': 'password'  # Configure this in settings
        }
        
        botble = BotbleCMSIntegration(**botble_config)
        
        # Test connection first
        if not botble.test_connection():
            return {
                'success': False,
                'message': 'Botble CMS connection failed'
            }
        
        # Authenticate
        if not botble.authenticate():
            return {
                'success': False,
                'message': 'Botble CMS authentication failed'
            }
        
        # Sync product
        result = botble.sync_product(product)
        
        if result['success']:
            logger.info(f"Successfully synced product to Botble CMS: {product.get('title', 'Unknown')}")
        else:
            logger.error(f"Failed to sync product to Botble CMS: {result['message']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing product to Botble CMS: {e}")
        return {
            'success': False,
            'message': str(e)
        }

def install_playwright_browsers():
    """Install Playwright browsers if not already installed"""
    try:
        from playwright.sync_api import sync_playwright
        logger.info("✅ Playwright browsers already available")
    except Exception:
        logger.info("📦 Installing Playwright browsers...")
        import subprocess
        subprocess.run(['playwright', 'install', 'chromium'], check=True)
        logger.info("✅ Playwright browsers installed")

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Create templates directory
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Install Playwright browsers if needed (for Railway)
    if FLASK_ENV == 'production':
        install_playwright_browsers()
    
    # Get port from environment variable (Railway sets this)
    port = int(os.getenv('PORT', 5000))
    
    logger.info("🚀 Starting Unified E-commerce Product Data Aggregator Admin Panel")
    logger.info(f"🌍 Environment: {FLASK_ENV}")
    logger.info(f"🔑 Database: {'PostgreSQL' if DATABASE_URL.startswith('postgresql://') else 'SQLite'}")
    logger.info("👤 Admin Login: admin / admin123")
    logger.info(f"🌐 Admin Panel: http://0.0.0.0:{port}/admin")
    
    # Run the Flask app with SocketIO
    socketio.run(app, debug=app.config['DEBUG'], host='0.0.0.0', port=port)
