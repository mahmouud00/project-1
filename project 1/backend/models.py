from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey, DateTime, Boolean, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base
import enum

class InvoiceStatus(str, enum.Enum):
    proforma = "proforma"
    confirmed = "confirmed"
    delivered = "delivered"
    cancelled = "cancelled"

class ProductionStatus(str, enum.Enum):
    pending = "pending"
    cutting = "cutting"
    sewing = "sewing"
    fitting = "fitting"
    finishing = "finishing"
    ironing = "ironing"
    completed = "completed"

class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50))
    email = Column(String(100))
    address = Column(Text)
    credit_limit = Column(DECIMAL(15, 2), default=0)
    current_balance = Column(DECIMAL(15, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    materials = relationship("RawMaterial", back_populates="supplier")

class RawMaterial(Base):
    __tablename__ = "raw_materials"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    unit = Column(String(20), nullable=False)
    cost_price = Column(DECIMAL(15, 2), default=0)
    reorder_point = Column(DECIMAL(15, 2), default=0)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    stock_level = Column(DECIMAL(15, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    supplier = relationship("Supplier", back_populates="materials")

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(100))
    address = Column(Text)
    shoulder_size = Column(DECIMAL(5, 2))
    chest_size = Column(DECIMAL(5, 2))
    waist_size = Column(DECIMAL(5, 2))
    length_size = Column(DECIMAL(5, 2))
    notes = Column(Text)
    balance = Column(DECIMAL(15, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    invoices = relationship("Invoice", back_populates="customer")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    base_price = Column(DECIMAL(15, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    bom_items = relationship("BOM", back_populates="product")
    production_orders = relationship("ProductionOrder", back_populates="product")

class BOM(Base):
    __tablename__ = "bom"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    quantity = Column(DECIMAL(15, 2), nullable=False)
    product = relationship("Product", back_populates="bom_items")
    material = relationship("RawMaterial")

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    total_amount = Column(DECIMAL(15, 2), nullable=False)
    paid_amount = Column(DECIMAL(15, 2), default=0)
    status = Column(String(50), default="proforma")
    created_at = Column(DateTime, default=datetime.utcnow)
    customer = relationship("Customer", back_populates="invoices")
    transactions = relationship("Transaction", back_populates="invoice")
    production_order = relationship("ProductionOrder", back_populates="invoice", uselist=False)

class ProductionOrder(Base):
    __tablename__ = "production_orders"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    status = Column(String(50), default="pending")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice = relationship("Invoice", back_populates="production_order")
    product = relationship("Product", back_populates="production_orders")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    category = Column(String(100))
    description = Column(Text)
    related_invoice_id = Column(Integer, ForeignKey("invoices.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice = relationship("Invoice", back_populates="transactions")