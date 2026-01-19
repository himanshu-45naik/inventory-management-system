from flask import jsonify
from sqlalchemy import func
from datetime import datetime, timedelta

@app.route("/api/companies/<uuid:company_id>/alerts/low-stock", methods=["GET"])
def low_stock_alerts(company_id):
    # ASSUMPTION:
    # "Recent sales" is considered as sales in the last 30 days
    DAYS_WINDOW = 30
    since_date = datetime.utcnow() - timedelta(days=DAYS_WINDOW)

    alerts = []

    # Fetch all low-stock inventory items for this company
    low_stock_items = (
        db.session.query(
            Inventory.id.label("inventory_id"),
            Inventory.quantity.label("current_stock"),

            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.sku,
            Product.low_stock_threshold,

            Warehouse.id.label("warehouse_id"),
            Warehouse.name.label("warehouse_name"),

            Supplier.id.label("supplier_id"),
            Supplier.name.label("supplier_name")
        )
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .join(Supplier, Supplier.id == Product.supplier_id)
        .filter(Product.company_id == company_id)
        # ASSUMPTION:
        # Low stock = current inventory below product threshold
        .filter(Inventory.quantity < Product.low_stock_threshold)
        .all()
    )

    # For each low-stock item, check recent sales activity
    for item in low_stock_items:
        # ASSUMPTION:
        # A sale is represented by:  event_type = 'sale', delta = 'dec', quantity_per_event = positive integer
        total_sales_quantity = (
            db.session.query(func.sum(InventoryEvent.quantity_per_event))
            .filter(InventoryEvent.inventory_id == item.inventory_id)
            .filter(InventoryEvent.event_type == "sale")
            .filter(InventoryEvent.delta == "dec")
            .filter(InventoryEvent.created_at >= since_date)
            .scalar()
        )

        # Edge case:
        # If there are no recent sales, we do not raise an alert
        if not total_sales_quantity:
            continue

        # Average daily sales rate
        daily_sales_rate = total_sales_quantity / DAYS_WINDOW

        # Safety check - edge case
        if daily_sales_rate == 0:
            continue

        # ASSUMPTION:
        # Days until stockout is an estimate based on recent sales velocity
        days_until_stockout = int(item.current_stock / daily_sales_rate)

        alerts.append({
            "product_id": item.product_id,
            "product_name": item.product_name,
            "sku": item.sku,
            "warehouse_id": item.warehouse_id,
            "warehouse_name": item.warehouse_name,
            "current_stock": item.current_stock,
            "threshold": item.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id": item.supplier_id,
                "name": item.supplier_name
            }
        })

    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    })
