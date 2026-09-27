# ==========================================
# FILE: run.py (Project Root)
# ==========================================
import os
from app import create_app, db
from app.models import (
    User,
    Product,
    Supplier,
    Customer,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    StockMovement,
    Expense,
    Capital,
    TierConfig,
)

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "User": User,
        "Product": Product,
        "Supplier": Supplier,
        "Customer": Customer,
        "Purchase": Purchase,
        "PurchaseItem": PurchaseItem,
        "Sale": Sale,
        "SaleItem": SaleItem,
        "StockMovement": StockMovement,
        "Expense": Expense,
        "Capital": Capital,
        "TierConfig": TierConfig,
    }


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@example.com", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)

            user = User(username="staff", email="staff@example.com", role="user")
            user.set_password("staff123")
            db.session.add(user)

            db.session.commit()
            print("Default users created: admin/admin123, staff/staff123")

    app.run(debug=True, host="0.0.0.0", port=5000)