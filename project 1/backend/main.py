from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
from datetime import datetime

from backend.database import engine, Base, get_db
from backend import models, schemas, services

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tailor ERP API")

@app.post("/suppliers/", response_model=schemas.Supplier)
def create_supplier(supplier: schemas.SupplierCreate, db: Session = Depends(get_db)):
    db_supplier = models.Supplier(**supplier.model_dump())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier

@app.get("/suppliers/", response_model=List[schemas.Supplier])
def read_suppliers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Supplier).offset(skip).limit(limit).all()

@app.post("/raw-materials/", response_model=schemas.RawMaterial)
def create_raw_material(material: schemas.RawMaterialCreate, db: Session = Depends(get_db)):
    db_material = models.RawMaterial(**material.model_dump())
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material

@app.get("/raw-materials/", response_model=List[schemas.RawMaterial])
def read_raw_materials(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.RawMaterial).offset(skip).limit(limit).all()

@app.post("/customers/", response_model=schemas.Customer)
def create_customer(customer: schemas.CustomerBase, db: Session = Depends(get_db)):
    db_customer = models.Customer(**customer.model_dump())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@app.get("/customers/", response_model=List[schemas.Customer])
def read_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Customer).offset(skip).limit(limit).all()

@app.post("/invoices/", response_model=schemas.Invoice)
def create_invoice(invoice: schemas.InvoiceBase, db: Session = Depends(get_db)):
    db_invoice = models.Invoice(**invoice.model_dump(), paid_amount=0)
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

@app.get("/invoices/", response_model=List[schemas.Invoice])
def read_invoices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Invoice).offset(skip).limit(limit).all()

@app.post("/production-orders/", response_model=schemas.ProductionOrder)
def create_production_order(order: schemas.ProductionOrderBase, db: Session = Depends(get_db)):
    db_order = models.ProductionOrder(**order.model_dump())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@app.get("/production-orders/", response_model=List[schemas.ProductionOrder])
def read_production_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.ProductionOrder).offset(skip).limit(limit).all()

@app.put("/production-orders/{order_id}/status")
def update_production_order_status(order_id: int, status: str, db: Session = Depends(get_db)):
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return {"message": "Status updated", "order_id": order_id, "new_status": status}

@app.get("/inventory/low-stock-alerts")
def low_stock_alerts(db: Session = Depends(get_db)):
    return services.check_low_stock_alerts(db)

@app.post("/transactions/", response_model=schemas.Transaction)
def create_transaction(transaction: schemas.TransactionBase, db: Session = Depends(get_db)):
    db_transaction = models.Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.get("/transactions/", response_model=List[schemas.Transaction])
def read_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Transaction).offset(skip).limit(limit).all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)