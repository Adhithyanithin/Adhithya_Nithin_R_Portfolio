"""Smart Inventory & Order Management System (Flask + MySQL)."""
import os
from contextlib import contextmanager

import mysql.connector
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "smart_inventory"),
}


@contextmanager
def db():
    """Yield (connection, cursor); commit on success, roll back on error."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def log_txn(cur, product_id, qty, kind, note=""):
    cur.execute(
        "INSERT INTO inventory_transactions (product_id, change_qty, type, note) "
        "VALUES (%s, %s, %s, %s)", (product_id, qty, kind, note))


@app.route("/")
def dashboard():
    with db() as (_, cur):
        cur.execute("SELECT COUNT(*) AS n FROM products")
        n_products = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS revenue "
                    "FROM orders WHERE status = 'Completed'")
        totals = cur.fetchone()
        cur.execute("SELECT sku, name, stock, reorder_level FROM products "
                    "WHERE stock <= reorder_level ORDER BY stock")
        low = cur.fetchall()
        cur.execute("SELECT p.name, SUM(i.quantity) AS sold, SUM(i.quantity * i.unit_price) AS revenue "
                    "FROM order_items i JOIN orders o ON o.id = i.order_id "
                    "JOIN products p ON p.id = i.product_id "
                    "WHERE o.status = 'Completed' GROUP BY p.id ORDER BY sold DESC LIMIT 5")
        top = cur.fetchall()
        cur.execute("SELECT o.id, c.name AS customer, o.total, o.status, o.order_date "
                    "FROM orders o JOIN customers c ON c.id = o.customer_id "
                    "ORDER BY o.id DESC LIMIT 5")
        recent = cur.fetchall()
    return render_template("dashboard.html", n_products=n_products, totals=totals,
                           low=low, top=top, recent=recent)


@app.route("/api/dashboard-data")
def dashboard_data():
    with db() as (_, cur):
        cur.execute("SELECT DATE(order_date) AS day, SUM(total) AS total FROM orders "
                    "WHERE status = 'Completed' AND order_date >= CURDATE() - INTERVAL 6 DAY "
                    "GROUP BY DATE(order_date) ORDER BY day")
        sales = [{"day": str(r["day"]), "total": float(r["total"])} for r in cur.fetchall()]
        cur.execute("SELECT name, stock, reorder_level FROM products ORDER BY name")
        stock = cur.fetchall()
    return jsonify(sales=sales, stock=stock)


@app.route("/products", methods=["GET", "POST"])
def products():
    with db() as (conn, cur):
        if request.method == "POST":
            f = request.form
            try:
                cur.execute(
                    "INSERT INTO products (sku, name, supplier_id, price, stock, reorder_level) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (f["sku"].strip(), f["name"].strip(), f.get("supplier_id") or None,
                     f["price"], to_int(f.get("stock")), to_int(f.get("reorder_level"), 10)))
                flash("Product added.", "ok")
            except mysql.connector.Error as e:
                conn.rollback()
                flash(f"Could not add product: {e.msg}", "error")
            return redirect(url_for("products"))
        cur.execute("SELECT p.*, s.name AS supplier FROM products p "
                    "LEFT JOIN suppliers s ON s.id = p.supplier_id ORDER BY p.name")
        items = cur.fetchall()
        cur.execute("SELECT id, name FROM suppliers ORDER BY name")
        suppliers = cur.fetchall()
    return render_template("products.html", items=items, suppliers=suppliers)


@app.post("/products/<int:pid>/stock")
def update_stock(pid):
    qty = to_int(request.form.get("qty"))
    note = request.form.get("note", "").strip()[:200]
    with db() as (_, cur):
        cur.execute("SELECT stock FROM products WHERE id = %s FOR UPDATE", (pid,))
        row = cur.fetchone()
        if not row:
            abort(404)
        if qty == 0 or row["stock"] + qty < 0:
            flash("Enter a non-zero quantity; stock cannot go below zero.", "error")
        else:
            cur.execute("UPDATE products SET stock = stock + %s WHERE id = %s", (qty, pid))
            log_txn(cur, pid, qty, "RESTOCK" if qty > 0 else "ADJUST", note)
            flash("Stock updated.", "ok")
    return redirect(url_for("products"))


@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    with db() as (_, cur):
        if request.method == "POST":
            f = request.form
            cur.execute("INSERT INTO suppliers (name, phone, email) VALUES (%s, %s, %s)",
                        (f["name"].strip(), f.get("phone", "").strip(), f.get("email", "").strip()))
            flash("Supplier added.", "ok")
            return redirect(url_for("suppliers"))
        cur.execute("SELECT s.*, COUNT(p.id) AS n_products FROM suppliers s "
                    "LEFT JOIN products p ON p.supplier_id = s.id GROUP BY s.id ORDER BY s.name")
        items = cur.fetchall()
    return render_template("suppliers.html", items=items)


@app.post("/customers")
def add_customer():
    f = request.form
    with db() as (_, cur):
        cur.execute("INSERT INTO customers (name, phone, email) VALUES (%s, %s, %s)",
                    (f["name"].strip(), f.get("phone", "").strip(), f.get("email", "").strip()))
    flash("Customer added.", "ok")
    return redirect(url_for("orders"))


@app.route("/orders", methods=["GET", "POST"])
def orders():
    with db() as (conn, cur):
        if request.method == "POST":
            cid = to_int(request.form.get("customer_id"))
            pid = to_int(request.form.get("product_id"))
            qty = to_int(request.form.get("quantity"))
            try:
                cur.execute("SELECT name, price, stock, reorder_level FROM products "
                            "WHERE id = %s FOR UPDATE", (pid,))
                p = cur.fetchone()
                if not p or qty < 1:
                    flash("Choose a product and a quantity of at least 1.", "error")
                elif p["stock"] < qty:
                    flash(f"Only {p['stock']} of {p['name']} in stock.", "error")
                else:
                    cur.execute("INSERT INTO orders (customer_id, total) VALUES (%s, %s)",
                                (cid, p["price"] * qty))
                    oid = cur.lastrowid
                    cur.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                                "VALUES (%s, %s, %s, %s)", (oid, pid, qty, p["price"]))
                    cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, pid))
                    log_txn(cur, pid, -qty, "SALE", f"Order #{oid}")
                    flash(f"Order #{oid} placed.", "ok")
                    left = p["stock"] - qty
                    if left <= p["reorder_level"]:
                        flash(f"Low stock alert: {p['name']} has {left} left.", "warn")
            except mysql.connector.Error as e:
                conn.rollback()
                flash(f"Could not place order: {e.msg}", "error")
            return redirect(url_for("orders"))
        cur.execute("SELECT o.id, c.name AS customer, "
                    "GROUP_CONCAT(CONCAT(p.name, ' x', i.quantity) SEPARATOR ', ') AS items, "
                    "o.total, o.status, o.order_date "
                    "FROM orders o JOIN customers c ON c.id = o.customer_id "
                    "JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id "
                    "GROUP BY o.id ORDER BY o.id DESC")
        rows = cur.fetchall()
        cur.execute("SELECT id, name FROM customers ORDER BY name")
        customers = cur.fetchall()
        cur.execute("SELECT id, name, stock, price FROM products WHERE stock > 0 ORDER BY name")
        prods = cur.fetchall()
    return render_template("orders.html", rows=rows, customers=customers, prods=prods)


@app.post("/orders/<int:oid>/cancel")
def cancel_order(oid):
    with db() as (_, cur):
        cur.execute("SELECT status FROM orders WHERE id = %s FOR UPDATE", (oid,))
        order = cur.fetchone()
        if not order or order["status"] != "Completed":
            flash("This order cannot be cancelled.", "error")
        else:
            cur.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (oid,))
            for it in cur.fetchall():
                cur.execute("UPDATE products SET stock = stock + %s WHERE id = %s",
                            (it["quantity"], it["product_id"]))
                log_txn(cur, it["product_id"], it["quantity"], "RETURN", f"Order #{oid} cancelled")
            cur.execute("UPDATE orders SET status = 'Cancelled' WHERE id = %s", (oid,))
            flash(f"Order #{oid} cancelled and stock restored.", "ok")
    return redirect(url_for("orders"))


if __name__ == "__main__":
    app.run(debug=True)
