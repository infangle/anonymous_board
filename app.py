import os
import psycopg2
from flask import Flask, render_template, request, redirect
from datetime import datetime

app = Flask(__name__)

# Get database URL from environment variables (set by Render)
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# --- Database Setup ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Threads table
    c.execute('''
    CREATE TABLE IF NOT EXISTS threads (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        upvotes INTEGER DEFAULT 0,
        downvotes INTEGER DEFAULT 0,
        tags TEXT DEFAULT ''
    )
    ''')
    
    # Comments table
    c.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id SERIAL PRIMARY KEY,
        thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        upvotes INTEGER DEFAULT 0,
        downvotes INTEGER DEFAULT 0
    )
    ''')
    
    conn.commit()
    conn.close()



# --- Word Limits ---
MAX_THREAD_WORDS = 500
MAX_COMMENT_WORDS = 150

def count_words(text):
    return len(text.strip().split())


# --- Home Page with Pagination ---
@app.route('/')
def index():
    page = int(request.args.get('page', 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM threads')
    total_threads = c.fetchone()[0]

    total_pages = math.ceil(total_threads / per_page)

    c.execute('SELECT * FROM threads ORDER BY id DESC LIMIT ? OFFSET ?', (per_page, offset))
    threads = c.fetchall()
    conn.close()

    popular_threads = get_popular_threads()
    trending_tags = get_trending_tags()

    return render_template(
        'index.html',
        threads=threads,
        popular_threads=popular_threads,
        trending_tags=trending_tags,
        page=page,
        total_pages=total_pages
    )


# --- New Thread ---
@app.route('/new', methods=['GET', 'POST'])
def new_thread():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags = request.form.get('tags', '')

        if count_words(content) > MAX_THREAD_WORDS:
            return f"Thread too long! Max {MAX_THREAD_WORDS} words.", 400

        conn = sqlite3.connect('threads.db')
        c = conn.cursor()
        c.execute(
            'INSERT INTO threads (title, content, created_at, tags) VALUES (?, ?, ?, ?)',
            (title, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tags)
        )
        conn.commit()
        conn.close()
        return redirect('/')
    return render_template('new_thread.html')


# --- Thread Detail + Comments ---
@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
def thread_detail(thread_id):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()

    if request.method == 'POST':
        content = request.form['content']
        if count_words(content) > MAX_COMMENT_WORDS:
            return f"Comment too long! Max {MAX_COMMENT_WORDS} words.", 400
        c.execute(
            'INSERT INTO comments (thread_id, content, created_at) VALUES (?, ?, ?)',
            (thread_id, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

    c.execute('SELECT * FROM threads WHERE id = ?', (thread_id,))
    thread = c.fetchone()
    c.execute('SELECT * FROM comments WHERE thread_id = ? ORDER BY id ASC', (thread_id,))
    comments = c.fetchall()

    conn.close()
    return render_template('thread_detail.html', thread=thread, comments=comments)


# --- Voting ---
@app.route('/upvote/<int:thread_id>')
def upvote(thread_id):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('UPDATE threads SET upvotes = upvotes + 1 WHERE id = ?', (thread_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/')


@app.route('/downvote/<int:thread_id>')
def downvote(thread_id):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('UPDATE threads SET downvotes = downvotes + 1 WHERE id = ?', (thread_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/')


@app.route('/comment/upvote/<int:comment_id>')
def comment_upvote(comment_id):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('UPDATE comments SET upvotes = upvotes + 1 WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/')


@app.route('/comment/downvote/<int:comment_id>')
def comment_downvote(comment_id):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('UPDATE comments SET downvotes = downvotes + 1 WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/')


# --- Tag Filter ---
@app.route('/tag/<tag>')
def tag_filter(tag):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute("SELECT * FROM threads WHERE tags LIKE ?", ('%' + tag + '%',))
    threads = c.fetchall()
    conn.close()

    popular_threads = get_popular_threads()
    trending_tags = get_trending_tags()

    return render_template(
        'index.html',
        threads=threads,
        popular_threads=popular_threads,
        trending_tags=trending_tags,
        page=1,
        total_pages=1
    )


# --- Search Threads ---
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute("""
        SELECT * FROM threads
        WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
        ORDER BY id DESC
    """, (f'%{query}%', f'%{query}%', f'%{query}%'))
    results = c.fetchall()
    conn.close()

    popular_threads = get_popular_threads()
    trending_tags = get_trending_tags()

    return render_template(
        'index.html',
        threads=results,
        popular_threads=popular_threads,
        trending_tags=trending_tags,
        page=1,
        total_pages=1
    )


# --- Helpers ---
def get_popular_threads(limit=5):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('SELECT * FROM threads ORDER BY (upvotes - downvotes) DESC LIMIT ?', (limit,))
    threads = c.fetchall()
    conn.close()
    return threads


def get_trending_tags(limit=10):
    conn = sqlite3.connect('threads.db')
    c = conn.cursor()
    c.execute('SELECT tags FROM threads WHERE tags != ""')
    all_tags = c.fetchall()
    conn.close()

    tag_count = {}
    for row in all_tags:
        for tag in row[0].split(','):
            tag = tag.strip().lower()
            if tag:
                tag_count[tag] = tag_count.get(tag, 0) + 1

    trending = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
    return [tag for tag, _ in trending[:limit]]


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
