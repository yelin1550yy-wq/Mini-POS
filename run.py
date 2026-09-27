# ==========================================
# FILE: app/routes.py
# ==========================================
from datetime import datetime
from app import db
from app.models import (
    Customer,
    Expense,
    Product,
    Purchase,
    Sale,
    SaleItem,
    StockMovement,
    Supplier,
    User,
)
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

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
        customer_data.append(
            {
                "customer": c,
                "total_buy_item": total_buy_item,
                "total_spend": total_spend,
            }
        )

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

        ref = f"SO-{datetime.now().strftime('%Y%m%d')}-{Sale.query.count() + 1:04d}"
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
                        sale_id=new_sale_obj.id,
                        product_id=int(p_id),
                        quantity=q,
                        price=p,
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
    return render_template("new_sale.html", customers=customers, products=products)


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
            prod.stock += item.keyword if hasattr(item, "keyword") else item.quantity
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
