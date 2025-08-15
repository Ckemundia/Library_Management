import sqlite3

def get_db_connection():
    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Create Books table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            isbn TEXT,
            category TEXT,
            available INTEGER
        )
    ''')

    # Add 'cover' column to Books
    try:
        cur.execute('ALTER TABLE books ADD COLUMN cover TEXT')
    except sqlite3.OperationalError as e:
        if "duplicate column name: cover" not in str(e):
            raise

    # Create Members table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            member_id TEXT UNIQUE,
            contact TEXT,
            password TEXT
        )
    ''')

    # Add new columns to Members table
    try:
        cur.execute('ALTER TABLE members ADD COLUMN last_visited TEXT')
    except sqlite3.OperationalError as e:
        if "duplicate column name: last_visited" not in str(e):
            raise

    try:
        cur.execute('ALTER TABLE members ADD COLUMN role TEXT DEFAULT "student"')
    except sqlite3.OperationalError as e:
        if "duplicate column name: role" not in str(e):
            raise

    # Create Transactions table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            member_id INTEGER,
            issue_date TEXT,
            return_date TEXT,
            returned INTEGER,
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (member_id) REFERENCES members(id)
        )
    ''')

    # Add 'status' column to Transactions
    try:
        cur.execute('ALTER TABLE transactions ADD COLUMN status TEXT DEFAULT "pending"')
    except sqlite3.OperationalError as e:
        if "duplicate column name: status" not in str(e):
            raise

    # Add default librarian
    cur.execute('SELECT * FROM members WHERE role = "librarian"')
    if not cur.fetchone():
        cur.execute('''
            INSERT INTO members (name, member_id, contact, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ("Admin Librarian", "lib001", "admin@example.com", "admin123", "librarian"))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
