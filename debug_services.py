from app import app, db, Service

with app.app_context():
    services = Service.query.all()
    print(f"Total services found: {len(services)}")
    for s in services:
        print(f"ID: {s.id}, Category: '{s.category}', Name: {s.name}")

    categories = [
        '🛋️ Upholstery & Interior Works',
        '🚤 Marine & Canvas Services',
        '🛠️ Fabrication & Engineering',
        '🧵 Textiles & Branding',
        '🏕️ Outdoor & Utility Solutions',
        '🧼 Cleaning & Maintenance'
    ]
    
    print("\nChecking categories matches:")
    for cat in categories:
        count = Service.query.filter_by(category=cat).count()
        print(f"Category '{cat}': {count} items")
