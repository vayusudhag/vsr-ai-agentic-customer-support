"""Repeatable synthetic seed data. All names, emails, and addresses are fictional.

Dates are generated relative to the moment of seeding so that demo scenarios
(in-transit orders, inside/outside the 30-day return window) stay valid.
Run:  python -m app.seed  (drops and recreates all tables)
"""
import random
from datetime import datetime, timedelta, timezone

from app.db import Base, SessionLocal, engine
from app.models import Order, OrderItem, Product, User
from app.security import hash_password

PRODUCTS = [
    # sku, name, category, price, rating, stock, tags, returnable, description
    ("AUD-100", "Halden Aria Wireless Earbuds", "Audio", 89.0, 4.4, 140, ["wireless", "noise-cancelling", "commute", "budget"], True,
     "True wireless earbuds with active noise cancellation, 28-hour battery with case, and IPX4 sweat resistance."),
    ("AUD-110", "Halden Aria Pro Headphones", "Audio", 249.0, 4.7, 60, ["wireless", "noise-cancelling", "travel", "premium"], True,
     "Over-ear headphones with adaptive noise cancellation, 40-hour battery, and multipoint Bluetooth."),
    ("AUD-120", "Lumio Pocket Speaker", "Audio", 59.0, 4.2, 210, ["portable", "waterproof", "outdoor", "budget"], True,
     "Palm-sized Bluetooth speaker, IP67 waterproof, 12-hour battery, clip-on strap."),
    ("AUD-130", "Lumio Studio Bookshelf Speakers", "Audio", 329.0, 4.6, 25, ["home", "hi-fi", "premium"], True,
     "Powered bookshelf pair with 4-inch woofers, optical input, and Bluetooth 5.3."),
    ("WEA-200", "Pulse Fit Band 3", "Wearables", 69.0, 4.1, 180, ["fitness", "sleep", "budget", "running"], True,
     "Slim fitness tracker with heart-rate, sleep tracking, and 10-day battery."),
    ("WEA-210", "Pulse Active Smartwatch", "Wearables", 199.0, 4.5, 90, ["fitness", "gps", "running", "waterproof"], True,
     "GPS smartwatch with 5 ATM water resistance, training load metrics, and 7-day battery."),
    ("WEA-220", "Pulse Trail Ultra Watch", "Wearables", 379.0, 4.8, 30, ["gps", "outdoor", "hiking", "premium"], True,
     "Rugged multisport watch with topo maps, solar charging, and 21-day battery."),
    ("OFF-300", "Kestrel Ergonomic Office Chair", "Home Office", 299.0, 4.5, 40, ["ergonomic", "lumbar", "work-from-home"], True,
     "Mesh-back chair with adjustable lumbar support, 4D armrests, and seat-depth adjustment."),
    ("OFF-310", "Kestrel Standing Desk 55\"", "Home Office", 449.0, 4.6, 22, ["standing", "work-from-home", "premium"], True,
     "Dual-motor sit-stand desk, 55 x 28 inch top, four memory presets, 300 lb capacity."),
    ("OFF-320", "Lumio Arc Desk Lamp", "Home Office", 49.0, 4.3, 160, ["lighting", "work-from-home", "budget"], True,
     "LED desk lamp with adjustable colour temperature, USB-C charging port, and auto-dim."),
    ("OFF-330", "Quill Mechanical Keyboard", "Home Office", 129.0, 4.6, 75, ["keyboard", "wireless", "productivity"], True,
     "Low-profile wireless mechanical keyboard with hot-swappable switches and three device slots."),
    ("OFF-340", "Quill Precision Mouse", "Home Office", 59.0, 4.4, 130, ["mouse", "wireless", "ergonomic", "productivity"], True,
     "Ergonomic wireless mouse with silent clicks, 8K DPI sensor, and 70-day battery."),
    ("KIT-400", "Brewline Pour-Over Coffee Set", "Kitchen", 45.0, 4.5, 95, ["coffee", "gift", "budget"], True,
     "Glass carafe, stainless filter, and gooseneck kettle set for pour-over coffee."),
    ("KIT-410", "Brewline Espresso Machine", "Kitchen", 399.0, 4.4, 18, ["coffee", "espresso", "premium"], True,
     "15-bar espresso machine with steam wand, PID temperature control, and 2 L reservoir."),
    ("KIT-420", "Ember Cast-Iron Skillet 12\"", "Kitchen", 39.0, 4.7, 200, ["cooking", "budget", "gift"], True,
     "Pre-seasoned 12-inch cast-iron skillet suitable for oven, stovetop, and campfire."),
    ("KIT-430", "Ember Chef Knife 8\"", "Kitchen", 79.0, 4.6, 85, ["cooking", "knife", "gift"], True,
     "High-carbon stainless 8-inch chef knife with full tang and pakkawood handle."),
    ("OUT-500", "Ridgeway 2-Person Tent", "Outdoor", 179.0, 4.5, 35, ["camping", "hiking", "lightweight"], True,
     "Freestanding 3-season backpacking tent, 1.9 kg packed, with two vestibules."),
    ("OUT-510", "Ridgeway Trail Backpack 40L", "Outdoor", 139.0, 4.6, 55, ["hiking", "travel", "camping"], True,
     "40-litre pack with ventilated back panel, hip-belt pockets, and rain cover."),
    ("OUT-520", "Ridgeway Insulated Bottle", "Outdoor", 29.0, 4.8, 400, ["hiking", "gift", "budget"], True,
     "750 ml vacuum-insulated bottle keeps drinks cold for 24 hours or hot for 12."),
    ("ACC-600", "Volt 65W USB-C Charger", "Accessories", 39.0, 4.5, 260, ["charging", "travel", "budget"], True,
     "Compact GaN charger with two USB-C and one USB-A port, 65 W total output."),
    ("ACC-610", "Volt Power Bank 20K", "Accessories", 55.0, 4.4, 190, ["charging", "travel", "portable"], True,
     "20,000 mAh power bank with 30 W USB-C PD and pass-through charging."),
    ("ACC-620", "Shield Laptop Sleeve 14\"", "Accessories", 35.0, 4.2, 140, ["laptop", "travel", "budget"], True,
     "Water-resistant padded sleeve for 13-14 inch laptops with accessory pocket."),
    ("GFT-700", "VSR Store Digital Gift Card $50", "Gift Cards", 50.0, 4.9, 9999, ["gift"], False,
     "Digital gift card delivered by email. Final sale and non-returnable."),
    ("GFT-710", "VSR Store Digital Gift Card $100", "Gift Cards", 100.0, 4.9, 9999, ["gift"], False,
     "Digital gift card delivered by email. Final sale and non-returnable."),
]

CUSTOMERS = [
    ("pardha.saradhi@example.com", "Pardha Saradhi", "12 Willow Lane, Springfield, IL 62701"),
    ("pavan.y@example.com", "Pavan Y", "88 Harbor St, Portland, ME 04101"),
    ("diego.ramirez@example.com", "Diego Ramirez", "410 Cedar Ave, Austin, TX 78701"),
    ("mei.chen@example.com", "Mei Chen", "27 Orchard Rd, Madison, WI 53703"),
    ("samuel.okafor@example.com", "Samuel Okafor", "5 Riverbend Ct, Raleigh, NC 27601"),
    ("lena.fischer@example.com", "Lena Fischer", "903 Pine St, Boulder, CO 80302"),
    ("omar.haddad@example.com", "Omar Haddad", "61 Elm Park, Columbus, OH 43215"),
    ("grace.kim@example.com", "Grace Kim", "220 Bay View Dr, Tampa, FL 33602"),
]
ADMINS = [("gopireddy.vsr@example.com", "Gopireddy VSR (Support Lead)"), ("ops@vsr-ai.example", "Riley Park (Operations)")]
DEMO_PASSWORD = "demo1234"
ADMIN_PASSWORD = "admin1234"
CARRIERS = ["UPS", "FedEx", "USPS", "DHL"]


def _order(n, customer, status, placed_days_ago, items, now, *, eta_in=None, delivered_days_ago=None):
    placed = now - timedelta(days=placed_days_ago)
    o = Order(
        order_number=f"ORD-{n}",
        customer=customer,
        status=status,
        placed_at=placed,
        shipping_address="",
        total=0.0,
    )
    if status in ("shipped", "in_transit", "delivered"):
        o.carrier = CARRIERS[n % len(CARRIERS)]
        o.tracking_number = f"1Z{n:04d}VSR{(n * 7919) % 100000:05d}"
        o.shipped_at = placed + timedelta(days=1)
    if status in ("shipped", "in_transit"):
        o.estimated_delivery = now + timedelta(days=eta_in if eta_in is not None else 3)
    if status == "processing":
        o.estimated_delivery = now + timedelta(days=eta_in if eta_in is not None else 6)
    if status == "delivered":
        o.delivered_at = now - timedelta(days=delivered_days_ago)
        o.estimated_delivery = o.delivered_at
    total = 0.0
    for prod, qty in items:
        o.items.append(OrderItem(product=prod, quantity=qty, unit_price=prod.price))
        total += prod.price * qty
    o.total = round(total, 2)
    return o


def seed(drop: bool = True) -> dict:
    rng = random.Random(42)
    if drop:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        products = {}
        for sku, name, cat, price, rating, stock, tags, returnable, desc in PRODUCTS:
            p = Product(sku=sku, name=name, category=cat, price=price, rating=rating, stock=stock,
                        tags=tags, returnable=returnable, description=desc)
            db.add(p)
            products[sku] = p
        users = []
        for email, name, _addr in CUSTOMERS:
            u = User(email=email, full_name=name, role="customer", password_hash=hash_password(DEMO_PASSWORD))
            db.add(u)
            users.append(u)
        for email, name in ADMINS:
            db.add(User(email=email, full_name=name, role="admin", password_hash=hash_password(ADMIN_PASSWORD)))
        addr = {u.email: a for (_e, _n, a), u in zip(CUSTOMERS, users)}
        P = products
        alex, priya = users[0], users[1]

        # Hand-crafted demo scenarios (documented in DEMO.md)
        orders = [
            _order(1001, alex, "shipped", 3, [(P["AUD-110"], 1)], now, eta_in=4),            # in transit
            _order(1002, alex, "delivered", 14, [(P["WEA-210"], 1), (P["ACC-600"], 1)], now, delivered_days_ago=10),  # returnable
            _order(1003, alex, "delivered", 60, [(P["OFF-330"], 1)], now, delivered_days_ago=45),  # outside window
            _order(1004, alex, "processing", 1, [(P["KIT-410"], 1)], now, eta_in=6),         # not shipped yet
            _order(1005, alex, "delivered", 9, [(P["GFT-710"], 1)], now, delivered_days_ago=8),   # final sale
            _order(1006, priya, "delivered", 12, [(P["OFF-300"], 1)], now, delivered_days_ago=7),  # other customer
            _order(1007, priya, "in_transit", 4, [(P["OUT-500"], 1), (P["OUT-520"], 2)], now, eta_in=2),
            _order(1008, priya, "cancelled", 20, [(P["KIT-430"], 1)], now),
        ]
        # Additional varied orders for realistic volume
        statuses = ["delivered", "delivered", "delivered", "shipped", "in_transit", "processing", "cancelled"]
        skus = list(P.keys())
        n = 1009
        for u in users[2:] + users[:2]:
            for _ in range(rng.randint(3, 5)):
                st = rng.choice(statuses)
                placed = rng.randint(2, 75)
                items = [(P[s], rng.randint(1, 2)) for s in rng.sample(skus, rng.randint(1, 3))]
                kw = {}
                if st == "delivered":
                    kw["delivered_days_ago"] = max(1, placed - rng.randint(2, 6))
                elif st in ("shipped", "in_transit", "processing"):
                    placed = min(placed, 6)
                    kw["eta_in"] = rng.randint(1, 6)
                orders.append(_order(n, u, st, placed, items, now, **kw))
                n += 1
        for o in orders:
            o.shipping_address = addr[o.customer.email]
            db.add(o)
        db.commit()
        return {"products": len(PRODUCTS), "customers": len(users), "orders": len(orders)}
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeded:", seed())
