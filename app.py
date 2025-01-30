import os
from flask import Flask, render_template, redirect, request, session, flash
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from PyPDF2 import PdfReader
from io import BytesIO
from mysql.connector import pooling, Error

# Flask App Initialization
app = Flask(__name__, static_url_path='/static')
app.secret_key = 'your_secret_key'

# Database Configuration and Connection Pooling
db_config = {
    "host": "localhost",
    "user": "DB_USERNAME",
    "password": "DB_PASSWORD",
    "database": "DB_NAME"
}
try:
    connection_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)
except Error as e:
    print(f"Error setting up connection pool: {e}")
    exit()

# Utility Function to Get Database Connection
def get_db_connection():
    try:
        return connection_pool.get_connection()
    except Error as e:
        print(f"Error getting connection from pool: {e}")
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET'])
def show_register_page():
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    if not conn:
        return 'Database connection error. Please try again later.'

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('User already exists!', 'error')
            return redirect('/register')
        else:
            sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
            cursor.execute(sql, (username, password))
            conn.commit()
            flash('Registration successful!', 'success')
            return redirect('/admin-login')
    except Error as e:
        print(f"Database error during registration: {e}")
        flash('Failed to register user. Please try again.', 'error')
    finally:
        cursor.close()
        conn.close()


@app.route('/admin-login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        if not conn:
            return 'Database connection error. Please try again later.'

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()
            if user:
                session['username'] = username
                return redirect('/admin')
            else:
                flash('Invalid username or password!', 'error')
                return redirect('/admin-login')
        except Error as e:
            print(f"Database error during login: {e}")
            flash('Error logging in. Please try again later.', 'error')
        finally:
            cursor.close()
            conn.close()
    return render_template('admin-login.html')


@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect('/admin-login')

    conn = get_db_connection()
    if not conn:
        return 'Database connection error. Please try again later.'

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_description WHERE username = %s", (session['username'],))
        job_descriptions = cursor.fetchall()
        return render_template('admin.html', job_descriptions=job_descriptions)
    except Error as e:
        print(f"Database error fetching job descriptions: {e}")
        return 'Failed to fetch job descriptions.'
    finally:
        cursor.close()
        conn.close()


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Logged out successfully!', 'info')
    return redirect('/admin-login')


@app.route('/apply')
def apply():
    return render_template('submitResume.html')


@app.route('/submit-info', methods=['POST'])
def submit_info():
    name = request.form['name']
    email = request.form['email']
    resume = request.files['resume']
    resume_content = resume.read()

    conn = get_db_connection()
    if not conn:
        return 'Database connection error. Please try again later.'

    try:
        cursor = conn.cursor()
        sql = "INSERT INTO job_applications (name, email, resume) VALUES (%s, %s, %s)"
        cursor.execute(sql, (name, email, resume_content))
        conn.commit()
        flash('Application submitted successfully!', 'success')
    except Error as e:
        print(f"Database error submitting job application: {e}")
        flash('Failed to submit application. Please try again.', 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect('/apply')


@app.route('/submit-description', methods=['POST'])
def submit_description():
    job_title = request.form['job_title']
    job_description = request.form['job_description']
    required_skills = request.form['required_skills']
    qualifications = request.form['qualifications']
    experience = request.form['experience']
    education = request.form['education']
    location = request.form['location']
    salary = request.form['salary']
    employment_type = request.form['employment_type']
    industry = request.form['industry']

    conn = get_db_connection()
    if not conn:
        return 'Database connection error. Please try again later.'

    try:
        cursor = conn.cursor()
        sql = """INSERT INTO job_description 
                 (job_title, job_description, required_skills, qualifications, experience, education, location, salary, employment_type, industry, username)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (job_title, job_description, required_skills, qualifications, experience, education, location, salary, employment_type, industry, session.get('username')))
        conn.commit()
        flash('Job Description submitted successfully!', 'success')
    except Error as e:
        print(f"Database error submitting job description: {e}")
        flash('Failed to submit job description. Please try again.', 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect('/admin')


@app.route('/match-resumes', methods=['GET'])
def match_resumes():
    conn = get_db_connection()
    if not conn:
        return 'Database connection error. Please try again later.'

    try:
        # Fetch job descriptions
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_description")
        job_desc_data = cursor.fetchone()
        if not job_desc_data:
            return 'No job descriptions found.'
        job_desc_text = ' '.join(job_desc_data[2:])
        cursor.close()  # Close the cursor to avoid unread results

        # Fetch resumes using a new cursor
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_applications")
        resumes = cursor.fetchall()

        # Process text data for similarity calculation
        text_data = [job_desc_text] + [PdfReader(BytesIO(resume[3])).pages[0].extract_text() for resume in resumes]
        vectorizer = TfidfVectorizer(stop_words=stopwords.words('english'))
        tfidf_matrix = vectorizer.fit_transform(text_data)
        cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        # Sort resumes by similarity score
        sorted_resumes = sorted(zip(resumes, cosine_similarities), key=lambda x: x[1], reverse=True)

        return render_template('match-resumes.html', sorted_resumes=sorted_resumes)
    except Error as e:
        print(f"Database error during resume matching: {e}")
        return 'Failed to match resumes.'
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
