import re, sys, os
from urllib.parse import urljoin
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

def normalize_name(name):
    n = name.lower().strip()
    n = re.sub(r'\b(graphic\s*card|graphics\s*card|vga\s*card|display\s*card|gpu)\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = re.sub(r'(\d+)\s*(gb|gddr\d)', r'\1\2', n)
    return n

def generate_model_key(name, info=None):
    return normalize_name(name)

def slugify(text):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return s[:200]

def parse_price(text):
    cleaned = text.replace('\u09f3', '').replace('TK', '').strip()
    # Remove thousands commas, keep decimal dot
    cleaned = re.sub(r'(?<=\d),(?=\d{3})', '', cleaned)
    nums = re.findall(r'(\d+(?:\.\d+)?)', cleaned)
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
        'galax': 'Galax', 'gainward': 'Gainward', 'evga': 'EVGA',
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

def get_or_create_seller(session, name, slug, website):
    from models import Seller
    seller = session.query(Seller).filter_by(slug=slug).first()
    if not seller:
        seller = Seller(name=name, slug=slug, website=website)
        session.add(seller)
        session.commit()
    return seller

def save_product(session, seller, pd):
    from models import Product, Price, GpuModel
    existing = session.query(Product).filter_by(seller_id=seller.id, product_url=pd['url']).first()
    info = extract_gpu_info(pd['name'])

    if not existing:
        # Find or create GpuModel (grouped by normalized product name)
        model_key = generate_model_key(pd['name'], info)
        model = session.query(GpuModel).filter_by(model_key=model_key).first()
        if not model:
            display_name = pd['name'].strip()
            model = GpuModel(
                name=display_name,
                slug=model_key.replace(' ', '-')[:500],
                model_key=model_key,
                brand=info.get('brand'),
                chipset=info.get('chipset'),
                memory=info.get('memory'),
                memory_type=info.get('memory_type'),
                color=info.get('color'),
            )
            session.add(model)
            session.flush()

        product = Product(
            model_id=model.id,
            seller_id=seller.id,
            name=pd['name'],
            product_url=pd['url'],
            image_url=pd.get('image_url', ''),
            in_stock=pd.get('in_stock', True),
            brand=info.get('brand'),
            chipset=info.get('chipset'),
            memory=info.get('memory'),
            memory_type=info.get('memory_type'),
            color=info.get('color'),
        )
        session.add(product)
        session.flush()
    else:
        product = existing
        product.in_stock = pd.get('in_stock', True)

    price_rec = Price(
        product_id=product.id,
        price=pd['price'],
        original_price=pd.get('original_price'),
        currency='BDT',
    )
    session.add(price_rec)
    return product
