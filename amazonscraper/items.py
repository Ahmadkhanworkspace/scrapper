# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy import Field


class EcommercescraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class ProductItem(scrapy.Item):
    """Unified product item for all e-commerce platforms"""
    
    # Basic Information
    external_id = Field()  # Product ID on the source platform
    platform = Field()    # amazon, walmart, target, bestbuy
    title = Field()        # Product title
    description = Field() # Product description
    bullet_points = Field() # Key features/bullet points
    brand = Field()        # Product brand
    model = Field()        # Product model
    
    # Pricing Information
    current_price = Field()    # Current selling price
    original_price = Field()   # Original/MSRP price
    currency = Field()         # Currency code (USD, EUR, etc.)
    discount_percentage = Field() # Discount percentage
    
    # Availability
    availability_status = Field() # in_stock, out_of_stock, pre_order, limited_stock
    
    # Reviews and Ratings
    rating = Field()        # Average star rating (1-5)
    review_count = Field()  # Number of reviews
    
    # Categorization
    category = Field()      # Main category
    subcategory = Field()   # Subcategory
    
    # Media
    images = Field()        # List of image URLs and metadata
    
    # Specifications
    specifications = Field() # Key-value pairs of product specs
    
    # Variations
    variations = Field()    # Colors, sizes, styles, etc.
    
    # URLs
    product_url = Field()   # Direct link to product
    
    # Metadata
    scraped_at = Field()    # Timestamp when scraped
    spider_name = Field()   # Name of the spider that scraped this


class AmazonProductItem(ProductItem):
    """Amazon-specific product item"""
    
    # Amazon-specific fields
    asin = Field()          # Amazon Standard Identification Number
    seller_name = Field()   # Seller information
    fulfillment = Field()  # Fulfilled by Amazon or seller
    prime_eligible = Field() # Amazon Prime eligibility
    shipping_info = Field() # Shipping details
    
    # Amazon-specific pricing
    list_price = Field()    # List price
    sale_price = Field()    # Sale price
    savings = Field()       # Savings amount
    
    # Amazon-specific availability
    stock_level = Field()   # Stock level information
    delivery_time = Field() # Estimated delivery time


class WalmartProductItem(ProductItem):
    """Walmart-specific product item"""
    
    # Walmart-specific fields
    walmart_id = Field()    # Walmart product ID
    store_id = Field()      # Store ID
    pickup_available = Field() # Store pickup availability
    shipping_speed = Field() # Shipping speed options
    
    # Walmart-specific pricing
    rollback_price = Field() # Rollback pricing
    clearance_price = Field() # Clearance pricing


class TargetProductItem(ProductItem):
    """Target-specific product item"""
    
    # Target-specific fields
    tcin = Field()          # Target Catalog Item Number
    store_availability = Field() # Store availability
    drive_up_available = Field() # Drive up availability
    same_day_delivery = Field() # Same day delivery option
    
    # Target-specific pricing
    target_circle_price = Field() # Target Circle member pricing


class BestBuyProductItem(ProductItem):
    """Best Buy-specific product item"""
    
    # Best Buy-specific fields
    sku = Field()           # Stock Keeping Unit
    store_availability = Field() # Store availability
    geek_squad_services = Field() # Geek Squad services available
    
    # Best Buy-specific pricing
    member_price = Field()  # Best Buy member pricing
    open_box_price = Field() # Open box pricing


class mobileDetails(scrapy.Item):
    """Legacy mobile details item - keeping for backward compatibility"""
    url = Field()
    brand = Field()
    title = Field()
    model_name = Field()
    price = Field()
    star_rating = Field()
    no_rating = Field()
    colour = Field()
    storage_cap = Field()
    about_item = Field()
    img_url = Field()
    flipkart_url = Field()
    flipkart_price = Field()
    flipkart_star_rating = Field()
    flipkart_no_rating = Field()


class ImageItem(scrapy.Item):
    """Item for storing image information"""
    product_id = Field()
    image_url = Field()
    image_type = Field()    # primary, thumbnail, gallery, zoom
    alt_text = Field()
    width = Field()
    height = Field()
    file_size = Field()


class SpecificationItem(scrapy.Item):
    """Item for storing product specifications"""
    product_id = Field()
    spec_name = Field()
    spec_value = Field()
    spec_category = Field() # technical, physical, features, etc.


class VariationItem(scrapy.Item):
    """Item for storing product variations"""
    product_id = Field()
    variation_type = Field() # color, size, storage, style, material
    variation_value = Field()
    variation_price = Field()
    availability_status = Field()
    external_variation_id = Field()


class ReviewItem(scrapy.Item):
    """Item for storing product reviews"""
    product_id = Field()
    review_text = Field()
    rating = Field()
    reviewer_name = Field()
    review_date = Field()
    helpful_votes = Field()
    platform = Field()
    external_review_id = Field()