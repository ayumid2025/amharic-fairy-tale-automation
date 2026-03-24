import os
import csv
from io import TextIOWrapper
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Video, BatchJob, BatchVideo
from tasks import generate_video_task, process_batch_video_task
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET')

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
stripe.api_key = app.config['STRIPE_SECRET_KEY']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ Authentication ------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ------------------ Dashboard & Generation ------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')  # a landing page

@app.route('/dashboard')
@login_required
def dashboard():
    videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).all()
    batches = BatchJob.query.filter_by(user_id=current_user.id).order_by(BatchJob.created_at.desc()).all()
    return render_template('dashboard.html', videos=videos, batches=batches, credits=current_user.credits)

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    if current_user.credits < 1:
        return jsonify({'error': 'Insufficient credits'}), 402
    topic = request.form.get('topic')
    character = request.form.get('character')
    if not topic or not character:
        return jsonify({'error': 'Topic and character are required'}), 400
    # Deduct credit
    current_user.credits -= 1
    db.session.commit()
    task = generate_video_task.delay(topic, character, current_user.id)
    return jsonify({'task_id': task.id}), 202

@app.route('/status/<task_id>')
@login_required
def status(task_id):
    task = generate_video_task.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        video_id = task.result
        video = Video.query.get(video_id)
        if video and video.user_id == current_user.id:
            return jsonify({'state': 'SUCCESS', 'download_url': video.s3_url})
        else:
            return jsonify({'state': 'FAILURE', 'status': 'Video not found or access denied'})
    elif task.state == 'FAILURE':
        return jsonify({'state': 'FAILURE', 'status': str(task.info)})
    else:
        return jsonify({'state': task.state})

# ------------------ Batch Upload ------------------
@app.route('/batch', methods=['GET', 'POST'])
@login_required
def batch_upload():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file:
            flash('No file selected')
            return redirect(url_for('batch_upload'))
        stream = TextIOWrapper(file.stream._file, encoding='utf-8')
        reader = csv.DictReader(stream)
        rows = []
        for row in reader:
            topic = row.get('topic', '').strip()
            character = row.get('character', '').strip()
            if topic and character:
                rows.append({'topic': topic, 'character': character})
        if not rows:
            flash('CSV must contain at least one valid row with topic and character')
            return redirect(url_for('batch_upload'))
        if current_user.credits < len(rows):
            flash(f'Insufficient credits. You need {len(rows)} credits, you have {current_user.credits}.')
            return redirect(url_for('batch_upload'))
        # Deduct credits
        current_user.credits -= len(rows)
        db.session.commit()
        # Create batch job
        batch = BatchJob(
            user_id=current_user.id,
            csv_filename=file.filename,
            total=len(rows),
            status='PROCESSING'
        )
        db.session.add(batch)
        db.session.commit()
        # Create BatchVideo entries and start tasks
        for idx, row in enumerate(rows):
            bv = BatchVideo(
                batch_id=batch.id,
                row_index=idx,
                topic=row['topic'],
                character=row['character'],
                status='PENDING'
            )
            db.session.add(bv)
            db.session.commit()
            process_batch_video_task.delay(bv.id)
        return redirect(url_for('batch_status_page', batch_id=batch.id))
    return render_template('batch_upload.html')

@app.route('/batch/<int:batch_id>')
@login_required
def batch_status_page(batch_id):
    batch = BatchJob.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        abort(403)
    return render_template('batch_status.html', batch=batch)

@app.route('/batch/<int:batch_id>/status')
@login_required
def batch_status_json(batch_id):
    batch = BatchJob.query.get_or_404(batch_id)
    if batch.user_id != current_user.id:
        abort(403)
    videos = BatchVideo.query.filter_by(batch_id=batch.id).all()
    return jsonify({
        'total': batch.total,
        'completed': batch.completed,
        'failed': batch.failed,
        'status': batch.status,
        'zip_url': batch.zip_url,
        'videos': [{'topic': v.topic, 'character': v.character, 'status': v.status, 'error': v.error} for v in videos]
    })

# ------------------ Credits & Payment ------------------
@app.route('/credits')
@login_required
def credits():
    return render_template('credits.html', publishable_key=app.config['STRIPE_PUBLISHABLE_KEY'])

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json()
    price_id = data['price_id']
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='payment',
            success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('credits', _external=True),
            client_reference_id=current_user.id,
            metadata={'user_id': current_user.id}
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/payment-success')
@login_required
def payment_success():
    # Stripe will redirect here. We can optionally display a success message.
    # Credits are added via webhook.
    flash('Payment successful! Credits have been added.')
    return redirect(url_for('credits'))

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('client_reference_id')
        if user_id:
            # Map price_id to credits (you must configure prices in Stripe)
            # For simplicity, assume you have prices with metadata "credits"
            line_items = stripe.checkout.Session.list_line_items(session['id'])
            if line_items and line_items.data:
                price_id = line_items.data[0].price.id
                # You should store price-to-credits mapping in DB or config
                # Here's a hardcoded example:
                credits_map = {
                    'price_123': 10,
                    'price_456': 50,
                }
                credits = credits_map.get(price_id, 0)
                if credits:
                    with app.app_context():
                        user = User.query.get(int(user_id))
                        if user:
                            user.credits += credits
                            db.session.commit()
    return 'OK', 200

# ------------------ Download ------------------
@app.route('/download/<filename>')
@login_required
def download(filename):
    # For local files (if not using S3)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# ------------------ Run ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
