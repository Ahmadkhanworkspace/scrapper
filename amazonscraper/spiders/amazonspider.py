from urllib.parse import urlencode
import scrapy
from scrapy import Request
from ..items import mobileDetails
import re


class AmazonSpiderSpider(scrapy.Spider):
    name = 'amazon_spider'
    allowed_domains = ['amazon.com']
    API = "YOUR-SCRAPERAPI-KEY"

    def __init__(self, keywords='electronics', max_pages=3, *args, **kwargs):
        super(AmazonSpiderSpider, self).__init__(*args, **kwargs)
        self.keywords = keywords
        self.max_pages = int(max_pages)
        self.count = 1
        # Build URL with keywords for Amazon USA
        self.url = f'https://www.amazon.com/s?k={keywords.replace(" ", "+")}'

    def get_url(url):
        # For testing purposes, return the original URL without proxy
        # Uncomment the lines below to use ScraperAPI proxy service
        # payload = {'api_key': AmazonSpiderSpider.API,
        #            'url': url, 'country_code': 'us'}
        # proxy_url = 'http://api.scraperapi.com/?' + urlencode(payload)
        # return proxy_url
        return url

    def start_requests(self):
        yield Request(
            url=self.get_url(self.url),
            callback=self.parse
        )

    def parse(self, response, **kwargs):

        details = mobileDetails()

        url_phones = response.css(
            'div.s-product-image-container > div.aok-relative > span > a::attr(href)').getall()
        img_urls = response.css(
            'div.a-section>img.s-image::attr(src)').getall()
        titles = response.css('span.a-size-medium::text').getall()

        model_names = []
        brands = []
        colours = []
        storage_caps = []

        delimiter = "()|"
        for title in titles:
            words = list(filter(None, re.split(f'[{delimiter}]', title)))
            try:
                if words[0] == 'Renewed':
                    model_names.append(words[1])
                    brands.append(list(filter(None, (words[1].split(' '))))[0])
                    colours.append(
                        list(filter(None, (words[2].split(','))))[0])
                    storage_caps.append(
                        list(filter(None, (words[2].split(','))))[1:])

                else:
                    model_names.append(words[0])
                    brands.append(list(filter(None, (words[0].split(' '))))[0])
                    colours.append(
                        list(filter(None, (words[1].split(','))))[0])
                    storage_caps.append(
                        list(filter(None, (words[1].split(','))))[1:])

            except IndexError:
                continue

        details['url'] = url_phones
        details['title'] = titles
        details['brand'] = brands
        details['model_name'] = model_names
        details['price'] = response.css('span.a-price-whole::text').getall()
        details['star_rating'] = response.css('span.a-icon-alt::text').getall()
        details['no_rating'] = response.css(
            'span > a.a-link-normal s-underline-text s-underline-link-text s-link-style > span.a-size-base s-underline-text ::text').getall()
        details['colour'] = colours
        details['storage_cap'] = storage_caps
        details['img_url'] = img_urls

        yield details

        if self.count <= self.max_pages:
            self.count += 1
            next_url = f'https://www.amazon.com/s?k={self.keywords.replace(" ", "+")}&page={self.count}'
            yield Request(
                url=self.get_url(next_url),
                callback=self.parse
            )
        else:
            pass
