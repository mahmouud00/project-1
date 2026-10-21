from sqlalchemy.orm import Session
from decimal import Decimal
from backend import models

def calculate_suit_cost(db: Session, product_id: int, labor_cost: Decimal, overheads: Decimal, size_multiplier: Decimal = Decimal('1.0')) -> dict:
    bom_items = db.query(models.BOM).filter(models.BOM.product_id == product_id).all()
    total_material_cost = Decimal('0.0')
    material_breakdown = []

    for item in bom_items:
        material = db.query(models.RawMaterial).filter(models.RawMaterial.id == item.material_id).first()
        if material:
            adjusted_qty = item.quantity * size_multiplier
            cost = adjusted_qty * material.cost_price
            total_material_cost += cost
            material_breakdown.append({
                "material_name": material.name,
                "quantity": float(adjusted_qty),
                "unit": material.unit,
                "cost": float(cost)
            })

    total_cost = total_material_cost + labor_cost + overheads
    return {
        "product_id": product_id,
        "material_cost": float(total_material_cost),
        "labor_cost": float(labor_cost),
        "overheads": float(overheads),
        "total_cost": float(total_cost),
        "breakdown": material_breakdown
    }

def process_production_order(db: Session, order_id: int) -> dict:
    order = db.query(models.ProductionOrder).filter(models.ProductionOrder.id == order_id).first()
    if not order:
        return {"error": "Order not found"}

    bom_items = db.query(models.BOM).filter(models.BOM.product_id == order.product_id).all()

    for item in bom_items:
        material = db.query(models.RawMaterial).filter(models.RawMaterial.id == item.material_id).first()
        if material and material.stock_level >= item.quantity:
            material.stock_level -= item.quantity
        else:
            return {"error": f"Insufficient stock for material: {material.name if material else 'Unknown'}"}

    order.status = "cutting"
    db.commit()
    return {"message": "Order processed successfully", "order_id": order_id, "new_status": "cutting"}

def check_low_stock_alerts(db: Session) -> list:
    low_stock_items = db.query(models.RawMaterial).filter(
        models.RawMaterial.stock_level <= models.RawMaterial.reorder_point
    ).all()

    alerts = []
    for item in low_stock_items:
        alerts.append({
            "material_code": item.code,
            "material_name": item.name,
            "current_stock": float(item.stock_level),
            "reorder_point": float(item.reorder_point),
            "unit": item.unit
        })
    return alerts