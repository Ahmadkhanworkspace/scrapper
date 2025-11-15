"""
PostgreSQL Database Initialization Script for Railway
This script creates all necessary tables in PostgreSQL
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from werkzeug.security import generate_password_hash

def init_postgres_db():
    """Initialize PostgreSQL database with all tables"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        # Parse DATABASE_URL
        # Format: postgresql://user:password@host:port/database
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ Connected to PostgreSQL database")
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Scraper configurations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_configs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                category VARCHAR(100) NOT NULL,
                max_pages INTEGER DEFAULT 3,
                delay_min REAL DEFAULT 1.0,
                delay_max REAL DEFAULT 2.0,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Scraping schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraping_schedules (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                config_id INTEGER,
                schedule_type VARCHAR(50) NOT NULL,
                schedule_value VARCHAR(255) NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                last_run TIMESTAMP,
                next_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (config_id) REFERENCES scraper_configs (id)
            )
        ''')
        
        # Scraping logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraping_logs (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                platform VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                products_scraped INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                external_id VARCHAR(255),
                platform VARCHAR(50) NOT NULL,
                title TEXT NOT NULL,
                brand VARCHAR(255),
                model VARCHAR(255),
                price DECIMAL(10, 2),
                original_price DECIMAL(10, 2),
                rating REAL,
                review_count INTEGER,
                image_url TEXT,
                product_url TEXT,
                sync_status VARCHAR(50) DEFAULT 'pending',
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP
            )
        ''')
        
        # System settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default admin user
        admin_password = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role)
            VALUES ('admin', 'admin@ecommerce-aggregator.com', %s, 'admin')
            ON CONFLICT (username) DO NOTHING
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
                INSERT INTO system_settings (key, value, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO NOTHING
            ''', (key, value, description))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ PostgreSQL database initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing PostgreSQL database: {e}")
        return False

if __name__ == '__main__':
    init_postgres_db()

