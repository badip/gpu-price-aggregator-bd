import sys, os, re, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from models import init_db
from utils import save_product, get_or_create_seller

BASE_URL = "https://www.techlandbd.com"
GPU_LISTING_URL = "https://www.techlandbd.com/pc-components/graphics-card"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def parse_price(text):
    nums = re.findall(r'(\d[\d,]*)', text.replace(',', ''))
    return [float(n) for n in nums if n]

def extract_gpu_info(name):
    info = {}
    nl = name.lower()

    brand_map = {
        'asus': 'Asus', 'msi': 'MSI', 'gigabyte': 'Gigabyte', 'zotac': 'Zotac',
        'pny': 'PNY', 'inno3d': 'INNO3D', 'colorful': 'Colorful', 'sapphire': 'Sapphire',
        'powercolor': 'PowerColor', 'xfx': 'XFX', 'asrock': 'ASRock', 'manli': 'Manli',
        'maxsun': 'MAXSUN', 'yeston': 'Yeston', 'ocpc': 'OCPC', 'afox': 'AFOX',
        'arktek': 'ARKTEK', 'sparkle': 'Sparkle', 'unika': 'Unika', 'ninja': 'Ninja',
        'gunnir': 'Gunnir', 'peladn': 'PELADN', 'onix': 'ONIX', 'biostar': 'Biostar',
        'intel': 'Intel', 'nvidia': 'NVIDIA', 'amd': 'AMD', 'leadtek': 'Leadtek',
    }
    for key, val in brand_map.items():
        if key in nl:
            info['brand'] = val
            break

    chip_patterns = [
        r'RTX\s*5090', r'RTX\s*5080', r'RTX\s*5070\s*Ti\s*Super', r'RTX\s*5070\s*Ti', r'RTX\s*5070',
        r'RTX\s*5060\s*Ti', r'RTX\s*5060', r'RTX\s*5050',
        r'RTX\s*4090', r'RTX\s*4080\s*Super', r'RTX\s*4080',
        r'RTX\s*4070\s*Ti\s*Super', r'RTX\s*4070\s*Ti', r'RTX\s*4070\s*Super', r'RTX\s*4070',
        r'RTX\s*4060\s*Ti', r'RTX\s*4060', r'RTX\s*4050',
        r'RTX\s*3090\s*Ti', r'RTX\s*3090', r'RTX\s*3080\s*Ti', r'RTX\s*3080',
        r'RTX\s*3070\s*Ti', r'RTX\s*3070', r'RTX\s*3060\s*Ti', r'RTX\s*3060', r'RTX\s*3050',
        r'RTX\s*2080\s*Ti', r'RTX\s*2080\s*Super', r'RTX\s*2080',
        r'RTX\s*2070\s*Super', r'RTX\s*2070', r'RTX\s*2060\s*Super', r'RTX\s*2060',
        r'GTX\s*1660\s*Ti', r'GTX\s*1660\s*Super', r'GTX\s*1660',
        r'GTX\s*1650\s*Super', r'GTX\s*1650', r'GTX\s*1630',
        r'GTX\s*1080\s*Ti', r'GTX\s*1080', r'GTX\s*1070\s*Ti', r'GTX\s*1070', r'GTX\s*1060',
        r'GTX\s*1050\s*Ti', r'GTX\s*1050',
        r'GT\s*1030', r'GT\s*730', r'GT\s*710',
        r'RX\s*9070\s*XT', r'RX\s*9070', r'RX\s*9060\s*XT', r'RX\s*9060',
        r'RX\s*7900\s*XTX', r'RX\s*7900\s*XT', r'RX\s*7900\s*GRE', r'RX\s*7900',
        r'RX\s*7800\s*XT', r'RX\s*7700\s*XT', r'RX\s*7600\s*XT', r'RX\s*7600',
        r'RX\s*6750\s*XT', r'RX\s*6700\s*XT', r'RX\s*6650\s*XT', r'RX\s*6600\s*XT', r'RX\s*6600',
        r'RX\s*6500\s*XT', r'RX\s*6500', r'RX\s*6400',
        r'RX\s*580', r'RX\s*570', r'RX\s*560', r'RX\s*550',
        r'Arc\s*B580', r'Arc\s*B570', r'Arc\s*A770', r'Arc\s*A750', r'Arc\s*A580',
        r'Arc\s*A380', r'Arc\s*A310',
    ]
    for pat in chip_patterns:
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            info['chipset'] = m.group(0).upper().replace(' ', ' ')
            break

    mm = re.search(r'(\d+)\s*GB', name)
    if mm:
        info['memory'] = mm.group(1) + ' GB'

    for mt in ['GDDR7', 'GDDR6X', 'GDDR6', 'GDDR5X', 'GDDR5', 'DDR6', 'DDR5', 'DDR4', 'DDR3']:
        if mt.lower() in nl:
            info['memory_type'] = mt
            break

    if 'white' in nl:
        info['color'] = 'White'
    elif 'black' in nl:
        info['color'] = 'Black'

    return info

def extract_product_from_article(article):
    try:
        name_el = article.find(['h2', 'h3', 'h4'])
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name or len(name) < 10:
            return None

        link_el = name_el.find('a') if name_el else None
        if not link_el:
            link_el = article.find('a', href=lambda h: h and h.startswith('/') and 'graphics' not in h)
        if not link_el:
            return None
        href = link_el.get('href', '')
        product_url = href if href.startswith('http') else urljoin(BASE_URL, href)

        img_el = article.find('img')
        img_url = img_el.get('data-src') or img_el.get('src') or '' if img_el else ''

        price_span = article.find('span', class_=lambda c: c and 'font-bold' in (c if c else '') and 'text-gray-800' in (c if c else ''))
        current_price = 0
        if price_span:
            nums = parse_price(price_span.get_text(strip=True))
            if nums:
                current_price = nums[0]

        original_price = None
        line_through = article.find('span', class_=lambda c: c and 'line-through' in (c if c else ''))
        if line_through:
            nums = parse_price(line_through.get_text(strip=True))
            if nums:
                original_price = nums[0]

        stock_p = article.find('p', class_=lambda c: c and 'text-green' in (c if c else ''))
        in_stock = current_price > 0
        if stock_p and 'out of stock' in stock_p.get_text(strip=True).lower():
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

async def scrape_page(client, url):
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')

    grid = soup.select_one('div.product-grid-optimized')
    if not grid:
        return [], None

    products = []
    articles = grid.find_all('article')
    total_pages = 0
    current_page = 0

    for article in articles:
        prod = extract_product_from_article(article)
        if prod:
            products.append(prod)

    pagination_ul = soup.find('ul', class_=lambda c: c and 'inline-flex' in c if c else False)
    next_page = None
    if pagination_ul:
        buttons = pagination_ul.find_all('button')
        page_numbers = []
        for btn in buttons:
            click = btn.get('wire:click', '')
            m = re.search(r'gotoPage\((\d+)\)', click)
            if m:
                pn = int(m.group(1))
                page_numbers.append(pn)
                if btn.get('aria-current') is not None:
                    current_page = pn
        if current_page > 0 and page_numbers:
            total_pages = max(page_numbers)
            if current_page < total_pages:
                next_page = f"{GPU_LISTING_URL}?page={current_page + 1}"

    return products, next_page

async def main(limit_pages=None, session=None):
    own_session = False
    if session is None:
        session, engine = init_db()
        own_session = True

    seller = get_or_create_seller(session, 'TechLand BD', 'techlandbd', 'https://www.techlandbd.com')

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        url = GPU_LISTING_URL
        page_num = 0
        all_count = 0

        while url:
            page_num += 1
            if limit_pages and page_num > limit_pages:
                break

            print(f"Page {page_num}...", end=" ", flush=True)
            products, next_url = await scrape_page(client, url)

            if not products:
                print("No products found, stopping")
                break

            for pd in products:
                save_product(session, seller, pd)
                all_count += 1

            session.commit()
            print(f"{len(products)} products (total records: {all_count})")
            url = next_url

    if own_session:
        session.close()
        print(f"\nDone! {all_count} price records saved across {page_num} pages.")
    else:
        print(f"  [techlandbd] Done! {all_count} total records.")

if __name__ == "__main__":
    asyncio.run(main(limit_pages=25))
