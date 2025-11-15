"""
Target Spider for Unified E-commerce Product Data Aggregator
"""
import scrapy
from scrapy import Request
from ..items import TargetProductItem, ImageItem, SpecificationItem, VariationItem, ReviewItem
from .base_spider import BaseSpider
import re
import json
from datetime import datetime
from typing import Optional

class TargetSpider(BaseSpider):
    name = 'target'
    allowed_domains = ['target.com']
    start_urls = [
        'https://www.target.com/c/electronics/-/N-5xtg6',
        'https://www.target.com/c/home/-/N-5xtg5',
        'https://www.target.com/c/clothing/-/N-5xtg4',
        'https://www.target.com/c/toys/-/N-5xtg3',
        'https://www.target.com/c/beauty/-/N-5xtg2',
    ]
    
    def start_requests(self):
        """Start requests for Target categories"""
        for url in self.start_urls:
            yield self.make_request(url=url, callback=self.parse_category_page)

    def parse_category_page(self, response):
        """
        Parse Target category listing pages and extract product links
        """
        # Extract product links from search results
        product_links = response.css('a[data-test="product-title"]::attr(href)').getall()
        
        # Alternative selectors for different page layouts
        if not product_links:
            product_links = response.css('div[data-test="product-details"] a::attr(href)').getall()
        
        if not product_links:
            product_links = response.css('a[href*="/p/"]::attr(href)').getall()
        
        for link in product_links:
            if link and '/p/' in link:
                yield self.make_request(url=response.urljoin(link), callback=self.parse_product_page)

        # Follow pagination
        next_page = response.css('a[data-test="next-page"]::attr(href)').get()
        if not next_page:
            next_page = response.css('a[aria-label="Next page"]::attr(href)').get()
        
        if next_page:
            yield self.make_request(url=response.urljoin(next_page), callback=self.parse_category_page)

    def parse_product_page(self, response):
        """
        Parse individual Target product pages and extract detailed information
        """
        item = TargetProductItem()
        item['platform'] = 'target'
        item['product_url'] = response.url
        item['scraped_at'] = datetime.now().isoformat()
        
        # Extract basic information
        item['title'] = self._extract_title(response)
        item['brand'] = self._extract_brand(response)
        item['description'] = self._extract_description(response)
        item['bullet_points'] = self._extract_bullet_points(response)
        item['external_id'] = self._extract_product_id(response)

        # Pricing
        item['current_price'] = self._extract_current_price(response)
        item['original_price'] = self._extract_original_price(response)
        item['currency'] = 'USD'  # Target US uses USD
        item['discount_percentage'] = self._calculate_discount_percentage(item['current_price'], item['original_price'])

        # Availability
        item['availability_status'] = self._extract_availability(response)

        # Ratings and Reviews
        item['rating'] = self._extract_rating(response)
        item['review_count'] = self._extract_review_count(response)

        # Category information
        item['category'] = self._extract_category(response)
        item['subcategory'] = self._extract_subcategory(response)

        # Images
        item['images'] = self._extract_images(response)

        # Specifications
        item['specifications'] = self._extract_specifications(response)

        # Variations
        item['variations'] = self._extract_variations(response)

        # Target-specific fields
        item['tcin'] = item['external_id']
        item['store_pickup'] = self._extract_store_pickup(response)
        item['shipping_info'] = self._extract_shipping_info(response)
        item['redcard_discount'] = self._extract_redcard_discount(response)

        yield item

    def _extract_title(self, response) -> Optional[str]:
        """Extract product title"""
        title = response.css('h1[data-test="product-title"]::text').get()
        if not title:
            title = response.css('h1[data-testid="product-title"]::text').get()
        if not title:
            title = response.css('h1.styles__ProductTitle-sc-1x8c2g0-0::text').get()
        return title.strip() if title else None

    def _extract_brand(self, response) -> Optional[str]:
        """Extract product brand"""
        brand = response.css('span[data-test="product-brand"]::text').get()
        if not brand:
            brand = response.css('span[data-testid="product-brand"]::text').get()
        if not brand:
            brand = response.css('span.styles__BrandName-sc-1x8c2g0-1::text').get()
        if not brand:
            # Try to extract from title
            title = self._extract_title(response)
            if title:
                brand_match = re.match(r'^([^-\s]+)', title)
                if brand_match:
                    brand = brand_match.group(1)
        return brand.strip() if brand else None

    def _extract_description(self, response) -> Optional[str]:
        """Extract product description"""
        description = response.css('div[data-test="product-description"]::text').get()
        if not description:
            description = response.css('div[data-testid="product-description"]::text').get()
        if not description:
            description = response.css('div.styles__ProductDescription-sc-1x8c2g0-2::text').get()
        return description.strip() if description else None

    def _extract_bullet_points(self, response) -> list:
        """Extract bullet points"""
        bullets = response.css('ul[data-test="product-highlights"] li::text').getall()
        if not bullets:
            bullets = response.css('ul[data-testid="product-highlights"] li::text').getall()
        if not bullets:
            bullets = response.css('ul.styles__ProductHighlights-sc-1x8c2g0-3 li::text').getall()
        return [bullet.strip() for bullet in bullets if bullet.strip()]

    def _extract_product_id(self, response) -> Optional[str]:
        """Extract Target product ID (TCIN)"""
        # Extract from URL
        url_match = re.search(r'/p/([^/?]+)', response.url)
        if url_match:
            return url_match.group(1)
        
        # Extract from page data
        product_id = response.css('meta[property="og:url"]::attr(content)').get()
        if product_id:
            match = re.search(r'/p/([^/?]+)', product_id)
            if match:
                return match.group(1)
        
        # Try to extract TCIN from page
        tcin = response.css('span[data-test="tcin"]::text').get()
        if tcin:
            return tcin.strip()
        
        return None

    def _extract_current_price(self, response) -> Optional[float]:
        """Extract current price"""
        price_text = response.css('span[data-test="product-price"]::text').get()
        if not price_text:
            price_text = response.css('span[data-testid="product-price"]::text').get()
        if not price_text:
            price_text = response.css('span.styles__ProductPrice-sc-1x8c2g0-4::text').get()
        
        if price_text:
            # Extract numeric value
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group())
        
        return None

    def _extract_original_price(self, response) -> Optional[float]:
        """Extract original price"""
        price_text = response.css('span[data-test="product-original-price"]::text').get()
        if not price_text:
            price_text = response.css('span[data-testid="product-original-price"]::text').get()
        if not price_text:
            price_text = response.css('span.styles__ProductOriginalPrice-sc-1x8c2g0-5::text').get()
        
        if price_text:
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group())
        
        return None

    def _calculate_discount_percentage(self, current_price: Optional[float], original_price: Optional[float]) -> Optional[float]:
        """Calculate discount percentage"""
        if current_price and original_price and original_price > current_price:
            return round(((original_price - current_price) / original_price) * 100, 2)
        return None

    def _extract_availability(self, response) -> str:
        """Extract availability status"""
        availability_text = response.css('span[data-test="availability-status"]::text').get()
        if not availability_text:
            availability_text = response.css('span[data-testid="availability-status"]::text').get()
        if not availability_text:
            availability_text = response.css('span.styles__AvailabilityStatus-sc-1x8c2g0-6::text').get()
        
        if availability_text:
            availability_text = availability_text.strip().lower()
            if 'in stock' in availability_text or 'available' in availability_text:
                return 'in_stock'
            elif 'out of stock' in availability_text or 'unavailable' in availability_text:
                return 'out_of_stock'
            elif 'limited' in availability_text:
                return 'limited_stock'
            elif 'pre-order' in availability_text:
                return 'pre_order'
        
        return 'unknown'

    def _extract_rating(self, response) -> Optional[float]:
        """Extract product rating"""
        rating_text = response.css('span[data-test="product-rating"]::text').get()
        if not rating_text:
            rating_text = response.css('span[data-testid="product-rating"]::text').get()
        if not rating_text:
            rating_text = response.css('span.styles__ProductRating-sc-1x8c2g0-7::text').get()
        
        if rating_text:
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_match:
                rating = float(rating_match.group(1))
                if 0 <= rating <= 5:
                    return rating
        
        return None

    def _extract_review_count(self, response) -> int:
        """Extract review count"""
        review_text = response.css('span[data-test="review-count"]::text').get()
        if not review_text:
            review_text = response.css('span[data-testid="review-count"]::text').get()
        if not review_text:
            review_text = response.css('span.styles__ReviewCount-sc-1x8c2g0-8::text').get()
        
        if review_text:
            review_match = re.search(r'(\d+)', review_text.replace(',', ''))
            if review_match:
                return int(review_match.group(1))
        
        return 0

    def _extract_category(self, response) -> Optional[str]:
        """Extract product category"""
        category = response.css('nav[data-test="breadcrumb"] a::text').getall()
        if category and len(category) > 1:
            return category[1].strip()
        
        # Try alternative selectors
        category = response.css('ol.breadcrumb li a::text').getall()
        if category and len(category) > 1:
            return category[1].strip()
        
        return None

    def _extract_subcategory(self, response) -> Optional[str]:
        """Extract product subcategory"""
        breadcrumbs = response.css('nav[data-test="breadcrumb"] a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 2:
            return breadcrumbs[2].strip()
        
        # Try alternative selectors
        breadcrumbs = response.css('ol.breadcrumb li a::text').getall()
        if breadcrumbs and len(breadcrumbs) > 2:
            return breadcrumbs[2].strip()
        
        return None

    def _extract_images(self, response) -> list:
        """Extract product images"""
        images = []
        
        # Primary image
        primary_img = response.css('img[data-test="product-image"]::attr(src)').get()
        if primary_img:
            images.append(ImageItem(url=primary_img, type='primary'))
        
        # Gallery images
        gallery_imgs = response.css('div[data-test="image-gallery"] img::attr(src)').getall()
        if not gallery_imgs:
            gallery_imgs = response.css('div.styles__ImageGallery-sc-1x8c2g0-9 img::attr(src)').getall()
        
        for img_url in gallery_imgs:
            if img_url and img_url not in [img['url'] for img in images]:
                images.append(ImageItem(url=img_url, type='gallery'))
        
        return images

    def _extract_specifications(self, response) -> list:
        """Extract product specifications"""
        specs = []
        
        # Specifications table
        spec_rows = response.css('table[data-test="specifications"] tr').getall()
        if not spec_rows:
            spec_rows = response.css('table.styles__Specifications-sc-1x8c2g0-10 tr').getall()
        
        for row in spec_rows:
            spec_name = response.css('td:first-child::text').get()
            spec_value = response.css('td:last-child::text').get()
            if spec_name and spec_value:
                specs.append(SpecificationItem(
                    spec_name=spec_name.strip(),
                    spec_value=spec_value.strip()
                ))
        
        return specs

    def _extract_variations(self, response) -> list:
        """Extract product variations"""
        variations = []
        
        # Color variations
        color_options = response.css('div[data-test="color-options"] button::attr(data-color)').getall()
        if not color_options:
            color_options = response.css('div.styles__ColorOptions-sc-1x8c2g0-11 button::attr(data-color)').getall()
        
        for color in color_options:
            if color:
                variations.append(VariationItem(
                    variation_type='color',
                    variation_value=color.strip()
                ))
        
        # Size variations
        size_options = response.css('div[data-test="size-options"] button::text').getall()
        if not size_options:
            size_options = response.css('div.styles__SizeOptions-sc-1x8c2g0-12 button::text').getall()
        
        for size in size_options:
            if size and size.strip():
                variations.append(VariationItem(
                    variation_type='size',
                    variation_value=size.strip()
                ))
        
        return variations

    def _extract_store_pickup(self, response) -> bool:
        """Extract store pickup availability"""
        pickup_text = response.css('span[data-test="store-pickup"]::text').get()
        if not pickup_text:
            pickup_text = response.css('span.styles__StorePickup-sc-1x8c2g0-13::text').get()
        
        if pickup_text:
            return 'available' in pickup_text.lower()
        
        return False

    def _extract_shipping_info(self, response) -> Optional[str]:
        """Extract shipping information"""
        shipping_text = response.css('span[data-test="shipping-info"]::text').get()
        if not shipping_text:
            shipping_text = response.css('span.styles__ShippingInfo-sc-1x8c2g0-14::text').get()
        
        return shipping_text.strip() if shipping_text else None

    def _extract_redcard_discount(self, response) -> Optional[float]:
        """Extract RedCard discount percentage"""
        redcard_text = response.css('span[data-test="redcard-discount"]::text').get()
        if not redcard_text:
            redcard_text = response.css('span.styles__RedCardDiscount-sc-1x8c2g0-15::text').get()
        
        if redcard_text:
            discount_match = re.search(r'(\d+)%', redcard_text)
            if discount_match:
                return float(discount_match.group(1))
        
        return None


