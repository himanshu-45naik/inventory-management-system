from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
db = SQLAlchemy(app)

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()

    # validating contents of data
    if not data:
        return {"error": "Request body is missing"}, 400

    required_fields = ['name', 'sku', 'price', 'warehouse_id']
    for field in required_fields:
        if field not in data:
            return {"error": f"Missing field: {field}"}, 400

    try:
        # product + inventory committed at the same time
        with db.session.begin():

            product = Product(
                name=data['name'],
                sku=data['sku'],
                price=data['price'],
                warehouse_id=data['warehouse_id']
            )
            db.session.add(product)
            db.session.flush()  # get product.id without committing

            inventory = Inventory(
                product_id=product.id,
                warehouse_id=data['warehouse_id'],
                quantity=data['initial_quantity']
            )
            db.session.add(inventory)

        return { "message": "Product created successfully", "product_id": product.id}

    # Assuming database checking for unique SKU
    except IntegrityError:
        db.session.rollback()
        return {"error": "SKU already exists"}, 409

    # Incase of database system failure
    except Exception:
        db.session.rollback()
        return {"error": "Something went wrong"}, 50
