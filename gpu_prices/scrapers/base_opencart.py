import re, sys, os
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from utils import save_product, get_or_create_seller, parse_price

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

class OpenCartScraper:
    def __init__(self, session, seller_config):
        self.session = session
        self.config = seller_config
        self.seller = get_or_create_seller(
            session,
            seller_config['name'],
            seller_config['slug'],
            seller_config['website'],
        )

    async def scrape(self, limit_pages=None):
        config = self.config
        async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
            url = config['listing_url']
            page_num = 0
            all_count = 0

            while url:
                page_num += 1
                if limit_pages and page_num > limit_pages:
                    break

                print(f"  [{config['slug']}] Page {page_num}...", end=" ", flush=True)
                products, next_url = await self._scrape_page(client, url)

                if not products:
                    print("No products found, stopping")
                    break

                for pd in products:
                    save_product(self.session, self.seller, pd)
                    all_count += 1

                self.session.commit()
                print(f"{len(products)} products (total: {all_count})")
                url = next_url

            print(f"  [{config['slug']}] Done! {all_count} total records.")
            return all_count

    async def _scrape_page(self, client, url):
        config = self.config
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return [], None

        soup = BeautifulSoup(resp.text, 'lxml')
        products = []

        containers = soup.select(config['product_selector'])
        if not containers:
            return [], None

        for item in containers:
            prod = self._extract_product(item, config)
            if prod:
                products.append(prod)

        next_url = self._find_next_page(soup, config, url)

        return products, next_url

    def _extract_product(self, item, config):
        try:
            name_el = item.select_one(config['name_selector']) if config.get('name_selector') else item.find(['h2', 'h3', 'h4'])
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            if not name or len(name) < 5:
                return None

            link_el = item.select_one(config['link_selector']) if config.get('link_selector') else name_el.find('a')
            if not link_el:
                link_el = item.find('a', href=True)
            href = ''
            product_url = ''
            if link_el:
                href = link_el.get('href', '')
                product_url = href if href.startswith('http') else urljoin(config['base_url'], href)

            img_el = item.select_one(config['image_selector']) if config.get('image_selector') else item.find('img')
            img_url = ''
            if img_el:
                img_url = img_el.get('data-src') or img_el.get('src') or ''

            current_price = 0.0
            original_price = None
            price_el = item.select_one(config['price_selector']) if config.get('price_selector') else None
            if price_el:
                # Check for .price-new / .price-old (Journal3)
                price_new = price_el.select_one('.price-new')
                price_old = price_el.select_one('.price-old')
                if price_new:
                    nums = parse_price(price_new.get_text(strip=True))
                    if nums: current_price = nums[0]
                if price_old:
                    nums = parse_price(price_old.get_text(strip=True))
                    if nums: original_price = nums[0]
                if not price_new:
                    full_text = price_el.get_text(strip=True)
                    nums = parse_price(full_text)
                    if len(nums) >= 2:
                        current_price = nums[0]
                        original_price = nums[1]
                    elif len(nums) == 1:
                        current_price = nums[0]

            in_stock = True
            if config.get('stock_selector'):
                stock_el = item.select_one(config['stock_selector'])
                if stock_el:
                    txt = stock_el.get_text(strip=True).lower()
                    if 'out of stock' in txt or 'outofstock' in txt:
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
        except Exception as e:
            return None

    def _find_next_page(self, soup, config, current_url):
        pagination = soup.select_one(config.get('pagination_selector', 'ul.pagination'))
        if not pagination:
            return None

        next_link = pagination.find('a', string=re.compile(r'Next|next|›|»|>'))
        if next_link and next_link.get('href'):
            href = next_link['href']
            return href if href.startswith('http') else urljoin(config['base_url'], href)

        current_page = None
        m_page = re.search(r'[?&]page=(\d+)', current_url)
        if m_page:
            current_page = int(m_page.group(1))
        else:
            current_page = 1

        links = pagination.find_all('a')
        max_page = 0
        for link in links:
            m = re.search(r'[?&]page=(\d+)', link.get('href', ''))
            if m:
                pn = int(m.group(1))
                if pn > max_page:
                    max_page = pn

        if max_page > current_page:
            next_page_url = re.sub(r'[?&]page=\d+', '', current_url)
            sep = '&' if '?' in next_page_url else '?'
            next_page = current_page + 1
            if '?' in current_url:
                if 'page=' in current_url:
                    return re.sub(r'page=\d+', f'page={next_page}', current_url)
                else:
                    return f"{current_url}&page={next_page}"
            else:
                return f"{current_url}?page={next_page}"

        return None
