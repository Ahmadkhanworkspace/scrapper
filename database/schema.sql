-- Unified E-commerce Product Data Aggregator Database Schema
-- PostgreSQL Database Setup

-- Create database (run this manually)
-- CREATE DATABASE ecommerce_aggregator;

-- Connect to the database
-- \c ecommerce_aggregator;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Products table - Main product information
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(255) UNIQUE NOT NULL,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('amazon', 'walmart', 'target', 'bestbuy')),
    title TEXT NOT NULL,
    description TEXT,
    bullet_points TEXT[],
    brand VARCHAR(100),
    model VARCHAR(100),
    current_price DECIMAL(10,2),
    original_price DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD',
    discount_percentage DECIMAL(5,2),
    availability_status VARCHAR(20) CHECK (availability_status IN ('in_stock', 'out_of_stock', 'pre_order', 'limited_stock')),
    rating DECIMAL(3,2) CHECK (rating >= 0 AND rating <= 5),
    review_count INTEGER DEFAULT 0,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    product_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_price_update TIMESTAMP,
    last_availability_update TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_curated BOOLEAN DEFAULT FALSE
);

-- Product specifications table
CREATE TABLE product_specifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    spec_name VARCHAR(100) NOT NULL,
    spec_value TEXT NOT NULL,
    spec_category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Product images table
CREATE TABLE product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    image_type VARCHAR(20) CHECK (image_type IN ('primary', 'thumbnail', 'gallery', 'zoom')),
    alt_text TEXT,
    is_downloaded BOOLEAN DEFAULT FALSE,
    local_path TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Product variations table
CREATE TABLE product_variations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    variation_type VARCHAR(50) NOT NULL CHECK (variation_type IN ('color', 'size', 'storage', 'style', 'material')),
    variation_value VARCHAR(100) NOT NULL,
    variation_price DECIMAL(10,2),
    availability_status VARCHAR(20) CHECK (availability_status IN ('in_stock', 'out_of_stock', 'pre_order', 'limited_stock')),
    external_variation_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Price history table
CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    platform VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW(),
    price_change_type VARCHAR(20) CHECK (price_change_type IN ('increase', 'decrease', 'stable', 'new'))
);

-- Product reviews table
CREATE TABLE product_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    review_text TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    reviewer_name VARCHAR(100),
    review_date DATE,
    helpful_votes INTEGER DEFAULT 0,
    platform VARCHAR(50) NOT NULL,
    external_review_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scraping logs table
CREATE TABLE scraping_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(50) NOT NULL,
    spider_name VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    products_scraped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Data quality reports table
CREATE TABLE data_quality_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_date DATE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    total_products INTEGER NOT NULL,
    products_with_images INTEGER DEFAULT 0,
    products_with_specs INTEGER DEFAULT 0,
    products_with_reviews INTEGER DEFAULT 0,
    average_rating DECIMAL(3,2),
    data_completeness_percentage DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Product deduplication table
CREATE TABLE product_deduplication (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    primary_product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    duplicate_product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    similarity_score DECIMAL(5,4),
    match_type VARCHAR(50) CHECK (match_type IN ('exact', 'fuzzy', 'manual', 'image')),
    status VARCHAR(20) CHECK (status IN ('pending', 'approved', 'rejected', 'merged')),
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(100)
);

-- Indexes for performance optimization
CREATE INDEX idx_products_platform ON products(platform);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_availability ON products(availability_status);
CREATE INDEX idx_products_rating ON products(rating);
CREATE INDEX idx_products_price ON products(current_price);
CREATE INDEX idx_products_updated_at ON products(updated_at);
CREATE INDEX idx_products_external_id ON products(external_id);

CREATE INDEX idx_specifications_product_id ON product_specifications(product_id);
CREATE INDEX idx_specifications_name ON product_specifications(spec_name);

CREATE INDEX idx_images_product_id ON product_images(product_id);
CREATE INDEX idx_images_type ON product_images(image_type);

CREATE INDEX idx_variations_product_id ON product_variations(product_id);
CREATE INDEX idx_variations_type ON product_variations(variation_type);

CREATE INDEX idx_price_history_product_id ON price_history(product_id);
CREATE INDEX idx_price_history_recorded_at ON price_history(recorded_at);

CREATE INDEX idx_reviews_product_id ON product_reviews(product_id);
CREATE INDEX idx_reviews_rating ON product_reviews(rating);

CREATE INDEX idx_scraping_logs_platform ON scraping_logs(platform);
CREATE INDEX idx_scraping_logs_start_time ON scraping_logs(start_time);

-- Triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views for common queries
CREATE VIEW active_products AS
SELECT 
    p.*,
    COUNT(DISTINCT pi.id) as image_count,
    COUNT(DISTINCT ps.id) as spec_count,
    COUNT(DISTINCT pv.id) as variation_count
FROM products p
LEFT JOIN product_images pi ON p.id = pi.product_id
LEFT JOIN product_specifications ps ON p.id = ps.product_id
LEFT JOIN product_variations pv ON p.id = pv.product_id
WHERE p.is_active = TRUE
GROUP BY p.id;

CREATE VIEW curated_products AS
SELECT 
    p.*,
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
GROUP BY p.id;

-- Sample data insertion (for testing)
INSERT INTO products (external_id, platform, title, brand, current_price, availability_status, rating, review_count, category, product_url) VALUES
('B08N5WRWNW', 'amazon', 'Echo Dot (4th Gen) | Smart speaker with Alexa | Charcoal', 'Amazon', 49.99, 'in_stock', 4.5, 125000, 'Electronics', 'https://amazon.com/dp/B08N5WRWNW'),
('490552', 'walmart', 'Apple AirPods Pro (2nd Generation)', 'Apple', 249.00, 'in_stock', 4.7, 89000, 'Electronics', 'https://walmart.com/ip/490552'),
('TCIN-123456', 'target', 'Samsung 55" Class QLED 4K UHD Smart TV', 'Samsung', 699.99, 'in_stock', 4.3, 45000, 'Electronics', 'https://target.com/p/TCIN-123456'),
('6426149', 'bestbuy', 'MacBook Air 13-inch M2 Chip', 'Apple', 1199.99, 'in_stock', 4.8, 67000, 'Computers', 'https://bestbuy.com/site/6426149');

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;


