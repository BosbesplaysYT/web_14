from flask import Flask, render_template, request, redirect, url_for, abort, flash, session
from functools import wraps
import markdown
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for session management

POSTS_DIR = 'posts'
ADMIN_PASSWORD = 'admin123'  # Simple hardcoded password (will change later)

# Helper function for login-required routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Incorrect password. Please try again.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Admin panel for creating and managing blog posts (protected by login)
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    posts = load_posts()  # Load existing posts for display
    if request.method == 'POST':
        # Admin logic for creating posts
        title = request.form['title']
        content_md = request.form['content']
        post_id = len(os.listdir(POSTS_DIR)) + 1
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Write post to a markdown file
        with open(os.path.join(POSTS_DIR, f'{post_id}.md'), 'w') as f:
            f.write(f"{title}\n{date}\n{content_md}")

        flash('Post created successfully!', 'success')
        return redirect(url_for('admin'))  # Redirect to admin to see the new post

    return render_template('admin_panel.html', posts=posts)

# Route for viewing a single post
@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = None
    for filename in os.listdir(POSTS_DIR):
        if filename.startswith(f"{post_id}"):
            with open(os.path.join(POSTS_DIR, filename), 'r') as f:
                title = f.readline().strip()
                date = f.readline().strip()
                content_md = f.read()
                content_html = markdown.markdown(content_md)
                post = {
                    'title': title,
                    'date': date,
                    'content': content_html
                }
            break
    if post is None:
        abort(404)
    return render_template('view_single_post.html', post=post)

# Route for deleting a post
@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    try:
        os.remove(os.path.join(POSTS_DIR, f'{post_id}.md'))
        flash('Post deleted successfully!', 'success')
    except FileNotFoundError:
        flash('Post not found!', 'error')
    return redirect(url_for('admin'))

# Home page route
@app.route('/')
def index():
    posts = load_posts()
    return render_template('view_posts.html', posts=posts)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Helper function to load posts
def load_posts():
    posts = []
    for filename in os.listdir(POSTS_DIR):
        if filename.endswith(".md"):
            post_id = int(filename.split('.')[0])
            with open(os.path.join(POSTS_DIR, filename), 'r') as f:
                title = f.readline().strip()
                date = f.readline().strip()
                content_md = f.read()
                posts.append({
                    'id': post_id,
                    'title': title,
                    'date': date,
                    'content': markdown.markdown(content_md),
                    'preview': markdown.markdown(content_md[:40] + '...')  # Add preview for homepage
                })
    posts.sort(key=lambda x: x['id'], reverse=True)
    return posts

# Error handler for unauthorized access
@app.errorhandler(401)
def unauthorized(e):
    return "Unauthorized: Incorrect password", 401

if __name__ == '__main__':
    app.run(debug=True)