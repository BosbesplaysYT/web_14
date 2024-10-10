from flask import Flask, render_template, request, redirect, url_for, abort, flash, session
from functools import wraps
import markdown
import os
import json
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for session management

POSTS_DIR = 'posts'
USERS_FILE = 'users.json'

# Helper function to save users to JSON
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Helper function to load users from JSON
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)
    
def load_comments_for_post(post_id):
    comments = []
    users = load_users()  # Assuming you have a function to load users from users.json
    for user_data in users.values():
        if 'comments' in user_data:
            for comment in user_data['comments']:
                if comment['post_id'] == post_id:
                    comments.append(comment['comment'])
    return comments


# Helper function for login-required routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function for admin-required routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('is_admin'):
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# Route to sign up a new user
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Password match check
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('signup'))

        users = load_users()

        # Check if the username already exists
        if username in users:
            flash('Username already exists.', 'error')
            return redirect(url_for('signup'))

        # Hash and salt the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Save new user with hashed password and default admin status
        users[username] = {
            'password': hashed_password.decode('utf-8'),
            'admin': False
        }
        save_users(users)

        flash('Signup successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        users = load_users()

        # Check if the user exists and password is correct
        if username in users and bcrypt.checkpw(password.encode('utf-8'), users[username]['password'].encode('utf-8')):
            session['logged_in'] = True
            session['username'] = username
            session['is_admin'] = users[username].get('admin', False)
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin') if session['is_admin'] else url_for('index'))
        else:
            flash('Incorrect username or password.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Admin panel for creating and managing blog posts (protected by admin access)
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
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

# Route for moderating comments in the admin panel
@app.route('/admin/comments', methods=['GET'])
def moderate_comments():
    users = load_users()
    comments = []  # To store all comments for display

    # Loop through users to gather comments
    for username, user in users.items():
        if 'comments' in user:
            for comment in user['comments']:
                comments.append({
                    'username': username,
                    'content': comment['content'],
                    'timestamp': comment['timestamp'],
                    'post_id': comment['post_id']
                })

    return render_template('moderate_comments.html', comments=comments)

# Route for deleting a comment
@app.route('/admin/delete_comment', methods=['POST'])
def delete_comment():
    username = request.form.get('username')
    post_id = int(request.form.get('post_id'))
    content = request.form.get('content')

    # Load users and remove the comment
    users = load_users()
    if username in users and 'comments' in users[username]:
        users[username]['comments'] = [
            comment for comment in users[username]['comments']
            if not (comment['post_id'] == post_id and comment['content'] == content)
        ]

    save_users(users)  # Save changes back to the JSON file
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('moderate_comments'))  # Redirect back to the moderation page


# Route for viewing a single post (with comments)
@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    # Find the post by ID
    post = None
    for filename in os.listdir(POSTS_DIR):
        if filename.startswith(f"{post_id}"):
            with open(os.path.join(POSTS_DIR, filename), 'r') as f:
                title = f.readline().strip()
                date = f.readline().strip()
                content_md = f.read()
                content_html = markdown.markdown(content_md)
                post = {
                    'id': post_id,  # Add the post id
                    'title': title,
                    'date': date,
                    'content': content_html
                }
            break
    if post is None:
        abort(404)

    # Load comments related to the post from users.json
    users = load_users()
    comments = []
    for username, user in users.items():
        if 'comments' in user:
            for comment in user['comments']:
                if comment['post_id'] == post_id:
                    comments.append({
                        'username': username,  # Use the key directly as the username
                        'content': comment['content'],
                        'timestamp': comment['timestamp']
                    })

    # Handle new comment submission
    if request.method == 'POST':
        if 'logged_in' not in session:
            flash('You must be logged in to comment.', 'error')
            return redirect(url_for('login'))

        username = session.get('username')  # Get username from session
        comment_content = request.form.get('comment')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Append the new comment to the correct user's data
        if username in users:
            users[username].setdefault('comments', []).append({
                'post_id': post_id,
                'content': comment_content,
                'timestamp': timestamp
            })
            save_users(users)
            flash('Comment added successfully!', 'success')
        else:
            flash('User not found.', 'error')

        return redirect(url_for('view_post', post_id=post_id))

    return render_template('view_single_post.html', post=post, comments=comments)



@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    comment_text = request.form.get('comment')
    username = session.get('username')  # Assuming you save the username in session upon login
    if username and comment_text:
        # Load existing users
        users = load_users()
        if username in users:
            # Add comment to user's comments list
            if 'comments' not in users[username]:
                users[username]['comments'] = []
            users[username]['comments'].append({
                'post_id': post_id,
                'comment': comment_text
            })
            save_users(users)
            flash('Comment added successfully!', 'success')
        else:
            flash('User not found. Cannot add comment.', 'error')
    else:
        flash('You must be logged in to comment.', 'error')

    return redirect(url_for('view_post', post_id=post_id))


@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    # Remove the post markdown file
    try:
        os.remove(os.path.join(POSTS_DIR, f'{post_id}.md'))
        flash('Post deleted successfully!', 'success')

        # Load users and clean up comments associated with the deleted post
        users = load_users()
        for username, user_data in users.items():
            if 'comments' in user_data:
                # Filter out comments associated with the deleted post
                user_data['comments'] = [comment for comment in user_data['comments'] if comment['post_id'] != post_id]
        
        # Save the updated users data back to the users.json file
        save_users(users)

    except FileNotFoundError:
        flash('Post not found!', 'error')
    
    return redirect(url_for('admin'))


# Home page route
@app.route('/')
def index():
    posts = load_posts()
    return render_template('view_posts.html', posts=posts)

# About page
@app.route('/about')
def about():
    flash("Deze pagina is nog onder constructie! Kom later terug!", "error")
    abort(404)

# Contact page
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
    return "Unauthorized: Incorrect credentials", 401

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")