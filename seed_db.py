from __future__ import annotations

from app import app, db, User, Role, Category, Product
from werkzeug.security import generate_password_hash


def seed() -> None:
    with app.app_context():
        db.create_all()

        admin_email = "admin@example.com"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(email=admin_email, role=Role.ADMIN, full_name="Admin")
            admin.password_hash = generate_password_hash("Admin123!")
            db.session.add(admin)

        # Categories
        cats = [
            ("Electronics", "Gadgets and devices"),
            ("Books", "Reading material"),
            ("Home", "Home essentials"),
        ]
        for name, desc in cats:
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name, description=desc))

        db.session.flush()

        # Products
        electronics = Category.query.filter_by(name="Electronics").first()
        books = Category.query.filter_by(name="Books").first()
        home = Category.query.filter_by(name="Home").first()

        products = [
            ("Wireless Mouse", "Ergonomic 2.4G mouse", electronics.id, 1999, 25),
            ("USB-C Charger", "Fast charging (20W)", electronics.id, 2499, 50),
            ("Python Crash Course", "Learn Python by building projects", books.id, 2899, 40),
            ("Data Structures", "Essential CS concepts", books.id, 3199, 30),
            ("Stainless Water Bottle", "Keeps drinks cold/hot", home.id, 1499, 60),
        ]

        for name, desc, category_id, price_cents, stock in products:
            if not Product.query.filter_by(name=name).first():
                db.session.add(
                    Product(
                        name=name,
                        description=desc,
                        category_id=category_id,
                        price_cents=price_cents,
                        stock=stock,
                    )
                )

        db.session.commit()
        print("Seed complete.")
        print("Admin credentials:")
        print("  Email: admin@example.com")
        print("  Password: Admin123!")


if __name__ == "__main__":
    seed()

