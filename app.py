from __future__ import annotations

from datetime import datetime

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


# -------------------- Models --------------------

class Role:
    ADMIN = "admin"
    CUSTOMER = "customer"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default=Role.CUSTOMER)
    full_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    products = db.relationship("Product", back_populates="category", cascade="all,delete")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_cents = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category = db.relationship("Category", back_populates="products")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="placed")
    total_cents = db.Column(db.Integer, nullable=False, default=0)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
    items = db.relationship("OrderItem", back_populates="order", cascade="all,delete")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    name_snapshot = db.Column(db.String(200), nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False, default=5)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


# -------------------- Cart helpers (session) --------------------

def _get_cart() -> dict[str, int]:
    cart = (request.cookies.get("_dummy") or None)  # keep deterministic - not used
    # We use Flask session but avoid importing session in helper to keep call sites clear.
    from flask import session  # local import

    if "cart" not in session:
        session["cart"] = {}
    return session["cart"]


def cart_add(product_id: int, qty: int = 1) -> None:
    from flask import session

    cart = _get_cart()
    key = str(product_id)
    cart[key] = int(cart.get(key, 0)) + int(qty)
    session["cart"] = cart


def cart_set(product_id: int, qty: int) -> None:
    from flask import session

    cart = _get_cart()
    key = str(product_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = int(qty)
    session["cart"] = cart


def cart_items() -> list[tuple[Product, int]]:
    from flask import session

    cart = session.get("cart", {})
    if not cart:
        return []

    ids = [int(k) for k in cart.keys()]
    products = Product.query.filter(Product.id.in_(ids)).all()
    result = []
    for p in products:
        q = int(cart.get(str(p.id), 0))
        if q > 0:
            result.append((p, q))
    return result


def cart_total_cents() -> int:
    total = 0
    for p, q in cart_items():
        total += p.price_cents * q
    return total


# -------------------- Forms --------------------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])


class SignupForm(FlaskForm):
    full_name = StringField("Full name", validators=[Optional(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    price = IntegerField("Price (cents)", validators=[DataRequired(), NumberRange(min=0, max=1_000_000_000)])
    stock = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0, max=1_000_000_000)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])


class FeedbackForm(FlaskForm):
    rating = IntegerField("Rating (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=2, max=4000)])


# -------------------- Auth decorators --------------------

def role_required(role: str):
    def decorator(fn):
        @login_required
        def wrapper(*args, **kwargs):
            if getattr(current_user, "role", None) != role:
                flash("Unauthorized", "error")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)

        # preserve name
        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator


# -------------------- App factory --------------------

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="dev-secret-change-me",
        SQLALCHEMY_DATABASE_URI="sqlite:///ecommerce.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    csrf.init_app(app)

    # -------------------- Routes --------------------

    @app.get("/")
    def index():
        categories = Category.query.order_by(Category.name.asc()).all()
        category_id = request.args.get("category", type=int)
        q = request.args.get("q", type=str)

        products_query = Product.query
        if category_id:
            products_query = products_query.filter(Product.category_id == category_id)
        if q:
            products_query = products_query.filter(Product.name.ilike(f"%{q.strip()}%"))

        products = products_query.order_by(Product.id.desc()).limit(12).all()
        return render_template(
            "index.html",
            categories=categories,
            products=products,
            selected_category_id=category_id,
            q=q,
        )

    @app.get("/product/<int:product_id>")
    def product_detail(product_id: int):
        p = db.session.get(Product, product_id)
        if not p:
            flash("Product not found", "error")
            return redirect(url_for("index"))
        return render_template("product_detail.html", product=p)

    @app.post("/cart/add/<int:product_id>")
    def cart_add_route(product_id: int):
        qty = request.form.get("qty", type=int, default=1)
        if qty <= 0:
            qty = 1
        p = db.session.get(Product, product_id)
        if not p:
            flash("Product not found", "error")
            return redirect(url_for("index"))
        if p.stock <= 0:
            flash("Out of stock", "error")
            return redirect(url_for("product_detail", product_id=product_id))

        cart_add(product_id, qty=min(qty, p.stock))
        from flask import session

        flash(f"Added {p.name} to cart", "success")
        return redirect(request.referrer or url_for("cart"))

    @app.get("/cart")
    def cart():
        items = cart_items()
        total_cents = cart_total_cents()
        return render_template("cart.html", items=items, total_cents=total_cents)

    @app.post("/cart/set/<int:product_id>")
    def cart_set_route(product_id: int):
        qty = request.form.get("qty", type=int)
        if qty is None:
            return redirect(url_for("cart"))

        p = db.session.get(Product, product_id)
        if not p:
            return redirect(url_for("cart"))

        qty = max(0, min(qty, p.stock))
        cart_set(product_id, qty)
        flash("Cart updated", "success")
        return redirect(url_for("cart"))

    @app.post("/cart/clear")
    def cart_clear_route():
        from flask import session

        session["cart"] = {}
        flash("Cart cleared", "success")
        return redirect(url_for("cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        items = cart_items()
        if not items:
            flash("Your cart is empty", "error")
            return redirect(url_for("index"))

        if request.method == "POST":
            # Demo checkout: place order and clear cart.
            user = current_user
            order = Order(user_id=user.id, status="placed", total_cents=cart_total_cents())
            db.session.add(order)
            db.session.flush()

            for product, qty in items:
                # Basic stock decrement
                if product.stock < qty:
                    db.session.rollback()
                    flash(f"Insufficient stock for {product.name}", "error")
                    return redirect(url_for("cart"))

                product.stock -= qty
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        name_snapshot=product.name,
                        unit_price_cents=product.price_cents,
                        quantity=qty,
                    )
                )

            db.session.commit()

            from flask import session

            session["cart"] = {}
            flash("Order placed successfully!", "success")
            return redirect(url_for("order_success", order_id=order.id))

        total_cents = cart_total_cents()
        return render_template("checkout.html", items=items, total_cents=total_cents)

    @app.get("/order/<int:order_id>")
    @login_required
    def order_success(order_id: int):
        order = db.session.get(Order, order_id)
        if not order or order.user_id != current_user.id:
            flash("Order not found", "error")
            return redirect(url_for("index"))
        return render_template("order_success.html", order=order)

    @app.route("/feedback", methods=["GET", "POST"])
    @login_required
    def feedback():
        form = FeedbackForm()
        if form.validate_on_submit():
            f = Feedback(user_id=current_user.id, rating=form.rating.data, message=form.message.data)
            db.session.add(f)
            db.session.commit()
            flash("Feedback submitted. Thank you!", "success")
            return redirect(url_for("index"))
        return render_template("feedback.html", form=form)

    @app.get("/login")
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        return render_template("login.html", form=form)

    @app.post("/login")
    def login_post():
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.strip().lower()).first()
            if not user or not user.check_password(form.password.data):
                flash("Invalid credentials", "error")
                return render_template("login.html", form=form)

            login_user(user)
            return redirect(url_for("index"))

        return render_template("login.html", form=form)

    @app.get("/signup")
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        return render_template("signup.html", form=SignupForm())

    @app.post("/signup")
    def signup_post():
        form = SignupForm()
        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            if User.query.filter_by(email=email).first():
                flash("Email already registered", "error")
                return render_template("signup.html", form=form)

            user = User(email=email, full_name=form.full_name.data, role=Role.CUSTOMER)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created", "success")
            return redirect(url_for("index"))

        return render_template("signup.html", form=form)

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out", "success")
        return redirect(url_for("index"))

    # -------------------- Admin panel --------------------

    @app.get("/admin")
    @role_required(Role.ADMIN)
    def admin_dashboard():
        product_count = Product.query.count()
        category_count = Category.query.count()
        order_count = Order.query.count()
        customer_count = User.query.filter_by(role=Role.CUSTOMER).count()
        return render_template(
            "admin/dashboard.html",
            product_count=product_count,
            category_count=category_count,
            order_count=order_count,
            customer_count=customer_count,
        )

    @app.get("/admin/categories")
    @role_required(Role.ADMIN)
    def admin_categories():
        cats = Category.query.order_by(Category.name.asc()).all()
        form = CategoryForm()
        return render_template("admin/categories.html", categories=cats, form=form)

    @app.post("/admin/categories")
    @role_required(Role.ADMIN)
    def admin_categories_post():
        form = CategoryForm()
        if not form.validate_on_submit():
            return redirect(url_for("admin_categories"))
        cat = Category(name=form.name.data.strip(), description=form.description.data)
        db.session.add(cat)
        db.session.commit()
        flash("Category created", "success")
        return redirect(url_for("admin_categories"))

    @app.post("/admin/categories/<int:category_id>/delete")
    @role_required(Role.ADMIN)
    def admin_category_delete(category_id: int):
        cat = db.session.get(Category, category_id)
        if not cat:
            flash("Category not found", "error")
            return redirect(url_for("admin_categories"))
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted", "success")
        return redirect(url_for("admin_categories"))

    @app.get("/admin/products")
    @role_required(Role.ADMIN)
    def admin_products():
        categories = Category.query.order_by(Category.name.asc()).all()
        products = Product.query.order_by(Product.id.desc()).all()
        form = ProductForm()
        form.category_id.choices = [(c.id, c.name) for c in categories]
        return render_template("admin/products.html", products=products, form=form, categories=categories)

    @app.post("/admin/products")
    @role_required(Role.ADMIN)
    def admin_products_post():
        categories = Category.query.order_by(Category.name.asc()).all()
        form = ProductForm()
        form.category_id.choices = [(c.id, c.name) for c in categories]
        if not form.validate_on_submit():
            flash("Invalid product input", "error")
            return redirect(url_for("admin_products"))

        p = Product(
            name=form.name.data.strip(),
            description=form.description.data,
            price_cents=form.price.data,
            stock=form.stock.data,
            category_id=form.category_id.data,
        )
        db.session.add(p)
        db.session.commit()
        flash("Product created", "success")
        return redirect(url_for("admin_products"))

    @app.post("/admin/products/<int:product_id>/delete")
    @role_required(Role.ADMIN)
    def admin_product_delete(product_id: int):
        p = db.session.get(Product, product_id)
        if not p:
            flash("Product not found", "error")
            return redirect(url_for("admin_products"))
        db.session.delete(p)
        db.session.commit()
        flash("Product deleted", "success")
        return redirect(url_for("admin_products"))

    @app.get("/admin/orders")
    @role_required(Role.ADMIN)
    def admin_orders():
        orders = Order.query.order_by(Order.placed_at.desc()).all()
        return render_template("admin/orders.html", orders=orders)

    @app.get("/admin/customers")
    @role_required(Role.ADMIN)
    def admin_customers():
        customers = User.query.filter_by(role=Role.CUSTOMER).order_by(User.created_at.desc()).all()
        return render_template("admin/customers.html", customers=customers)

    @app.get("/admin/feedback")
    @role_required(Role.ADMIN)
    def admin_feedback():
        items = Feedback.query.order_by(Feedback.created_at.desc()).all()
        return render_template("admin/feedback.html", items=items)

    # Expose helpers to templates
    @app.context_processor
    def inject_cart_count():
        from flask import session

        cart = session.get("cart", {})
        cart_count = sum(int(q) for q in cart.values())
        return {"cart_count": cart_count}

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

