import os
import mysql.connector
from flask import Flask, render_template, redirect, request, session
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from PyPDF2 import PdfReader
from io import BytesIO

app = Flask(__name__, static_url_path='/static')

# app = Flask(__name__, )

# Database connection details
conn = mysql.connector.connect(
    host='localhost',
    user='DB_USER_NAME',
    password='DB_PASSWORD',
    database='DB_NAME'
)

cursor = conn.cursor()

# Secret key for session
app.secret_key = 'your_secret_key'

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

    # Check if username already exists in the database
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return 'User already exists!'
    else:
        # Insert user data into the database
        try:
            sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
            val = (username, password)
            cursor.execute(sql, val)
            conn.commit()
            return redirect('/admin-login')
        except mysql.connector.Error as err:
            print(f"Error inserting user data: {err}")
            conn.rollback()
            return 'Failed to register user.'

@app.route('/admin-login', methods=['GET', 'POST'])

def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Query the database to check if username and password are correct
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        
        if user:
            session['username'] = username
            return redirect('/admin')
        else:
            return 'Invalid username or password!'
    return render_template('admin-login.html')

@app.route('/admin')
def admin():
    if 'username' in session:
        username = session['username']
        cursor.execute("SELECT * FROM job_description WHERE username = %s", (username,))
        job_descriptions = cursor.fetchall()
        return render_template('admin.html', job_descriptions=job_descriptions)
    else:
        return redirect('/admin-login')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/admin-login')

@app.route('/apply')
def apply():
    return render_template('submitResume.html')

@app.route('/submit-info', methods=['POST'])
def submit_info():
    name = request.form['name']
    email = request.form['email']
    resume = request.files['resume']

    # Read the PDF content as binary data
    resume_content = resume.read()

    # Saving to the database
    sql = "INSERT INTO job_applications (name, email, resume) VALUES (%s, %s, %s)"
    val = (name, email, resume_content)
    cursor.execute(sql, val)
    conn.commit()

    return 'Application submitted successfully!'

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

    # Get the username of the logged-in user
    username = session.get('username')

    # Saving to the database with username
    sql = "INSERT INTO job_description (job_title, job_description, required_skills, qualifications, experience, education, location, salary, employment_type, industry, username) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    val = (job_title, job_description, required_skills, qualifications, experience, education, location, salary, employment_type, industry, username)
    cursor.execute(sql, val)
    conn.commit()

    return 'Job Description submitted successfully!'

@app.route('/match-resumes', methods=['GET'])
def match_resumes():
    # Retrieve job description data
    cursor.execute("SELECT * FROM job_description")
    job_desc_data = cursor.fetchone()
    job_desc_text = ' '.join(job_desc_data[2:])

    # Retrieve all resumes
    cursor.execute("SELECT * FROM job_applications")
    resumes = cursor.fetchall()  # Fetch all results

    # Close the cursor
    cursor.close()

    # Prepare the text data for comparison
    text_data = [job_desc_text] + [PdfReader(BytesIO(resume[3])).pages[0].extract_text() for resume in resumes]

    # Calculate TF-IDF and cosine similarity
    vectorizer = TfidfVectorizer(stop_words=stopwords.words('english'))
    tfidf_matrix = vectorizer.fit_transform(text_data)
    cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    # Sort the resumes by similarity score
    sorted_resumes = sorted(zip(resumes, cosine_similarities), key=lambda x: x[1], reverse=True)

    # Return the sorted resumes
    return render_template('match-resumes.html', sorted_resumes=sorted_resumes)

if __name__ == '__main__':
    app.run(debug=True)
