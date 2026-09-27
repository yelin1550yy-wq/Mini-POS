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


# ==========================================
# FILE: app/models.py
# ==========================================
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(64), unique=True, nullable=False)
  email = db.Column(db.String(120), unique=True, nullable=False)
  password_hash = db.Column(db.String(128))
  role = db.Column(db.String(20), default="user")

  def set_password(self, password):
    self.password_hash = generate_password_hash(password)

  def check_password(self, password):
    return check_password_hash(self.password_hash, password)


class Product(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(100), nullable=False)
  sku = db.Column(db.String(50), unique=True, nullable=False)
  price = db.Column(db.Float, nullable=False)
  cost = db.Column(db.Float, nullable=False)
  stock = db.Column(db.Integer, default=0)
  category = db.Column(db.String(50))


class Supplier(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(100), nullable=False)
  contact = db.Column(db.String(50))
  email = db.Column(db.String(120))
  address = db.Column(db.Text)


class Customer(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(100), nullable=False)
  account_name = db.Column(db.String(100))
  phone = db.Column(db.String(30))
  township = db.Column(db.String(50))
  is_blacklisted = db.Column(db.Boolean, default=False)
  sales = db.relationship("Sale", backref="customer", lazy=True)


class Purchase(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  reference = db.Column(db.String(50), unique=True, nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)
  supplier_id = db.Column(
      db.Integer, db.ForeignKey("supplier.id"), nullable=False
  )
  total_amount = db.Column(db.Float, nullable=False)
  items = db.relationship(
      "PurchaseItem", backref="purchase", cascade="all, delete-orphan"
  )


class PurchaseItem(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  purchase_id = db.Column(db.Integer, db.ForeignKey("purchase.id"), nullable=False)
  product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
  quantity = db.Column(db.Integer, nullable=False)
  price = db.Column(db.Float, nullable=False)
  product = db.relationship("Product")


class Sale(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  reference = db.Column(db.String(50), unique=True, nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)
  customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
  total_amount = db.Column(db.Float, nullable=False)
  status = db.Column(db.String(20), default="Completed")
  items = db.relationship(
      "SaleItem", backref="sale", cascade="all, delete-orphan"
  )


class SaleItem(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
  product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
  quantity = db.Column(db.Integer, nullable=False)
  price = db.Column(db.Float, nullable=False)
  product = db.relationship("Product")


class StockMovement(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
  qty_change = db.Column(db.Integer, nullable=False)
  type = db.Column(db.String(20), nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)
  reference = db.Column(db.String(50))
  product = db.relationship("Product")


class Expense(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  title = db.Column(db.String(100), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)
  category = db.Column(db.String(50))


# ==========================================
# FILE: app/routes.py
# ==========================================
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, login_user, logout_user
from app import db
from app.models import (
    Customer,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    Purchase,
    Expense,
    User,
)

main = Blueprint("main", __name__)


@main.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    user = User.query.filter_by(username=request.form.get("username")).first()
    if user and user.check_password(request.form.get("password")):
      login_user(user)
      return redirect(url_for("main.dashboard"))
    flash("Invalid username or password", "danger")
  return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
  logout_user()
  return redirect(url_for("main.login"))


@main.route("/")
@login_required
def dashboard():
  total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
  total_returns = (
      db.session.query(db.func.sum(SaleItem.quantity))
      .join(Sale)
      .filter(Sale.status == "Returned")
      .scalar()
      or 0
  )
  total_items_sold = (
      db.session.query(db.func.sum(SaleItem.quantity))
      .join(Sale)
      .filter(Sale.status == "Completed")
      .scalar()
      or 1
  )
  return_ratio = (
      (total_returns / (total_items_sold + total_returns)) * 100
      if (total_items_sold + total_returns) > 0
      else 0
  )

  return render_template(
      "index.html",
      total_sales=total_sales,
      total_returns=total_returns,
      return_ratio=round(return_ratio, 2),
  )


@main.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
  if request.method == "POST":
    name = request.form.get("name")
    account_name = request.form.get("account_name")
    phone = request.form.get("phone")
    township = request.form.get("township")
    is_blacklisted = True if request.form.get("is_blacklisted") else False

    new_cust = Customer(
        name=name,
        account_name=account_name,
        phone=phone,
        township=township,
        is_blacklisted=is_blacklisted,
    )
    db.session.add(new_cust)
    db.session.commit()
    flash("Customer registered successfully!", "success")
    return redirect(url_for("main.customers"))

  all_customers = Customer.query.all()
  customer_data = []
  for c in all_customers:
    completed_sales = [s for s in c.sales if s.status == "Completed"]
    total_buy_item = sum(
        sum(item.quantity for item in s.items) for s in completed_sales
    )
    total_spend = sum(s.total_amount for s in completed_sales)
    customer_data.append({
        "customer": c,
        "total_buy_item": total_buy_item,
        "total_spend": total_spend,
    })

  return render_template("customers.html", customer_data=customer_data)


@main.route("/customer/toggle_blacklist/", methods=["POST"])
@login_required
def toggle_blacklist(id):
  cust = Customer.query.get_or_404(id)
  cust.is_blacklisted = not cust.is_blacklisted
  db.session.commit()
  flash(
      f"Customer {cust.name} blacklist status updated.",
      "warning" if cust.is_blacklisted else "success",
  )
  return redirect(url_for("main.customers"))


@main.route("/sales")
@login_required
def sales_list():
  all_sales = Sale.query.order_by(Sale.date.desc()).all()
  return render_template("sales.html", sales=all_sales)


@main.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale():
  if request.method == "POST":
    customer_id = request.form.get("customer_id")
    cust = Customer.query.get(customer_id)
    if cust and cust.is_blacklisted:
      flash("Error: Cannot create sale for a blacklisted customer!", "danger")
      return redirect(url_for("main.new_sale"))

    ref = (
        f"SO-{datetime.now().strftime('%Y%m%d')}-{Sale.query.count() + 1:04d}"
    )
    product_ids = request.form.getlist("product_id[]")
    quantities = request.form.getlist("quantity[]")
    prices = request.form.getlist("price[]")

    new_sale_obj = Sale(
        reference=ref, customer_id=customer_id, total_amount=0, status="Completed"
    )
    db.session.add(new_sale_obj)
    db.session.flush()

    grand_total = 0
    for p_id, qty, prc in zip(product_ids, quantities, prices):
      if p_id and qty:
        q = int(qty)
        p = float(prc)
        grand_total += q * p
        db.session.add(
            SaleItem(
                sale_id=new_sale_obj.id, product_id=int(p_id), quantity=q, price=p
            )
        )

        prod = Product.query.get(int(p_id))
        if prod:
          prod.stock -= q
          db.session.add(
              StockMovement(
                  product_id=prod.id,
                  qty_change=-q,
                  type="Sale",
                  reference=ref,
              )
          )

    new_sale_obj.total_amount = grand_total
    db.session.commit()
    flash("Sale completed successfully!", "success")
    return redirect(url_for("main.sales_list"))

  customers = Customer.query.filter_by(is_blacklisted=False).all()
  products = Product.query.all()
  return render_template(
      "new_sale.html", customers=customers, products=products
  )


@main.route("/sales/return/", methods=["POST"])
@login_required
def return_sale(id):
  sale = Sale.query.get_or_404(id)
  if sale.status == "Returned":
    flash("This sale is already marked as returned.", "warning")
    return redirect(url_for("main.sales_list"))

  sale.status = "Returned"
  for item in sale.items:
    prod = Product.query.get(item.product_id)
    if prod:
      prod.stock += item.quantity
      db.session.add(
          StockMovement(
              product_id=prod.id,
              qty_change=item.quantity,
              type="Return",
              reference=sale.reference,
          )
      )

  db.session.commit()
  flash(f"Sale {sale.reference} successfully marked as Returned.", "info")
  return redirect(url_for("main.sales_list"))