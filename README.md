# Python E-commerce Website (Flask)

A simple e-commerce web app built with **Flask** + **Jinja templates**.

## Features
- Product listing
- Product detail page
- Session-based shopping cart
- Checkout page (demo)
- SQLite database for products

## Tech Stack
- Python 3
- Flask
- Flask-SQLAlchemy
- Bootstrap (frontend)

## Setup (local)
```bash
cd /Users/akshatkumawat/Desktop/ecommerce_site
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Initialize DB + seed products/admin
python seed_db.py

# Run server
flask --app app run --debug

```

Then open: http://127.0.0.1:5000

## Admin/Seeder
- Edit `seed_db.py` to change sample products.

