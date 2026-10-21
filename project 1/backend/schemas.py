from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class SupplierBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class SupplierCreate(SupplierBase):
    credit_limit: Decimal = 0
    current_balance: Decimal = 0

class Supplier(SupplierBase):
    id: int
    credit_limit: Decimal
    current_balance: Decimal
    created_at: datetime
    class Config:
        from_attributes = True

class RawMaterialBase(BaseModel):
    code: str
    name: str
    category: Optional[str] = None
    unit: str
    cost_price: Decimal = 0
    reorder_point: Decimal = 0
    supplier_id: Optional[int] = None

class RawMaterialCreate(RawMaterialBase):
    stock_level: Decimal = 0

class RawMaterial(RawMaterialBase):
    id: int
    stock_level: Decimal
    created_at: datetime
    class Config:
        from_attributes = True

class CustomerBase(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    shoulder_size: Optional[Decimal] = None
    chest_size: Optional[Decimal] = None
    waist_size: Optional[Decimal] = None
    length_size: Optional[Decimal] = None
    notes: Optional[str] = None

class Customer(CustomerBase):
    id: int
    balance: Decimal
    created_at: datetime
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    base_price: Decimal = 0

class Product(ProductBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class BOMBase(BaseModel):
    product_id: int
    material_id: int
    quantity: Decimal

class BOM(BOMBase):
    id: int
    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    customer_id: int
    total_amount: Decimal
    status: Optional[str] = "proforma"

class Invoice(InvoiceBase):
    id: int
    paid_amount: Decimal
    created_at: datetime
    class Config:
        from_attributes = True

class ProductionOrderBase(BaseModel):
    invoice_id: int
    product_id: int
    status: Optional[str] = "pending"
    notes: Optional[str] = None

class ProductionOrder(ProductionOrderBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    type: str
    amount: Decimal
    category: Optional[str] = None
    description: Optional[str] = None
    related_invoice_id: Optional[int] = None

class Transaction(TransactionBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True