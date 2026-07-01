import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone

Base = declarative_base()

class Seller(Base):
    __tablename__ = "sellers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    website = Column(String(500))
    logo_url = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="seller")

class GpuChipset(Base):
    __tablename__ = "gpu_chipsets"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    manufacturer = Column(String(50))

class GpuModel(Base):
    __tablename__ = "gpu_models"
    id = Column(Integer, primary_key=True)
    name = Column(String(500))
    slug = Column(String(500), unique=True)
    model_key = Column(String(200), unique=True, index=True)
    brand = Column(String(100))
    chipset = Column(String(200))
    memory = Column(String(50))
    memory_type = Column(String(50))
    clock_speed = Column(String(100))
    boost_clock = Column(String(100))
    color = Column(String(100))
    cooling = Column(String(100))
    tdp = Column(String(50))
    interface = Column(String(100))
    length_mm = Column(String(50))
    power_connectors = Column(String(100))
    image_url = Column(String(1000))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="model")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey("gpu_models.id"), index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False)
    name = Column(String(500), nullable=False)
    slug = Column(String(500))
    sku = Column(String(200))
    product_url = Column(String(1000))
    image_url = Column(String(1000))

    chipset = Column(String(200))
    memory = Column(String(50))
    memory_type = Column(String(50))
    gpu_series = Column(String(200))
    brand = Column(String(100))
    clock_speed = Column(String(100))
    boost_clock = Column(String(100))
    color = Column(String(100))
    cooling = Column(String(100))
    tdp = Column(String(50))
    interface = Column(String(100))
    length_mm = Column(String(50))
    power_connectors = Column(String(100))

    in_stock = Column(Boolean, default=True)
    is_pre_order = Column(Boolean, default=False)
    is_upcoming = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    seller = relationship("Seller", back_populates="products")
    model = relationship("GpuModel", back_populates="products")
    prices = relationship("Price", back_populates="product", order_by="Price.recorded_at.desc()")

    @property
    def current_price(self):
        if self.prices:
            return self.prices[0].price
        return None

    @property
    def original_price(self):
        if self.prices:
            return self.prices[0].original_price
        return None

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    original_price = Column(Float)
    currency = Column(String(10), default="BDT")
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="prices")

def init_db(db_path=None):
    if db_path is None:
        db_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = f"sqlite:///{os.path.join(db_dir, 'gpu_prices.db')}"
    engine = create_engine(db_path, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine
