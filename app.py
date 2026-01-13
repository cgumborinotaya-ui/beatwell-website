from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
from PIL import Image, ImageFilter

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
default_db_path = os.path.join(app.instance_path, 'beatwell.db')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or f'sqlite:///{default_db_path}'
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'img', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED_UPLOAD_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.pdf'}

def _allowed_upload(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_UPLOAD_EXTENSIONS

# --- Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # Household, Marine, etc.
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(100), nullable=True)

class QuoteRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    service_category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='New')  # New, Contacted, In Progress, Completed
    image_filename = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    approved = db.Column(db.Boolean, default=False)

# --- Routes ---

@app.route('/')
def home():
    services = Service.query.limit(3).all()
    testimonials = Testimonial.query.filter_by(approved=True).limit(3).all()
    def list_images(relative_dir: str):
        abs_dir = os.path.join(app.static_folder, *relative_dir.split('/'))
        if not os.path.isdir(abs_dir):
            return []
        allowed_ext = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
        files = [
            f for f in sorted(os.listdir(abs_dir))
            if os.path.isfile(os.path.join(abs_dir, f)) and f.lower().endswith(allowed_ext)
        ]
        return [url_for('static', filename=f'{relative_dir}/{f}') for f in files]

    hero_images = list_images('img/hero')
    if len(hero_images) < 2:
        hero_images = list_images('img/portfolio')[:6]
    if len(hero_images) < 2:
        hero_images = [url_for('static', filename='img/hero-bg.jpg')]

    return render_template('index.html', services=services, testimonials=testimonials, hero_images=hero_images)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    categories = [
        'Upholstery & Interior Works',
        'Marine & Canvas Services',
        'Fabrication & Engineering',
        'Textiles & Branding',
        'Outdoor & Utility Solutions',
        'Cleaning & Maintenance'
    ]
    grouped_services = {}
    for cat in categories:
        grouped_services[cat] = Service.query.filter_by(category=cat).all()
    return render_template('services.html', grouped_services=grouped_services)

@app.route('/portfolio')
def portfolio():
    portfolio_dir = os.path.join(app.static_folder, 'img', 'portfolio')
    os.makedirs(portfolio_dir, exist_ok=True)
    allowed_ext = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
    file_names = [
        f for f in sorted(os.listdir(portfolio_dir))
        if os.path.isfile(os.path.join(portfolio_dir, f)) and f.lower().endswith(allowed_ext)
    ]

    def _ahash(image_path: str, size: int = 8) -> int:
        with Image.open(image_path) as img:
            img = img.convert('L').resize((size, size))
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = 0
            for p in pixels:
                bits = (bits << 1) | (1 if p > avg else 0)
            return bits

    def _hamming(a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def _edge_score(image_path: str) -> float:
        with Image.open(image_path) as img:
            img = img.convert('L').resize((256, 256))
            edges = img.filter(ImageFilter.FIND_EDGES)
            pixels = list(edges.getdata())
            return sum(pixels) / len(pixels)

    image_infos = []
    for f in file_names:
        full_path = os.path.join(portfolio_dir, f)
        try:
            image_infos.append({
                'file': f,
                'path': full_path,
                'mtime': os.path.getmtime(full_path),
                'hash': _ahash(full_path),
                'edge': _edge_score(full_path),
            })
        except Exception:
            image_infos.append({
                'file': f,
                'path': full_path,
                'mtime': os.path.getmtime(full_path),
                'hash': None,
                'edge': 0.0,
            })

    groups = []
    for info in sorted(image_infos, key=lambda x: x['mtime']):
        placed = False
        for g in groups:
            if info['hash'] is None or g['hash'] is None:
                continue
            if _hamming(info['hash'], g['hash']) <= 12:
                g['items'].append(info)
                placed = True
                break
        if not placed:
            groups.append({'hash': info['hash'], 'items': [info]})

    portfolio_groups = []
    for g in groups:
        items = g['items']
        before = max(items, key=lambda x: x['edge'])
        after = min(items, key=lambda x: x['edge'])
        extras = [x for x in items if x['file'] not in {before['file'], after['file']}]
        portfolio_groups.append({
            'before': before['file'],
            'after': after['file'],
            'extras': [x['file'] for x in sorted(extras, key=lambda x: x['mtime'])],
            'mtime': min(x['mtime'] for x in items),
        })

    portfolio_groups = sorted(portfolio_groups, key=lambda x: x['mtime'])
    return render_template('portfolio.html', portfolio_groups=portfolio_groups)

@app.route('/quote', methods=['GET', 'POST'])
def quote():
    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone_number']
        category = request.form['service_category']
        description = request.form['description']
        location = request.form['location']
        
        attachment = request.files.get('image')
        attachment_filename = None
        if attachment and attachment.filename:
            if not _allowed_upload(attachment.filename):
                flash('Only images or PDF files are allowed.', 'danger')
                return redirect(url_for('quote'))

            safe_original = secure_filename(attachment.filename)
            _, ext = os.path.splitext(safe_original)
            unique_name = f'{uuid.uuid4().hex}{ext.lower()}'
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            attachment.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            attachment_filename = unique_name

        new_quote = QuoteRequest(
            full_name=full_name,
            phone_number=phone,
            service_category=category,
            description=description,
            location=location,
            image_filename=attachment_filename
        )
        db.session.add(new_quote)
        db.session.commit()
        flash('Your quote request has been submitted successfully!', 'success')
        return redirect(url_for('home'))
    return render_template('quote.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/testimonial', methods=['GET', 'POST'])
def testimonial_submit():
    if request.method == 'POST':
        customer_name = (request.form.get('customer_name') or '').strip()
        content = (request.form.get('content') or '').strip()
        rating_raw = (request.form.get('rating') or '').strip()

        try:
            rating = int(rating_raw)
        except ValueError:
            rating = 0

        if not customer_name or not content or rating not in (1, 2, 3, 4, 5):
            flash('Please fill in your name, rating, and testimonial.', 'danger')
            return redirect(url_for('testimonial_submit'))

        if len(content) > 800:
            flash('Testimonial is too long (max 800 characters).', 'danger')
            return redirect(url_for('testimonial_submit'))

        t = Testimonial(customer_name=customer_name, content=content, rating=rating, approved=False)
        db.session.add(t)
        db.session.commit()
        flash('Thank you! Your testimonial was submitted and is awaiting approval.', 'success')
        return redirect(url_for('home'))

    return render_template('testimonial_submit.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    quotes = QuoteRequest.query.order_by(QuoteRequest.created_at.desc()).all()
    testimonials = Testimonial.query.order_by(Testimonial.id.desc()).all()
    return render_template('admin.html', quotes=quotes, testimonials=testimonials)

@app.route('/admin/testimonial/<int:id>/approve', methods=['POST'])
def approve_testimonial(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    t = Testimonial.query.get_or_404(id)
    t.approved = True
    db.session.commit()
    flash('Testimonial approved.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/testimonial/<int:id>/delete', methods=['POST'])
def delete_testimonial(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    t = Testimonial.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Testimonial deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/quote/<int:id>/update', methods=['POST'])
def update_quote_status(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    quote = QuoteRequest.query.get_or_404(id)
    quote.status = request.form['status']
    db.session.commit()
    flash('Quote status updated', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

# --- Init DB ---
def init_db():
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password_hash=generate_password_hash('admin123'))
            db.session.add(admin)
            db.session.commit()

        categories = [
            'Upholstery & Interior Works',
            'Marine & Canvas Services',
            'Fabrication & Engineering',
            'Textiles & Branding',
            'Outdoor & Utility Solutions',
            'Cleaning & Maintenance'
        ]

        if Service.query.count() == 0 or Service.query.filter(Service.category.in_(categories)).count() == 0:
            db.session.query(Service).delete()
            services_data = [
                (
                    'Upholstery & Interior Works',
                    [
                        ('Upholstery & interior finishing', 'Upholstery work and interior finishing for homes and businesses.'),
                        ('Car seat covers & ceiling upholstery', 'Custom car seat covers and headliner/ceiling upholstery.'),
                        ('Foam mattresses, bed linen & carpeting', 'Foam mattresses, bed linen and carpeting solutions.')
                    ]
                ),
                (
                    'Marine & Canvas Services',
                    [
                        ('Boat furnishing & marine canvas works', 'Boat furnishing, marine upholstery and canvas works.'),
                        ('Covers, blinds & protective canvas', 'Protective covers, blinds and custom canvas.'),
                        ('Canvas repairs & new canvas manufacturing', 'Repairs and new canvas manufacturing.'),
                        ('Life rings, life jackets & life rafts', 'Marine safety items supply and servicing.')
                    ]
                ),
                (
                    'Fabrication & Engineering',
                    [
                        ('Spray painting', 'Professional spray painting services.'),
                        ('Welding', 'Welding services and repairs.'),
                        ('Metal fabrication', 'Custom metal fabrication projects.'),
                        ('Fibre glass works', 'Fibre glass works, repairs and manufacturing.')
                    ]
                ),
                (
                    'Textiles & Branding',
                    [
                        ('Banners & uniforms', 'Banners and uniforms for businesses and events.'),
                        ('T-shirt printing', 'T-shirt printing and branding.'),
                        ('PVC products', 'PVC products and custom solutions.')
                    ]
                ),
                (
                    'Outdoor & Utility Solutions',
                    [
                        ('Camping equipment', 'Camping equipment solutions and repairs.')
                    ]
                ),
                (
                    'Cleaning & Maintenance',
                    [
                        ('Cleaning services', 'Cleaning services for upholstery and related materials.'),
                        ('Fumigation services', 'Fumigation and pest control services.'),
                        ('Sewing machine repairs', 'Sewing machine repairs and maintenance.')
                    ]
                )
            ]

            for category, items in services_data:
                for name, description in items:
                    db.session.add(Service(category=category, name=name, description=description))

            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True, port=5001) # Use 5001 to avoid conflict with existing app on 5000
