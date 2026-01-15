from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text
from datetime import datetime
import os
import uuid
import hashlib
import secrets
import base64
import smtplib
from email.message import EmailMessage
import urllib.parse
import urllib.request
import re
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
app.config['RESET_TOKEN_TTL_SECONDS'] = 60 * 30

db = SQLAlchemy(app)

ALLOWED_UPLOAD_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.pdf'}

def _allowed_upload(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_UPLOAD_EXTENSIONS

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def _send_reset_email(to_email: str, reset_url: str) -> bool:
    smtp_host = os.environ.get('SMTP_HOST')
    if not smtp_host:
        return False
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    smtp_use_tls = os.environ.get('SMTP_USE_TLS', '1') == '1'
    from_email = os.environ.get('FROM_EMAIL') or smtp_user
    if not from_email:
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Password Reset'
    msg['From'] = from_email
    msg['To'] = to_email
    msg.set_content(
        "You requested a password reset.\n\n"
        f"Reset your password using this link:\n{reset_url}\n\n"
        "If you did not request this, ignore this email."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)
    return True

def _send_reset_sms(to_phone: str, reset_url: str) -> bool:
    sid = os.environ.get('TWILIO_ACCOUNT_SID')
    token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_FROM_NUMBER')
    if not sid or not token or not from_number:
        return False

    body = f"Beatwell password reset: {reset_url}"
    data = urllib.parse.urlencode({
        'From': from_number,
        'To': to_phone,
        'Body': body,
    }).encode('utf-8')

    req = urllib.request.Request(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        data=data,
        method='POST'
    )
    auth = base64.b64encode(f'{sid}:{token}'.encode('utf-8')).decode('ascii')
    req.add_header('Authorization', 'Basic ' + auth)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False

# --- Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)

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

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        method = (request.form.get('method') or 'email').strip().lower()

        user = None
        if identifier:
            user = User.query.filter_by(username=identifier).first()
            if not user:
                user = User.query.filter_by(email=identifier).first()
            if not user:
                user = User.query.filter_by(phone_number=identifier).first()

        flash('If the account exists, reset instructions have been sent.', 'info')

        if not user:
            return redirect(url_for('forgot_password'))

        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        ttl_seconds = int(app.config.get('RESET_TOKEN_TTL_SECONDS', 1800))
        from datetime import timedelta
        expires_at = datetime.utcnow().replace(microsecond=0) + timedelta(seconds=ttl_seconds)

        reset = PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at, used_at=None)
        db.session.add(reset)
        db.session.commit()

        reset_url = url_for('reset_password', token=token, _external=True)
        sent = False
        if method == 'sms':
            if user.phone_number:
                sent = _send_reset_sms(user.phone_number, reset_url)
        else:
            if user.email:
                sent = _send_reset_email(user.email, reset_url)

        if not sent and app.debug:
            flash(f'DEBUG reset link: {reset_url}', 'warning')

        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_hash = _hash_token(token)
    reset = PasswordReset.query.filter_by(token_hash=token_hash).first()
    if not reset or reset.used_at is not None or reset.expires_at < datetime.utcnow():
        flash('This password reset link is invalid or expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('reset_password', token=token))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('reset_password', token=token))

        user = User.query.get(reset.user_id)
        if not user:
            flash('Account not found.', 'danger')
            return redirect(url_for('forgot_password'))

        user.password_hash = generate_password_hash(password)
        reset.used_at = datetime.utcnow()
        db.session.commit()
        flash('Password updated. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_user = User.query.get(session.get('user_id'))
    quotes = QuoteRequest.query.order_by(QuoteRequest.created_at.desc()).all()
    testimonials = Testimonial.query.order_by(Testimonial.id.desc()).all()
    return render_template('admin.html', quotes=quotes, testimonials=testimonials, admin_user=admin_user)

@app.route('/admin/profile', methods=['POST'])
def update_admin_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(session.get('user_id'))
    email = (request.form.get('email') or '').strip()
    phone = (request.form.get('phone_number') or '').strip()

    if email:
        if len(email) > 255 or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('admin_dashboard'))

    if phone:
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        if len(cleaned) > 30 or not re.fullmatch(r'^\+?\d{6,30}$', cleaned):
            flash('Please enter a valid phone number (digits, optional +).', 'danger')
            return redirect(url_for('admin_dashboard'))
        phone = cleaned

    user.email = email or None
    user.phone_number = phone or None
    db.session.commit()
    flash('Admin contact details updated.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/change-password', methods=['POST'])
def change_admin_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get_or_404(session.get('user_id'))
    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('admin_dashboard'))

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

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

        if db.engine.dialect.name == 'sqlite':
            cols = db.session.execute(text("PRAGMA table_info(user)")).fetchall()
            existing = {c[1] for c in cols}
            if 'email' not in existing:
                db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(255)"))
            if 'phone_number' not in existing:
                db.session.execute(text("ALTER TABLE user ADD COLUMN phone_number VARCHAR(30)"))
            db.session.commit()

        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
        admin_reset_password_on_start = os.environ.get('ADMIN_RESET_PASSWORD_ON_START', '0') == '1'

        existing_admin = User.query.filter_by(username=admin_username).first()
        if not existing_admin:
            password_hash = generate_password_hash(admin_password or 'admin123')
            if admin_password_hash:
                password_hash = admin_password_hash
            admin = User(
                username=admin_username,
                password_hash=password_hash,
                email=os.environ.get('ADMIN_EMAIL'),
                phone_number=os.environ.get('ADMIN_PHONE')
            )
            db.session.add(admin)
            db.session.commit()
        else:
            admin = existing_admin
            if not admin.email and os.environ.get('ADMIN_EMAIL'):
                admin.email = os.environ.get('ADMIN_EMAIL')
            if not admin.phone_number and os.environ.get('ADMIN_PHONE'):
                admin.phone_number = os.environ.get('ADMIN_PHONE')
            if admin_reset_password_on_start:
                if admin_password:
                    admin.password_hash = generate_password_hash(admin_password)
                if admin_password_hash:
                    admin.password_hash = admin_password_hash
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
