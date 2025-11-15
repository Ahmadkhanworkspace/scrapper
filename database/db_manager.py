"""
Database configuration and connection management for Unified E-commerce Product Data Aggregator
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration class"""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME', 'ecommerce_aggregator')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'password')
        
        # Connection pool settings
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', '1'))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', '10'))
        
        # MongoDB settings
        self.mongo_host = os.getenv('MONGO_HOST', 'localhost')
        self.mongo_port = int(os.getenv('MONGO_PORT', '27017'))
        self.mongo_database = os.getenv('MONGO_DB', 'ecommerce_cache')
        
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"

class DatabaseManager:
    """Database connection and operation manager"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection_pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.connection_pool = SimpleConnectionPool(
                self.config.min_connections,
                self.config.max_connections,
                self.config.get_connection_string()
            )
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get database connection from pool"""
        connection = None
        try:
            connection = self.connection_pool.getconn()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Execute a database query"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(query, params)
                    if fetch:
                        return cursor.fetchall()
                    conn.commit()
                    return None
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Query execution error: {e}")
                    raise
    
    def insert_product(self, product_data: Dict[str, Any]) -> str:
        """Insert a new product into the database"""
        query = """
        INSERT INTO products (
            external_id, platform, title, description, bullet_points, brand, model,
            current_price, original_price, currency, discount_percentage, availability_status,
            rating, review_count, category, subcategory, product_url
        ) VALUES (
            %(external_id)s, %(platform)s, %(title)s, %(description)s, %(bullet_points)s,
            %(brand)s, %(model)s, %(current_price)s, %(original_price)s, %(currency)s,
            %(discount_percentage)s, %(availability_status)s, %(rating)s, %(review_count)s,
            %(category)s, %(subcategory)s, %(product_url)s
        ) RETURNING id
        """
        
        result = self.execute_query(query, product_data, fetch=True)
        return result[0]['id'] if result else None
    
    def update_product_price(self, product_id: str, new_price: float, currency: str = 'USD'):
        """Update product price and record in price history"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    # Get current price for comparison
                    cursor.execute("SELECT current_price FROM products WHERE id = %s", (product_id,))
                    current_price = cursor.fetchone()[0]
                    
                    # Update product price
                    cursor.execute("""
                        UPDATE products 
                        SET current_price = %s, last_price_update = NOW(), updated_at = NOW()
                        WHERE id = %s
                    """, (new_price, product_id))
                    
                    # Record price change
                    price_change_type = 'new' if current_price is None else (
                        'increase' if new_price > current_price else (
                            'decrease' if new_price < current_price else 'stable'
                        )
                    )
                    
                    cursor.execute("""
                        INSERT INTO price_history (product_id, price, currency, platform, price_change_type)
                        SELECT %s, %s, %s, platform, %s FROM products WHERE id = %s
                    """, (product_id, new_price, currency, price_change_type, product_id))
                    
                    conn.commit()
                    logger.info(f"Updated price for product {product_id}: {current_price} -> {new_price}")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to update product price: {e}")
                    raise
    
    def insert_product_specifications(self, product_id: str, specifications: Dict[str, Any]):
        """Insert product specifications"""
        query = """
        INSERT INTO product_specifications (product_id, spec_name, spec_value, spec_category)
        VALUES (%s, %s, %s, %s)
        """
        
        for spec_name, spec_value in specifications.items():
            if isinstance(spec_value, dict):
                for category, specs in spec_value.items():
                    for name, value in specs.items():
                        self.execute_query(query, (product_id, name, str(value), category))
            else:
                self.execute_query(query, (product_id, spec_name, str(spec_value), 'general'))
    
    def insert_product_images(self, product_id: str, images: List[Dict[str, Any]]):
        """Insert product images"""
        query = """
        INSERT INTO product_images (product_id, image_url, image_type, alt_text)
        VALUES (%s, %s, %s, %s)
        """
        
        for image in images:
            self.execute_query(query, (
                product_id,
                image.get('url'),
                image.get('type', 'gallery'),
                image.get('alt_text', '')
            ))
    
    def insert_product_variations(self, product_id: str, variations: List[Dict[str, Any]]):
        """Insert product variations"""
        query = """
        INSERT INTO product_variations (product_id, variation_type, variation_value, variation_price, availability_status)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        for variation in variations:
            self.execute_query(query, (
                product_id,
                variation.get('type'),
                variation.get('value'),
                variation.get('price'),
                variation.get('availability', 'in_stock')
            ))
    
    def get_products_for_price_update(self, platform: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get products that need price updates"""
        query = """
        SELECT id, external_id, platform, product_url, current_price, last_price_update
        FROM products 
        WHERE is_active = TRUE
        AND (last_price_update IS NULL OR last_price_update < NOW() - INTERVAL '1 hour')
        """
        
        params = []
        if platform:
            query += " AND platform = %s"
            params.append(platform)
        
        query += " ORDER BY last_price_update ASC NULLS FIRST LIMIT %s"
        params.append(limit)
        
        return self.execute_query(query, tuple(params), fetch=True)
    
    def get_curated_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get curated products meeting quality criteria"""
        query = """
        SELECT p.*, 
               COUNT(DISTINCT pi.id) as image_count,
               COUNT(DISTINCT ps.id) as spec_count,
               COUNT(DISTINCT pv.id) as variation_count
        FROM products p
        LEFT JOIN product_images pi ON p.id = pi.product_id
        LEFT JOIN product_specifications ps ON p.id = ps.product_id
        LEFT JOIN product_variations pv ON p.id = pv.product_id
        WHERE p.is_active = TRUE 
            AND p.is_curated = TRUE
            AND p.availability_status = 'in_stock'
            AND p.rating >= 4.0
        GROUP BY p.id
        ORDER BY p.rating DESC, p.review_count DESC
        LIMIT %s
        """
        
        return self.execute_query(query, (limit,), fetch=True)
    
    def log_scraping_session(self, platform: str, spider_name: str, start_time: datetime, 
                           status: str = 'running', products_scraped: int = 0, 
                           errors_count: int = 0, error_details: str = None) -> str:
        """Log scraping session"""
        query = """
        INSERT INTO scraping_logs (platform, spider_name, start_time, end_time, status, products_scraped, errors_count, error_details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        
        end_time = datetime.now() if status in ['completed', 'failed', 'cancelled'] else None
        
        result = self.execute_query(query, (
            platform, spider_name, start_time, end_time, status, 
            products_scraped, errors_count, error_details
        ), fetch=True)
        
        return result[0]['id'] if result else None
    
    def close_pool(self):
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")

# Global database manager instance
db_config = DatabaseConfig()
db_manager = DatabaseManager(db_config)

# Utility functions
def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    return db_manager

def test_connection() -> bool:
    """Test database connection"""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test database connection
    if test_connection():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")


