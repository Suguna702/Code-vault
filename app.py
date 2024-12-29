from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure MySQL connection
db = pymysql.connect(host='localhost', user='root', password='guna123', database='code_editor')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Model
class User:
    def __init__(self, id, username):
        self.id = id
        self.username = username

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    cursor = db.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        return User(user[0], user[1])
    return None

# Routes

@app.route('/')
def index():
    return render_template('index.html')

# Sign Up Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('signup'))

        # Use 'pbkdf2:sha256' for secure password hashing
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
            db.commit()
            flash('Signup successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except pymysql.MySQLError as e:
            flash('Error: ' + str(e), 'danger')
            return redirect(url_for('signup'))

    return render_template('signup.html')


# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = db.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1]))
            flash('Login successful!', 'success')
            return redirect(url_for('editor'))
        else:
            flash('Invalid username or password!', 'danger')

    return render_template('login.html')

# Code Editor (after login)
@app.route('/editor', methods=['GET', 'POST'])
@login_required
def editor():
    output = ""
    error = ""

    if request.method == 'POST':
        code = request.form['code']
        
        try:
            # Redirect standard output to capture print statements
            from io import StringIO
            import sys

            # Backup the standard output
            old_stdout = sys.stdout
            sys.stdout = StringIO()

            # Execute the code safely
            local_vars = {}
            exec(code, {}, local_vars)

            # Retrieve output from the redirected standard output
            output = sys.stdout.getvalue()

            # Restore the standard output
            sys.stdout = old_stdout

            # Extract the result if defined
            output += local_vars.get('result', 'Code executed successfully. No output.')

        except Exception as e:
            # Restore standard output in case of an error
            sys.stdout = old_stdout
            error = str(e)

    return render_template('editor.html', output=output, error=error)



# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
