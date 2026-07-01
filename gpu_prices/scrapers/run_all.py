"""
Unified multi-store scraper runner.
Scrapes all scrapable Bangladeshi GPU stores into the shared database.
"""
import sys, os, asyncio, re
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
sys.path.insert(0, _parent_dir)
sys.path.insert(0, _this_dir)

from models import init_db
DB_PATH = os.path.join(_parent_dir, "gpu_prices.db")
from base_opencart import OpenCartScraper
from utils import parse_price, save_product, get_or_create_seller
import scrape_techlandbd

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---- OpenCart Store Configs ----
OPENCART_STORES = [
    {
        'name': 'StarTech',
        'slug': 'startech',
        'website': 'https://www.startech.com.bd',
        'listing_url': 'https://www.startech.com.bd/component/graphics-card',
        'product_selector': 'div.p-item',
        'name_selector': 'h4.p-item-name a',
        'link_selector': 'h4.p-item-name a',
        'image_selector': '.p-item-img img',
        'price_selector': '.p-item-price',
        'stock_selector': None,
        'pagination_selector': 'ul.pagination',
    },
    {
        'name': 'PotakaIT',
        'slug': 'potakait',
        'website': 'https://www.potakait.com',
        'listing_url': 'https://www.potakait.com/graphics-cards',
        'product_selector': 'div.product-item',
        'name_selector': 'h4.title a',
        'link_selector': 'h4.title a',
        'image_selector': '.product-img img',
        'price_selector': 'p.price',
        'stock_selector': None,
        'pagination_selector': 'ul.pagination',
    },
    {
        'name': 'UltraTech',
        'slug': 'ultratech',
        'website': 'https://www.ultratech.com.bd',
        'listing_url': 'https://www.ultratech.com.bd/graphics-card',
        'product_selector': 'div.product-layout',
        'name_selector': '.name a',
        'link_selector': '.name a',
        'image_selector': '.image img',
        'price_selector': '.price',
        'stock_selector': None,
        'pagination_selector': 'ul.pagination',
    },
    {
        'name': 'UCC',
        'slug': 'ucc',
        'website': 'https://www.ucc.com.bd',
        'listing_url': 'https://www.ucc.com.bd/graphics-card',
        'product_selector': 'div.product-layout',
        'name_selector': '.name a',
        'link_selector': '.name a',
        'image_selector': '.image img',
        'price_selector': '.price',
        'stock_selector': None,
        'pagination_selector': 'ul.pagination',
    },
    {
        'name': 'Creatus',
        'slug': 'creatus',
        'website': 'https://www.creatus.com.bd',
        'listing_url': 'https://www.creatus.com.bd/graphics-card',
        'product_selector': 'div.product-layout',
        'name_selector': '.name a',
        'link_selector': '.name a',
        'image_selector': '.image img',
        'price_selector': '.price',
        'stock_selector': None,
        'pagination_selector': 'ul.pagination',
    },
]


async def scrape_woocommerce(session, config, limit_pages=None):
    """Scrape a WooCommerce-based store."""
    seller = get_or_create_seller(session, config['name'], config['slug'], config['website'])
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        url = config['listing_url']
        page_num = 0
        all_count = 0

        while url:
            page_num += 1
            if limit_pages and page_num > limit_pages:
                break

            print(f"  [{config['slug']}] Page {page_num}...", end=" ", flush=True)
            products, next_url = await _scrape_woocommerce_page(client, url, config)

            if not products:
                print("No products found, stopping")
                break

            for pd in products:
                save_product(session, seller, pd)
                all_count += 1

            session.commit()
            print(f"{len(products)} products (total: {all_count})")
            url = next_url

        print(f"  [{config['slug']}] Done! {all_count} total records.")
        return all_count


async def _scrape_woocommerce_page(client, url, config):
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [], None

    soup = BeautifulSoup(resp.text, 'lxml')
    products = []

    containers = soup.select(config.get('product_selector', 'li.product'))
    if not containers:
        return [], None

    for item in containers:
        prod = _extract_woocommerce_product(item, config)
        if prod:
            products.append(prod)

    next_url = _find_woocommerce_next(soup, url)
    return products, next_url


def _extract_woocommerce_product(item, config):
    try:
        name_el = item.select_one(config.get('name_selector', 'h2'))
        if not name_el:
            name_el = item.select_one('.woocommerce-loop-product__title')
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        link_el = item.select_one(config.get('link_selector', 'a.woocommerce-LoopProduct-link'))
        if not link_el:
            link_el = item.find('a', href=True)
        href = ''
        product_url = ''
        if link_el:
            href = link_el.get('href', '')
            product_url = href if href.startswith('http') else urljoin(config['website'], href)

        img_el = item.select_one(config.get('image_selector', 'img'))
        img_url = ''
        if img_el:
            img_url = img_el.get('data-src') or img_el.get('src') or ''

        current_price = 0.0
        original_price = None
        price_el = item.select_one(config.get('price_selector', '.price'))
        if price_el:
            full_text = price_el.get_text(strip=True)
            nums = parse_price(full_text)
            if len(nums) >= 2:
                original_price = nums[0]
                current_price = nums[1]
            elif len(nums) == 1:
                current_price = nums[0]

        in_stock = True
        stock_el = item.select_one(config.get('stock_selector', '.stock'))
        if stock_el:
            txt = stock_el.get_text(strip=True).lower()
            if 'out of stock' in txt:
                in_stock = False
        else:
            txt = item.get_text(strip=True).lower()
            if 'out of stock' in txt and 'in stock' not in txt:
                in_stock = False

        return {
            'name': name,
            'url': product_url,
            'image_url': img_url,
            'price': current_price,
            'original_price': original_price if original_price and original_price != current_price else None,
            'in_stock': in_stock,
        }
    except Exception:
        return None


def _find_woocommerce_next(soup, current_url):
    next_link = soup.select_one('a.next.page-numbers')
    if next_link and next_link.get('href'):
        href = next_link['href']
        return href if href.startswith('http') else urljoin('https://bengalpcbd.com', href)
    return None


# ---- WooCommerce Store Config ----
WOOCOMMERCE_STORES = [
    {
        'name': 'BengalPC',
        'slug': 'bengalpc',
        'website': 'https://bengalpcbd.com',
        'listing_url': 'https://bengalpcbd.com/product-category/components/graphics-card/',
        'product_selector': '.product-grid-item',
        'name_selector': 'h3 a',
        'link_selector': 'h3 a',
        'image_selector': 'img',
        'price_selector': '.price',
        'stock_selector': '.stock',
    },
]


async def scrape_pcbstore(session, limit_pages=None):
    """Scrape PCBStore.com.bd - custom site structure."""
    config = {
        'name': 'PCBStore',
        'slug': 'pcbstore',
        'website': 'https://www.pcbstore.com.bd',
        'listing_url': 'https://www.pcbstore.com.bd/product/category/graphics-card',
    }
    seller = get_or_create_seller(session, config['name'], config['slug'], config['website'])
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        url = config['listing_url']
        page_num = 0
        all_count = 0

        while url:
            page_num += 1
            if limit_pages and page_num > limit_pages:
                break

            print(f"  [{config['slug']}] Page {page_num}...", end=" ", flush=True)
            products, next_url = await _scrape_pcbstore_page(client, url)

            if not products:
                print("No products found, stopping")
                break

            for pd in products:
                save_product(session, seller, pd)
                all_count += 1

            session.commit()
            print(f"{len(products)} products (total: {all_count})")
            url = next_url

        print(f"  [{config['slug']}] Done! {all_count} total records.")
        return all_count


async def _scrape_pcbstore_page(client, url):
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return [], None

    soup = BeautifulSoup(resp.text, 'lxml')
    products = []

    for item in soup.select('div.group.relative.z-0'):
        try:
            # Get name from the product link
            a = item.find('a', href=lambda h: h and '/product/' in h)
            if not a:
                continue

            name = a.get_text(strip=True) or ''
            if not name or len(name) < 5:
                img = a.find('img')
                if img:
                    name = img.get('alt', '')
            if not name or len(name) < 5:
                continue

            href = a.get('href', '')
            product_url = href if href.startswith('http') else urljoin('https://www.pcbstore.com.bd', href)

            img_el = item.find('img')
            img_url = ''
            if img_el:
                img_url = img_el.get('src', '')

            current_price = 0.0
            original_price = None
            # Current price: span with theme price class
            curr_span = item.select_one('span.text-theme.font-bold')
            if curr_span:
                nums = parse_price(curr_span.get_text(strip=True))
                if nums: current_price = nums[0]
            # Original price: span with line-through
            orig_span = item.select_one('span.line-through')
            if orig_span:
                nums = parse_price(orig_span.get_text(strip=True))
                if nums: original_price = nums[0]
            # Fallback: parse all text
            if not current_price:
                nums = parse_price(item.get_text(strip=True))
                if nums:
                    if len(nums) >= 2:
                        original_price = nums[0]
                        current_price = nums[1]
                    else:
                        current_price = nums[0]

            in_stock = True
            txt = item.get_text(strip=True).lower()
            if 'out of stock' in txt and 'in stock' not in txt:
                in_stock = False

            products.append({
                'name': name,
                'url': product_url,
                'image_url': img_url,
                'price': current_price,
                'original_price': original_price if original_price and original_price != current_price else None,
                'in_stock': in_stock,
            })
        except Exception:
            continue

    next_url = None
    # PCBStore pagination: look for "Next" or ">" links
    for a in soup.find_all('a', href=True):
        txt = a.get_text(strip=True)
        if txt.lower() in ['next', 'next »', '›', '»', 'next page']:
            next_url = a['href']
            if not next_url.startswith('http'):
                next_url = urljoin('https://www.pcbstore.com.bd', next_url)
            break

    return products, next_url


async def run_all(limit_pages_per_store=None):
    """Run all scrapers sequentially."""
    session, engine = init_db(f"sqlite:///{DB_PATH}")
    total_products = 0

    try:
        # 1. TechLand BD (existing scraper)
        print("\n=== TechLand BD ===")
        tc = await scrape_techlandbd.main(limit_pages=limit_pages_per_store, session=session)
        total_products += (tc or 0)

        # 2. OpenCart stores
        for store_cfg in OPENCART_STORES:
            print(f"\n=== {store_cfg['name']} ===")
            scraper = OpenCartScraper(session, store_cfg)
            count = await scraper.scrape(limit_pages=limit_pages_per_store)
            total_products += count

        # 3. WooCommerce stores
        for store_cfg in WOOCOMMERCE_STORES:
            print(f"\n=== {store_cfg['name']} (WooCommerce) ===")
            count = await scrape_woocommerce(session, store_cfg, limit_pages=limit_pages_per_store)
            total_products += count

        # 4. PCBStore
        print(f"\n=== PCBStore ===")
        count = await scrape_pcbstore(session, limit_pages=limit_pages_per_store)
        total_products += count

    finally:
        session.close()

    print(f"\n{'='*50}")
    print(f"All scrapers completed! Total records: {total_products}")
    print(f"{'='*50}")
    return total_products


if __name__ == "__main__":
    asyncio.run(run_all())
