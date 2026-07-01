import os, re
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker
from models import Base, Seller, Product, Price, GpuModel
from jinja2 import Environment, FileSystemLoader

DB_PATH = os.path.join(os.path.dirname(__file__), "gpu_prices.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)

app = FastAPI(title="GPU Price Aggregator - Bangladesh")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

class _Env(Environment):
    def _load_template(self, name, globals):
        if self.loader is None:
            raise TypeError("no loader for this environment specified")
        cache_key = name
        if self.cache is not None:
            template = self.cache.get(cache_key)
            if template is not None:
                return template
        template = self.loader.load(self, name, self.make_globals(globals))
        if self.cache is not None:
            self.cache[cache_key] = template
        return template

_jinja = _Env(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")))
_jinja.globals["request"] = lambda: None

def get_session():
    return Session()

@app.get("/api/filters")
def get_filters():
    session = get_session()
    try:
        brands = [r[0] for r in session.query(GpuModel.brand).distinct().filter(GpuModel.brand.isnot(None)).order_by(GpuModel.brand).all()]
        chipsets = [r[0] for r in session.query(GpuModel.chipset).distinct().filter(GpuModel.chipset.isnot(None)).order_by(GpuModel.chipset).all()]
        memories = [r[0] for r in session.query(Product.memory).distinct().filter(Product.memory.isnot(None)).order_by(Product.memory).all()]
        memory_types = [r[0] for r in session.query(Product.memory_type).distinct().filter(Product.memory_type.isnot(None)).order_by(Product.memory_type).all()]
        sellers = [{"name": r[0], "slug": r[1]} for r in session.query(Seller.name, Seller.slug).order_by(Seller.name).all()]
        return {"brands": brands, "chipsets": chipsets, "memories": memories, "memory_types": memory_types, "sellers": sellers}
    finally:
        session.close()

@app.get("/api/products")
def list_products(
    search: str = "",
    brand: str = "",
    chipset: str = "",
    memory: str = "",
    memory_type: str = "",
    seller: str = "",
    min_price: float = 0,
    max_price: float = 0,
    in_stock: bool = False,
    sort: str = "name",
    order: str = "asc",
    page: int = 1,
    per_page: int = 50,
):
    session = get_session()
    try:
        lp_max = session.query(Price.product_id, func.max(Price.id).label('max_id')).group_by(Price.product_id).subquery()
        lp = session.query(Price).filter(Price.id.in_(session.query(lp_max.c.max_id))).subquery()

        query = session.query(Product, lp.c.price, lp.c.original_price, Seller.name, Seller.slug).join(
            lp, Product.id == lp.c.product_id
        ).join(Seller, Product.seller_id == Seller.id)

        if search:
            like = f"%{search}%"
            query = query.filter(
                (Product.name.ilike(like)) | (Product.brand.ilike(like)) | (Product.chipset.ilike(like))
            )
        if brand:
            query = query.filter(Product.brand.ilike(f"%{brand}%"))
        if chipset:
            query = query.filter(Product.chipset.ilike(f"%{chipset}%"))
        if memory:
            query = query.filter(Product.memory == memory)
        if memory_type:
            query = query.filter(Product.memory_type == memory_type)
        if seller:
            query = query.filter(Seller.slug == seller)
        if min_price > 0:
            query = query.filter(lp.c.price >= min_price)
        if max_price > 0:
            query = query.filter(lp.c.price <= max_price)
        if in_stock:
            query = query.filter(Product.in_stock == True)

        results = query.all()

        groups = defaultdict(lambda: {
            "model_id": 0, "name": "", "slug": "", "brand": "", "chipset": "",
            "memory": "", "memory_type": "", "image_url": "",
            "sellers": [], "min_price": float('inf'), "max_price": 0, "in_stock": False,
        })

        for prod, price, orig_price, seller_name, seller_slug in results:
            model = prod.model
            if not model:
                continue
            key = model.id
            g = groups[key]
            g["model_id"] = model.id
            g["name"] = model.name
            g["slug"] = model.slug
            g["brand"] = model.brand or prod.brand or ""
            g["chipset"] = model.chipset or prod.chipset or ""
            g["memory"] = model.memory or prod.memory or ""
            g["memory_type"] = model.memory_type or prod.memory_type or ""
            g["image_url"] = model.image_url or prod.image_url or ""

            g["sellers"].append({
                "product_id": prod.id,
                "name": prod.name,
                "seller": seller_name,
                "seller_slug": seller_slug,
                "price": price,
                "original_price": orig_price,
                "in_stock": prod.in_stock,
                "product_url": prod.product_url,
            })
            if price < g["min_price"]:
                g["min_price"] = price
            if price > g["max_price"]:
                g["max_price"] = price
            if prod.in_stock:
                g["in_stock"] = True

        product_list = list(groups.values())
        for g in product_list:
            if g["min_price"] == float('inf'):
                g["min_price"] = 0
            g["sellers"].sort(key=lambda s: s["price"])

        reverse = order == "desc"
        if sort == "price":
            product_list.sort(key=lambda g: g["min_price"], reverse=reverse)
        elif sort == "brand":
            product_list.sort(key=lambda g: g["brand"] or "", reverse=reverse)
        elif sort == "chipset":
            product_list.sort(key=lambda g: g["chipset"] or "", reverse=reverse)
        elif sort == "seller_count":
            product_list.sort(key=lambda g: len(g["sellers"]), reverse=reverse)
        else:
            product_list.sort(key=lambda g: g["name"] or "", reverse=reverse)

        count = len(product_list)
        total_pages = max(1, (count + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        product_page = product_list[start:start + per_page]

        filters_data = get_filters_from_db(session)
        return {
            "products": product_page,
            "total": count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "filters": filters_data,
        }
    finally:
        session.close()

def get_filters_from_db(session):
    brands = [r[0] for r in session.query(GpuModel.brand).distinct().filter(GpuModel.brand.isnot(None)).order_by(GpuModel.brand).all()]
    chipsets = [r[0] for r in session.query(GpuModel.chipset).distinct().filter(GpuModel.chipset.isnot(None)).order_by(GpuModel.chipset).all()]
    memories = [r[0] for r in session.query(Product.memory).distinct().filter(Product.memory.isnot(None)).order_by(Product.memory).all()]
    memory_types = [r[0] for r in session.query(Product.memory_type).distinct().filter(Product.memory_type.isnot(None)).order_by(Product.memory_type).all()]
    sellers = [{"name": r[0], "slug": r[1]} for r in session.query(Seller.name, Seller.slug).order_by(Seller.name).all()]
    return {"brands": brands, "chipsets": chipsets, "memories": memories, "memory_types": memory_types, "sellers": sellers}

@app.get("/api/models/{model_slug}")
def model_detail(model_slug: str):
    session = get_session()
    try:
        model = session.query(GpuModel).filter(GpuModel.slug == model_slug).first()
        if not model:
            return JSONResponse(status_code=404, content={"error": "Model not found"})

        products = session.query(Product).filter(Product.model_id == model.id).all()
        seller_list = []
        for prod in products:
            lp = session.query(Price).filter(Price.product_id == prod.id).order_by(Price.recorded_at.desc()).first()
            price_history = session.query(Price).filter(Price.product_id == prod.id).order_by(Price.recorded_at.desc()).limit(50).all()
            seller_list.append({
                "product_id": prod.id,
                "name": prod.name,
                "product_url": prod.product_url,
                "image_url": prod.image_url,
                "in_stock": prod.in_stock,
                "seller": prod.seller.name if prod.seller else "",
                "seller_slug": prod.seller.slug if prod.seller else "",
                "current_price": lp.price if lp else None,
                "original_price": lp.original_price if lp else None,
                "price_history": [{
                    "price": p.price,
                    "original_price": p.original_price,
                    "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
                } for p in price_history],
            })

        seller_list.sort(key=lambda s: (s["current_price"] or 0) if s["current_price"] else float('inf'))

        return {
            "model_id": model.id,
            "name": model.name,
            "slug": model.slug,
            "brand": model.brand,
            "chipset": model.chipset,
            "memory": model.memory,
            "memory_type": model.memory_type,
            "clock_speed": model.clock_speed,
            "boost_clock": model.boost_clock,
            "color": model.color,
            "cooling": model.cooling,
            "tdp": model.tdp,
            "interface": model.interface,
            "length_mm": model.length_mm,
            "power_connectors": model.power_connectors,
            "image_url": model.image_url,
            "sellers": seller_list,
        }
    finally:
        session.close()

@app.get("/api/products/{product_id}")
def product_detail(product_id: int):
    session = get_session()
    try:
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return JSONResponse(status_code=404, content={"error": "Product not found"})

        prices = session.query(Price).filter(Price.product_id == product_id).order_by(Price.recorded_at.desc()).limit(50).all()
        price_history = [{
            "price": p.price,
            "original_price": p.original_price,
            "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
        } for p in prices]
        current_price = prices[0] if prices else None
        model_slug = product.model.slug if product.model else ""

        return {
            "id": product.id,
            "model_id": product.model_id,
            "model_slug": model_slug,
            "name": product.name,
            "product_url": product.product_url,
            "image_url": product.image_url,
            "brand": product.brand,
            "chipset": product.chipset,
            "memory": product.memory,
            "memory_type": product.memory_type,
            "color": product.color,
            "clock_speed": product.clock_speed,
            "boost_clock": product.boost_clock,
            "tdp": product.tdp,
            "interface": product.interface,
            "length_mm": product.length_mm,
            "power_connectors": product.power_connectors,
            "cooling": product.cooling,
            "in_stock": product.in_stock,
            "seller": product.seller.name if product.seller else "",
            "seller_slug": product.seller.slug if product.seller else "",
            "seller_website": product.seller.website if product.seller else "",
            "current_price": current_price.price if current_price else None,
            "original_price": current_price.original_price if current_price else None,
            "price_history": price_history,
        }
    finally:
        session.close()

@app.get("/", response_class=HTMLResponse)
def listing_page(request: Request):
    t = _jinja.get_template("listing.html")
    return HTMLResponse(t.render(request=request))

@app.get("/model/{model_slug}", response_class=HTMLResponse)
def model_page(request: Request, model_slug: str):
    t = _jinja.get_template("model.html")
    return HTMLResponse(t.render(request=request, model_slug=model_slug))

@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: int):
    t = _jinja.get_template("product.html")
    return HTMLResponse(t.render(request=request, product_id=product_id))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
