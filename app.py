from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
# Azure SQL Database connection string
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_creator = db.Column(db.Boolean, default=False)
    media = db.relationship('Media', backref='author', lazy=True)

# Media Model
class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='media', lazy=True)
    ratings = db.relationship('Rating', backref='media', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    user = db.relationship('User', backref='comments')

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    user = db.relationship('User', backref='ratings')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    media = Media.query.order_by(Media.id.desc()).all()
    return render_template('index.html', media=media)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_creator = 'is_creator' in request.form

        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use another email.')
            return redirect(url_for('register'))

        user = User(username=username, email=email, is_creator=is_creator)
        user.password_hash = generate_password_hash(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if not current_user.is_creator:
        flash('Only creators can upload media')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            media = Media(
                title=request.form['title'],
                description=request.form['description'],
                filename=filename,
                user_id=current_user.id
            )
            db.session.add(media)
            db.session.commit()
            
            flash('Media uploaded successfully!')
            return redirect(url_for('home'))
    
    return render_template('upload.html')

@app.route('/delete/<int:media_id>', methods=['POST'])
@login_required
def delete_media(media_id):
    media = Media.query.get_or_404(media_id)
    # Only allow the creator to delete their own media
    if media.author != current_user:
        flash('You do not have permission to delete this media.')
        return redirect(url_for('home'))
    # Delete the file from the filesystem
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], media.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(media)
    db.session.commit()
    flash('Media deleted successfully!')
    return redirect(url_for('home'))

@app.route('/comment/<int:media_id>', methods=['POST'])
@login_required
def comment(media_id):
    content = request.form['content']
    comment = Comment(content=content, user_id=current_user.id, media_id=media_id)
    db.session.add(comment)
    db.session.commit()
    flash('Comment added!')
    return redirect(url_for('home'))

@app.route('/rate/<int:media_id>', methods=['POST'])
@login_required
def rate(media_id):
    value = int(request.form['rating'])
    # Prevent multiple ratings by the same user for the same media
    existing = Rating.query.filter_by(user_id=current_user.id, media_id=media_id).first()
    if existing:
        existing.value = value
        flash('Rating updated!')
    else:
        rating = Rating(value=value, user_id=current_user.id, media_id=media_id)
        db.session.add(rating)
        flash('Rating submitted!')
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 