from flask import Flask, render_template, request, redirect, session
from db import get_db_connection, init_db
from datetime import datetime
import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from db import get_db_connection
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask import request, jsonify, session
from jamaa_bot import handle_student_ai


# Allowed extensions for book cover uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/covers'
app.secret_key = 'your_secret_key'
init_db()

# ----------------- Student Login -----------------
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        member_id = request.form['member_id']
        password = request.form['password']

        conn = get_db_connection()
        student = conn.execute(
            'SELECT * FROM members WHERE member_id = ? AND role = "student"', (member_id,)
        ).fetchone()

        if student and student['password'] == password:
            session['student_id'] = student['id']
            session['student_name'] = student['name']

            # ✅ Update last_visited
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('UPDATE members SET last_visited = ? WHERE id = ?', (now, student['id']))
            conn.commit()
            conn.close()

            return redirect('/student/dashboard')
        else:
            conn.close()
            return render_template('student_login.html', error='Invalid credentials')

    return render_template('student_login.html')

# ----------------- Librarian Login -----------------
@app.route('/librarian/login', methods=['GET', 'POST'])
def librarian_login():
    if request.method == 'POST':
        member_id = request.form['member_id']
        password = request.form['password']

        conn = get_db_connection()
        librarian = conn.execute('SELECT * FROM members WHERE member_id = ? AND password = ? AND role = "librarian"',
                                 (member_id, password)).fetchone()
        conn.close()

        if librarian:
            session['librarian_id'] = librarian['id']
            session['librarian_name'] = librarian['name']
            return redirect('/librarian/dashboard')
        else:
            return render_template('librarian_login.html', error="Invalid credentials or not a librarian")

    return render_template('librarian_login.html')

@app.route('/librarian/logout')
def librarian_logout():
    session.pop('librarian_id', None)
    session.pop('librarian_name', None)
    return redirect('/librarian/login')

@app.route('/student/logout')
def student_logout():
    session.clear()
    return redirect('/student/login')

# ----------------- Home & Dashboard -----------------
@app.route('/')
def index():
    return redirect('/login')

@app.route('/librarian/dashboard')
def librarian_dashboard():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    conn = get_db_connection()
    books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    members = conn.execute('SELECT COUNT(*) FROM members WHERE role = "student"').fetchone()[0]
    pending = conn.execute('SELECT COUNT(*) FROM transactions WHERE status = "pending"').fetchone()[0]
    conn.close()

    summary = {
        'books': books,
        'members': members,
        'pending': pending
    }

    return render_template('librarian_dashboard.html', name=session.get('librarian_name'), summary=summary)

@app.route('/login')
def login_choice():
    return render_template('login_choice.html')

# ----------------- Book Management -----------------
@app.route('/books', methods=['GET'])
def books():
    conn = get_db_connection()
    cur = conn.cursor()

    search = request.args.get('search', '')

    if search:
        query = """
        SELECT * FROM books
        WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?
        ORDER BY id DESC
        """
        like = f"%{search}%"
        cur.execute(query, (like, like, like))
    else:
        cur.execute("SELECT * FROM books ORDER BY id DESC")

    books = cur.fetchall()
    conn.close()

    return render_template('books.html', books=books)


@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form['title']
    author = request.form['author']
    isbn = request.form['isbn']
    category = request.form['category']
    cover_filename = None

    if 'cover' in request.files:
        file = request.files['cover']
        if file and allowed_file(file.filename):
            cover_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], cover_filename))

    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ Check if ISBN already exists
    cur.execute("SELECT * FROM books WHERE isbn = ?", (isbn,))
    existing_book = cur.fetchone()

    if existing_book:
        conn.close()
        flash('❌ A book with this ISBN already exists.', 'danger')
        return redirect(url_for('books'))

    # ✅ If ISBN is unique, insert the book
    cur.execute("""
        INSERT INTO books (title, author, isbn, category, available, cover)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, author, isbn, category, 1, cover_filename))

    conn.commit()
    conn.close()

    flash('✅ Book added successfully!', 'success')
    return redirect(url_for('books'))

# ----------------- Member Management -----------------
@app.route('/members')
def members():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    conn = get_db_connection()
    members = conn.execute('SELECT * FROM members').fetchall()
    conn.close()
    return render_template('members.html', members=members)

@app.route('/add_member', methods=['POST'])
def add_member():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    name = request.form['name']
    member_id = request.form['member_id']
    contact = request.form['contact']
    password = request.form.get('password')

    conn = get_db_connection()

    # Check for duplicate member_id
    existing = conn.execute('SELECT * FROM members WHERE member_id = ?', (member_id,)).fetchone()

    if existing:
        conn.close()
        flash("❗ Member ID already exists. Please use a unique ID.", "danger")
        return redirect('/members')  # Or wherever your form is

    # Insert student or librarian
    if password:
        conn.execute(
            'INSERT INTO members (name, member_id, contact, password, role) VALUES (?, ?, ?, ?, "student")',
            (name, member_id, contact, password)
        )
    else:
        conn.execute(
            'INSERT INTO members (name, member_id, contact, role) VALUES (?, ?, ?, "librarian")',
            (name, member_id, contact)
        )

    conn.commit()
    conn.close()
    flash("✅ Member added successfully!", "success")
    return redirect('/members')


# ----------------- Transactions -----------------
@app.route('/transactions')
def transactions():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT t.*, b.title, m.name
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        ORDER BY t.id DESC
    ''').fetchall()

    books = conn.execute('SELECT * FROM books WHERE available = 1').fetchall()
    members = conn.execute('SELECT * FROM members WHERE role = "student"').fetchall()
    conn.close()

    return render_template('transactions.html',
                           transactions=transactions,
                           books=books,
                           members=members)

@app.route('/issue_book', methods=['POST'])
def issue_book():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    book_id = request.form['book_id']
    member_id = request.form['member_id']
    issue_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    conn.execute('INSERT INTO transactions (book_id, member_id, issue_date, returned) VALUES (?, ?, ?, 0)',
                 (book_id, member_id, issue_date))
    conn.execute('UPDATE books SET available = 0 WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()
    return redirect('/transactions')

@app.route('/return_book/<int:transaction_id>')
def return_book(transaction_id):
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    return_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    transaction = conn.execute('SELECT book_id FROM transactions WHERE id = ?', (transaction_id,)).fetchone()
    conn.execute('UPDATE transactions SET return_date = ?, returned = 1 WHERE id = ?',
                 (return_date, transaction_id))
    conn.execute('UPDATE books SET available = 1 WHERE id = ?', (transaction['book_id'],))
    conn.commit()
    conn.close()
    return redirect('/transactions')

@app.route('/approve_request', methods=['POST'])
def approve_request():
    if 'librarian_id' not in session:
        return redirect('/librarian/login')

    txn_id = request.form['transaction_id']
    issue_date = datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    cur = conn.cursor()

    # Update status and issue date
    cur.execute('''
        UPDATE transactions
        SET status = 'issued', issue_date = ?
        WHERE id = ?
    ''', (issue_date, txn_id))

    # Reduce book count by 1
    cur.execute('''
        UPDATE books
        SET available = available - 1
        WHERE id = (SELECT book_id FROM transactions WHERE id = ?)
    ''', (txn_id,))

    conn.commit()
    conn.close()

    return redirect('/transactions')


# ----------------- Student Dashboard -----------------
@app.route('/student/dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect('/student/login')

    conn = get_db_connection()
    student_id = session['student_id']

    # ✅ Get the full student row
    student = conn.execute('SELECT * FROM members WHERE id = ?', (student_id,)).fetchone()

    # Recent transactions
    transactions = conn.execute('''
        SELECT t.*, b.title FROM transactions t
        JOIN books b ON t.book_id = b.id
        WHERE t.member_id = ?
        ORDER BY t.id DESC
    ''', (student_id,)).fetchall()

    # Book requests
    requests = conn.execute('''
        SELECT t.status, b.title FROM transactions t
        JOIN books b ON t.book_id = b.id
        WHERE t.member_id = ?
        ORDER BY t.id DESC
    ''', (student_id,)).fetchall()

    summary = {
        'requested_count': len(requests),
        'pending_count': sum(1 for r in requests if r['status'] == 'pending'),
        'approved_count': sum(1 for r in requests if r['status'] == 'approved'),
    }

    conn.close()

    return render_template('student_dashboard.html',
                           student=student,  # ✅ Now you can use student.name, student.last_visited, etc.
                           transactions=transactions,
                           requests=requests,
                           summary=summary)

@app.route('/student/request_book', methods=['POST'])
def request_book():
    if 'student_id' not in session:
        return redirect('/student/login')

    book_id = request.form['book_id']
    conn = get_db_connection()
    cur = conn.cursor()

    # Insert a new transaction with pending status
    cur.execute('''
        INSERT INTO transactions (book_id, member_id, issue_date, return_date, returned, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (book_id, session['student_id'], None, None, 0, 'pending'))

    conn.commit()
    conn.close()

    return redirect('/student/dashboard?message=Book+requested+successfully.+Awaiting+approval.')

@app.route('/student/books')
def student_books():
    if 'student_id' not in session:
        return redirect('/student/login')

    search = request.args.get('search', '')
    conn = get_db_connection()

    if search:
        like = f"%{search}%"
        books = conn.execute('''
            SELECT * FROM books
            WHERE available > 0 AND (
                title LIKE ? OR author LIKE ? OR isbn LIKE ?
            )
        ''', (like, like, like)).fetchall()
    else:
        books = conn.execute('SELECT * FROM books WHERE available > 0').fetchall()

    conn.close()
    return render_template('student_books.html', name=session['student_name'], books=books, search=search)

#------------------AI ASSISTANT-----------------
@app.route('/student/ai', methods=['POST'])
def student_ai():
    if 'student_id' not in session:
        return jsonify({'answer': "Please log in first."})

    data = request.get_json()
    question = data.get('question', '')
    student_id = session['student_id']
    conn = get_db_connection()

    answer = handle_student_ai(question, student_id, conn)

    conn.close()
    return jsonify({'answer': answer})

#--------------------change password--------------
@app.route('/student/change_password', methods=['GET', 'POST'])
def change_student_password():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student_id = session['student_id']
    conn = get_db_connection()

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        user = conn.execute("SELECT password FROM members WHERE id = ?", (student_id,)).fetchone()

        if not user or user['password'] != old_password:
            flash("Current password is incorrect.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        elif new_password == old_password:
            flash("New password cannot be the same as the old one.", "warning")
        else:
            conn.execute("UPDATE members SET password = ? WHERE id = ?", (new_password, student_id))
            conn.commit()
            conn.close()
            flash("Password changed successfully!", "success")
            return render_template('change_password.html')  # ⚠️ STAY on this page!

    conn.close()
    return render_template('change_password.html')

# ----------------- Run Server -----------------
if __name__ == '__main__':
    app.run(debug=True)
