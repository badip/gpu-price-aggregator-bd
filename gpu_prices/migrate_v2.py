"""Migration: add GpuModel table and backfill model_id for existing products."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Base, Seller, Product, Price, GpuModel
from scrapers.utils import extract_gpu_info, generate_model_key, slugify, normalize_name
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_prices.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# Add model_id column if not exists (SQLite requires raw ALTER TABLE)
with engine.connect() as conn:
    # Check if column exists
    cols = conn.execute(text("PRAGMA table_info(products)")).fetchall()
    col_names = [c[1] for c in cols]
    if 'model_id' not in col_names:
        conn.execute(text("ALTER TABLE products ADD COLUMN model_id INTEGER REFERENCES gpu_models(id)"))
        conn.commit()
        print("Added model_id column to products table.")

# Create new tables (GpuModel) if not exist
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

try:
    # Check if migration already done
    existing = session.query(GpuModel).count()
    if existing > 0:
        print(f"Migration appears already done: {existing} models exist. Removing old models to re-migrate...")
        session.query(GpuModel).delete()
        session.execute(text("UPDATE products SET model_id = NULL"))
        session.commit()

    # For each product with no model_id, create or link to a GpuModel
    products = session.query(Product).filter(Product.model_id.is_(None)).all()
    print(f"Processing {len(products)} unlinked products...")

    model_cache = {}
    linked = 0

    for prod in products:
        model_key = generate_model_key(prod.name)

        if model_key in model_cache:
            prod.model_id = model_cache[model_key].id
        else:
            model = session.query(GpuModel).filter_by(model_key=model_key).first()
            if not model:
                info = extract_gpu_info(prod.name)
                model = GpuModel(
                    name=prod.name,
                    slug=model_key.replace(' ', '-')[:200],
                    model_key=model_key,
                    brand=info.get('brand'),
                    chipset=info.get('chipset'),
                    memory=info.get('memory'),
                    memory_type=info.get('memory_type'),
                    color=info.get('color'),
                    image_url=prod.image_url,
                )
                session.add(model)
                session.flush()
            model_cache[model_key] = model
            prod.model_id = model.id
        linked += 1

        if linked % 200 == 0:
            session.commit()
            print(f"  Linked {linked}/{len(products)}...")

    session.commit()
    total = session.query(GpuModel).count()
    print(f"Done! Created {total} GpuModels linking {linked} products.")

    # Ensure slug matches model_key (unique) to avoid slug collisions
    all_models = session.query(GpuModel).all()
    for m in all_models:
        m.slug = m.model_key.replace(' ', '-')[:200]
    session.commit()
    print(f"Slugs synced to model_keys.")

    # Update model image_url from best product
    for m in all_models:
        best = session.query(Product).filter(
            Product.model_id == m.id,
            Product.image_url != '',
            Product.image_url.isnot(None),
        ).order_by(Product.in_stock.desc()).first()
        if best:
            m.image_url = best.image_url
    session.commit()
    print("Model images updated.")

finally:
    session.close()

    # Print stats
    s2 = Session()
    total_models = s2.query(GpuModel).count()
    linked_count = s2.query(Product).filter(Product.model_id.isnot(None)).count()
    total_products = s2.query(Product).count()
    print(f"\nFinal stats: {total_models} models, {linked_count}/{total_products} products linked.")
    s2.close()
