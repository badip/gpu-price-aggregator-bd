# GPU Price Aggregator — Bangladesh

A [PCPartPicker](https://pcpartpicker.com)-style price comparison tool for graphics cards in Bangladesh. Scrapes real-time prices from 8 local stores and displays them in a unified, searchable dashboard.

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![SQLite](https://img.shields.io/badge/SQLite-3-blue)

## Features

- **8 stores scraped** — TechLand BD, StarTech, PotakaIT, UltraTech, UCC, Creatus, BengalPC, PCBStore
- **2,000+ unique GPU models** — grouped by exact product name across sellers
- **Real-time prices** — BDT prices with original/discounted pricing
- **Price history** — track price changes per seller
- **Smart filters** — brand, chipset, memory, seller, price range, in-stock only
- **Multi-seller comparison** — see all prices for the same GPU model side-by-side
- **Modern UI** — fluid animations, glassmorphism design, mobile responsive

## Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn httpx beautifulsoup4 lxml sqlalchemy jinja2
```

### 2. Start the server

```bash
cd gpu_prices
python main.py
```

Open **http://localhost:8000** in your browser.

### 3. Scrape fresh data

```bash
cd gpu_prices/scrapers
python run_all.py
```

Scrapes all 8 stores. Takes 2–5 minutes depending on connection speed.

### 4. Or use the existing database

The repository ships with a pre-scraped `gpu_prices.db` containing 2,000+ GPU models from all 8 stores.

## Project Structure

```
gpu-prices/
├── gpu_prices/
│   ├── main.py                 # FastAPI server + API endpoints
│   ├── models.py               # SQLAlchemy ORM (Seller, Product, Price, GpuModel)
│   ├── migrate_v2.py           # Schema migration script
│   ├── test_app2.py            # Integration tests
│   ├── gpu_prices.db           # SQLite database (pre-scraped)
│   ├── static/
│   │   └── style.css           # Modern animated stylesheet
│   ├── templates/
│   │   ├── listing.html        # Main GPU listing page
│   │   ├── model.html          # GPU model detail + comparison
│   │   └── product.html        # Seller-specific price history
│   └── scrapers/
│       ├── run_all.py          # Unified scraper runner
│       ├── base_opencart.py    # Generic OpenCart scraper class
│       ├── utils.py            # Shared parsing + database utilities
│       ├── scrape_techlandbd.py # TechLand BD scraper
│       └── ...
├── .gitignore
├── CLAUDE.md
└── README.md
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main listing page |
| `GET /model/{slug}` | GPU model detail with all seller prices |
| `GET /product/{id}` | Seller-specific product with price history |
| `GET /api/products` | JSON listing (supports filters, sort, pagination) |
| `GET /api/models/{slug}` | JSON model detail |
| `GET /api/products/{id}` | JSON product detail |
| `GET /api/filters` | Available filter options |

### API Query Parameters (`/api/products`)

| Param | Type | Example |
|-------|------|---------|
| `search` | string | `?search=RTX+5070` |
| `brand` | string | `?brand=Asus` |
| `chipset` | string | `?chipset=RTX+5080` |
| `seller` | string | `?seller=startech` |
| `memory` | string | `?memory=16+GB` |
| `memory_type` | string | `?memory_type=GDDR7` |
| `min_price` | float | `?min_price=10000` |
| `max_price` | float | `?max_price=50000` |
| `in_stock` | bool | `?in_stock=1` |
| `sort` | string | `?sort=price` |
| `order` | string | `?order=desc` |
| `page` | int | `?page=2` |
| `per_page` | int | `?per_page=50` |

## Database Schema

```
sellers (id, name, slug, website)
    └── products (id, model_id, seller_id, name, product_url, image_url,
    |              brand, chipset, memory, memory_type, in_stock, ...)
    |       └── prices (id, product_id, price, original_price, recorded_at)
    │
    └── gpu_models (id, name, slug, model_key, brand, chipset,
                     memory, memory_type, specs...)
```

Products are grouped by **normalized full product name** (`model_key`). Same SKU across multiple stores shares one `GpuModel` record.

## Supported Stores

| Store | Platform | Product Count |
|-------|----------|--------------|
| [TechLand BD](https://www.techlandbd.com) | Custom | 625 |
| [StarTech](https://www.startech.com.bd) | Custom theme | 568 |
| [PotakaIT](https://www.potakait.com) | OpenCart | 308 |
| [UltraTech](https://www.ultratech.com.bd) | OpenCart (Journal3) | 593 |
| [UCC](https://www.ucc.com.bd) | OpenCart (Journal3) | 258 |
| [Creatus](https://www.creatus.com.bd) | OpenCart (Journal3) | 849 |
| [BengalPC](https://www.bengalpcbd.com) | WooCommerce (Woodmart) | 85 |
| [PCBStore](https://www.pcbstore.com.bd) | Next.js (Tailwind) | 12 |

## Running Tests

```bash
cd gpu_prices
python test_app2.py
```

## Adding a New Store

1. Analyze the store's listing page HTML structure
2. Add a config to `scrapers/run_all.py` (OpenCart stores use `base_opencart.py`)
3. For non-OpenCart stores, write a scraper function following existing patterns
4. Run `python run_all.py` to scrape

## Roadmap

- [ ] Ryans.com (Cloudflare-bypass needed)
- [ ] Samanta Computer (React SPA, needs headless browser)
- [ ] Daily cron scraping
- [ ] Price drop alerts
- [ ] More categories (CPU, motherboard, PSU)

## License

MIT
