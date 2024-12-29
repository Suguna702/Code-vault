from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import subprocess 
import google.generativeai as genai
from flask import Flask, request, render_template, jsonify

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure MySQL connection
db = pymysql.connect(host='localhost', user='root', password='guna123', database='code_editor')

def get_db_connection():
    try:
        connection = pymysql.connect(
            host='localhost',
            user='root',
            password='guna123',
            database='code_editor',
            connect_timeout=5,
            charset='utf8mb4'
        )
        return connection
    except pymysql.MySQLError as e:
        print("Error connecting to the database:", e)
        return None

# Usage in a route


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

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
                connection.commit()
                flash('Signup successful! You can now log in.', 'success')
                return redirect(url_for('login'))
            except pymysql.MySQLError as e:
                flash('Error: ' + str(e), 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection failed!', 'danger')
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

@app.route('/editor', methods=['GET', 'POST'])
@login_required
def editor():
    output = ""
    error = ""
    result = None

    temp_dir = os.path.join(os.path.expanduser("~"), "temp_code_dir")
    os.makedirs(temp_dir, exist_ok=True)

    if request.method == 'POST':
        code = request.form['code']
        language = request.form['language']

        try:
            if language == 'python':
                file_path = os.path.join(temp_dir, 'temp_code.py')
                with open(file_path, 'w') as f:
                    f.write(code)
                result = subprocess.run(['python', file_path], capture_output=True, text=True)

            elif language == 'java':
                file_path = os.path.join(temp_dir, 'HelloWorld.java')
                with open(file_path, 'w') as f:
                    f.write(code)
                compile_result = subprocess.run(['javac', file_path], capture_output=True, text=True)
                if compile_result.returncode == 0:
                    result = subprocess.run(['java', 'HelloWorld'], capture_output=True, text=True, cwd=temp_dir)
                else:
                    error = compile_result.stderr

            elif language == 'javascript':
                file_path = os.path.join(temp_dir, 'temp_code.js')
                with open(file_path, 'w') as f:
                    f.write(code)
                result = subprocess.run(['node', file_path], capture_output=True, text=True)

            if result:
                output = result.stdout
                error = result.stderr

            # If code runs successfully, store it in the database
            if error == "":
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(
                            "INSERT INTO code_submissions (user_id, language, code) VALUES (%s, %s, %s)",
                            (current_user.get_id(), language, code)
                        )
                        connection.commit()
                        flash('Code saved successfully!', 'success')
                    except pymysql.MySQLError as e:
                        flash(f"Database error: {e}", 'danger')
                    finally:
                        cursor.close()
                        connection.close()

        except Exception as e:
            error = f"An error occurred: {str(e)}"

    return render_template('editor.html', output=output, error=error)

#chatbot
@app.route('/bot')
@login_required
def bot():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    # Ensure that the API key is set and configure the client
    api_key = os.getenv("API_KEY")
    if not api_key:
        return jsonify({"error": "API_KEY environment variable is not set."}), 500

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Retrieve user message from form data
    user_message = request.form.get('message', '')

    # Generate content based on user message
    response = model.generate_content(user_message)
    print(response)
    # Assuming response has an attribute 'text' which holds the generated content
    generated_text = response.text if hasattr(response, 'text') else str(response)

    # Extract data from the generated text into a list of bullet points
    data_points = []
    lines = generated_text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("#") or line.startswith("*") or line.startswith("-"):
            data_point = line.lstrip("*-#").strip()
            if line.startswith("-"):
                data_points.append(f"- {data_point}")
            elif line.startswith("*"):
                data_points.append(f"* {data_point}")
            elif line.startswith("#"):
                data_points.append(f"# {data_point}")
    
    formatted_response = '\n'.join(lines)
    # Return JSON response with extracted data
    return jsonify({"response": formatted_response, "data_points": data_points})

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
#AIzaSyAzpts5lhPiCjT0fSwpwaaSidrmiRuinhg