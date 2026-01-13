from app import app, db, Service

def update_services():
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        
        # Clear existing services
        db.session.query(Service).delete()
        
        services_data = [
            {
                'category': '🛋️ Upholstery & Interior Works',
                'items': [
                    ('Upholstery & interior finishing', 'Professional upholstery for furniture and interiors.'),
                    ('Car seat covers & ceiling upholstery', 'Custom car seat covers and roof lining repair.'),
                    ('Foam mattresses, bed linen & carpeting', 'High-quality foam products and installation.')
                ]
            },
            {
                'category': '🚤 Marine & Canvas Services',
                'items': [
                    ('Boat furnishing & marine canvas works', 'Complete boat upholstery and canvas solutions.'),
                    ('Covers, blinds & protective canvas', 'Custom protective covers and blinds.'),
                    ('Canvas repairs & new canvas manufacturing', 'Repair and fabrication of canvas products.'),
                    ('Life rings, life jackets & life rafts', 'Marine safety equipment and servicing.')
                ]
            },
            {
                'category': '🛠️ Fabrication & Engineering',
                'items': [
                    ('Spray painting', 'Professional spray painting services.'),
                    ('Welding', 'Metal welding and repair.'),
                    ('Metal fabrication', 'Custom metal structures and fittings.'),
                    ('Fibre glass works', 'Fiberglass repair and fabrication.')
                ]
            },
            {
                'category': '🧵 Textiles & Branding',
                'items': [
                    ('Banners & uniforms', 'Custom banners and staff uniforms.'),
                    ('T-shirt printing', 'High-quality t-shirt branding.'),
                    ('PVC products', 'Durable PVC covers and products.')
                ]
            },
            {
                'category': '🏕️ Outdoor & Utility Solutions',
                'items': [
                    ('Camping equipment', 'Tents, mattresses, and outdoor gear repairs.')
                ]
            },
            {
                'category': '🧼 Cleaning & Maintenance',
                'items': [
                    ('Cleaning services', 'Professional upholstery and carpet cleaning.'),
                    ('Fumigation services', 'Pest control and fumigation.'),
                    ('Sewing machine repairs', 'Service and repair of industrial and domestic machines.')
                ]
            }
        ]

        for group in services_data:
            for name, desc in group['items']:
                service = Service(
                    category=group['category'],
                    name=name,
                    description=desc
                )
                db.session.add(service)
        
        db.session.commit()
        print("Services updated successfully!")

if __name__ == '__main__':
    update_services()
