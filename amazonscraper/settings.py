# Scrapy settings for amazonscraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = 'amazonscraper'

SPIDER_MODULES = ['amazonscraper.spiders']
NEWSPIDER_MODULE = 'amazonscraper.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure pipelines
ITEM_PIPELINES = {
    'amazonscraper.pipelines.ValidationPipeline': 100,
    'amazonscraper.pipelines.DuplicatesPipeline': 200,
    'amazonscraper.pipelines.DataProcessingPipeline': 300,
    'amazonscraper.pipelines.ImageDownloadPipeline': 400,
    'amazonscraper.pipelines.DatabasePipeline': 500,
    'amazonscraper.pipelines.JsonWriterPipeline': 600,
    'amazonscraper.pipelines.StatisticsPipeline': 700,
}

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = 0.5

# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    'amazonscraper.middlewares.AmazonscraperSpiderMiddleware': 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    'amazonscraper.middlewares.AmazonscraperDownloaderMiddleware': 543,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy_user_agents.RotateUserAgentMiddleware': 400,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
#}

# Configure item exporters
# See https://docs.scrapy.org/en/latest/topics/exporters.html
#FEED_EXPORTERS = {
#    'json': 'scrapy.exporters.JsonItemExporter',
#}

# Configure logging
LOG_LEVEL = 'INFO'
LOG_FILE = 'scrapy.log'

# Configure concurrent requests
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Configure autothrottle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Configure retry
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Configure cache
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = 'httpcache'

# Configure user agents
USER_AGENT_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
]

# Configure proxy settings (uncomment when using proxies)
# ROTATING_PROXY_LIST_PATH = 'proxies.txt'
# ROTATING_PROXY_PAGE_RETRY_TIMES = 5

# Configure MongoDB settings
MONGO_URI = 'mongodb://localhost:27017'
MONGO_DATABASE = 'ecommerce_cache'

# Configure PostgreSQL settings
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'ecommerce_aggregator'
DB_USER = 'postgres'
DB_PASSWORD = 'password'

# Configure Redis settings
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# Configure Celery settings
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Configure image download settings
IMAGES_STORE = 'downloaded_images'
IMAGES_MIN_HEIGHT = 110
IMAGES_MIN_WIDTH = 110
IMAGES_EXPIRES = 90

# Configure feed settings
FEEDS = {
    'scraped_data.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'indent': 2,
    },
}

# Configure custom settings for different spiders
SPIDER_SETTINGS = {
    'amazon': {
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 1.0,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
    },
    'walmart': {
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 6,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.5,
    },
    'target': {
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 6,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.5,
    },
    'bestbuy': {
        'DOWNLOAD_DELAY': 1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 6,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.5,
    },
}

# Configure data quality settings
MIN_RATING = 4.0
MIN_REVIEW_COUNT = 10
REQUIRED_FIELDS = ['external_id', 'platform', 'title', 'current_price', 'product_url']

# Configure scheduling settings
SCHEDULE_INTERVAL_HOURS = 1
SCHEDULE_FULL_CRAWL_HOURS = 24

# Configure notification settings
ENABLE_NOTIFICATIONS = True
NOTIFICATION_EMAIL = 'admin@example.com'
NOTIFICATION_WEBHOOK_URL = None

# Configure monitoring settings
ENABLE_MONITORING = True
MONITORING_INTERVAL_SECONDS = 300
ALERT_THRESHOLD_ERROR_RATE = 0.1
ALERT_THRESHOLD_RESPONSE_TIME = 5.0
