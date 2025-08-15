from flask import session
import re
from difflib import get_close_matches

# Assuming get_db_connection is already imported in the main file

def handle_student_ai(question, student_id, conn):
    question = question.lower().strip()
    student_name = session.get('student_name', 'there')

    # Normalize question (remove punctuation)
    question_clean = re.sub(r'[^\w\s]', '', question)

    # Define keyword maps
    greetings = ["hi", "hello", "hey", "yo", "good morning", "good afternoon"]
    study_keywords = ["study", "quiz", "tips", "pomodoro", "exam"]
    suggest_keywords = ["suggest", "recommend", "book", "read"]
    research_keywords = ["research", "how to research", "sources", "cite", "jstor", "scholar"]
    available_keywords = ["books available", "available books", "which books"]
    borrowed_keywords = ["how many books", "borrowed", "checked out"]
    due_keywords = ["due", "deadline", "return", "when to return"]

    def contains_keywords(keywords):
        return any(k in question_clean for k in keywords)

    # === Jamaa Bot Brain ===
    if get_close_matches(question_clean, greetings, cutoff=0.8):
        return f"Hey {student_name}! 👋 I'm Jamaa Bot — your library assistant! 📚 How can I help you today?"

    elif contains_keywords(study_keywords):
        return (
            "🧠 Study Tips:\n"
            "📌 Break study time into chunks (Pomodoro technique)\n"
            "📌 Practice with past papers or flashcards\n"
            "📌 Teach concepts out loud (even to yourself!)\n"
            "📌 I can also suggest helpful books if you'd like!"
        )

    elif contains_keywords(suggest_keywords):
        books = conn.execute("SELECT title FROM books ORDER BY RANDOM() LIMIT 3").fetchall()
        if books:
            suggestions = ', '.join(b['title'] for b in books)
            return f"📘 Try these books: {suggestions}"
        return "Hmm, I couldn't find any books to suggest right now. Try again later!"

    elif contains_keywords(research_keywords):
        return (
            "🔍 Research Tips:\n"
            "- Use academic sources like Google Scholar or JSTOR\n"
            "- Start with broad keywords, then narrow\n"
            "- Use your library’s catalog (ask me!)\n"
            "- Remember to cite sources properly!"
        )

    elif contains_keywords(available_keywords):
        books = conn.execute("SELECT title FROM books WHERE available > 0").fetchall()
        titles = ', '.join(b['title'] for b in books)
        return f"📚 Available books: {titles if titles else 'No books available right now.'}"

    elif contains_keywords(borrowed_keywords):
        count = conn.execute("SELECT COUNT(*) FROM transactions WHERE member_id = ?", (student_id,)).fetchone()[0]
        return f"📦 You've borrowed {count} book(s)."

    elif contains_keywords(due_keywords):
        due = conn.execute("""
            SELECT b.title, t.due_date 
            FROM transactions t 
            JOIN books b ON t.book_id = b.id 
            WHERE t.member_id = ? AND t.status = 'approved'
        """, (student_id,)).fetchall()
        if due:
            due_list = [f"📘 {row['title']} — due on {row['due_date']}" for row in due]
            return "⏰ Books due:\n" + '\n'.join(due_list)
        return "🎉 You have no books currently due!"

    # Fallback
    return (
        f"I'm Jamaa Bot 🤖. Try asking me about:\n"
        "- 📘 What books are available?\n"
        "- 📅 Which books are due?\n"
        "- 📚 Recommend a book\n"
        "- 🧠 Study tips or research help"
    )
