from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# =========================================================
# FLASK SECRET KEY
# =========================================================

app.secret_key = "quizmaster_secret_key_2026"

DATABASE = "quiz.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    # =====================================================
    # USERS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # =====================================================
    # QUESTIONS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL
        )
    """)

    # =====================================================
    # RESULTS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =====================================================
    # ADMINS TABLE
    # =====================================================

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # =====================================================
    # DEFAULT ADMIN
    # =====================================================

    admin = conn.execute(
        "SELECT * FROM admins WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:

        hashed_password = generate_password_hash("admin123")

        conn.execute(
            """
            INSERT INTO admins (username, password)
            VALUES (?, ?)
            """,
            ("admin", hashed_password)
        )

    conn.commit()
    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (username, email, password)
                VALUES (?, ?, ?)
                """,
                (username, email, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                error="Email already registered."
            )

    return render_template("register.html")


# =========================================================
# USER LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["username"]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()

    results = conn.execute(
        """
        SELECT *
        FROM results
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    total_quizzes = len(results)

    best_score = 0
    total_percentage = 0

    for result in results:

        if result["total_questions"] > 0:

            percentage = (
                result["score"]
                / result["total_questions"]
            ) * 100

            if percentage > best_score:
                best_score = percentage

            total_percentage += percentage

    if total_quizzes > 0:
        average_score = total_percentage / total_quizzes
    else:
        average_score = 0

    conn.close()

    return render_template(
        "dashboard.html",
        user_name=session["user_name"],
        results=results,
        total_quizzes=total_quizzes,
        best_score=round(best_score),
        average_score=round(average_score)
    )


# =========================================================
# QUIZ
# =========================================================

@app.route("/quiz/<category>")
def quiz(category):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    questions = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE category = ?
        """,
        (category,)
    ).fetchall()

    conn.close()

    return render_template(
        "quiz.html",
        questions=questions,
        category=category
    )


# =========================================================
# SUBMIT QUIZ
# =========================================================

@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():

    if "user_id" not in session:
        return redirect(url_for("login"))

    category = request.form["category"]

    conn = get_db()

    questions = conn.execute(
        """
        SELECT *
        FROM questions
        WHERE category = ?
        """,
        (category,)
    ).fetchall()

    score = 0

    for question in questions:

        answer = request.form.get(
            f"question_{question['id']}"
        )

        if answer == question["correct_answer"]:
            score += 1

    total_questions = len(questions)

    # Save result
    conn.execute(
        """
        INSERT INTO results
        (user_id, category, score, total_questions)
        VALUES (?, ?, ?, ?)
        """,
        (
            session["user_id"],
            category,
            score,
            total_questions
        )
    )

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        category=category,
        score=score,
        total=total_questions
    )


# =========================================================
# USER LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop("user_id", None)
    session.pop("user_name", None)

    return redirect(url_for("home"))


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()

        admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin_login.html",
            error="Invalid admin username or password."
        )

    return render_template("admin_login.html")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_questions = conn.execute(
        "SELECT COUNT(*) FROM questions"
    ).fetchone()[0]

    total_results = conn.execute(
        "SELECT COUNT(*) FROM results"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        username=session["admin_username"],
        total_users=total_users,
        total_questions=total_questions,
        total_results=total_results
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)

    return redirect(url_for("admin_login"))


# =========================================================
# ADMIN SETTINGS
# =========================================================

@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():

    # Check admin login
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    # Get current admin
    admin = conn.execute(
        """
        SELECT *
        FROM admins
        WHERE id = ?
        """,
        (session["admin_id"],)
    ).fetchone()

    # =====================================================
    # UPDATE ADMIN
    # =====================================================

    if request.method == "POST":

        username = request.form["username"].strip()

        current_password = request.form["current_password"]

        new_password = request.form["new_password"]

        confirm_password = request.form["confirm_password"]

        # =================================================
        # CURRENT PASSWORD CHECK
        # =================================================

        if not check_password_hash(
            admin["password"],
            current_password
        ):

            conn.close()

            return render_template(
                "admin_settings.html",
                error="Current password is incorrect.",
                username=admin["username"]
            )

        # =================================================
        # NEW PASSWORD CHECK
        # =================================================

        if new_password != confirm_password:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="New passwords do not match.",
                username=admin["username"]
            )

        # =================================================
        # USERNAME CHECK
        # =================================================

        if not username:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="Username cannot be empty.",
                username=admin["username"]
            )

        # =================================================
        # DUPLICATE USERNAME CHECK
        # =================================================

        existing_admin = conn.execute(
            """
            SELECT *
            FROM admins
            WHERE username = ?
            AND id != ?
            """,
            (
                username,
                session["admin_id"]
            )
        ).fetchone()

        if existing_admin:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="This username is already taken.",
                username=admin["username"]
            )

        # =================================================
        # HASH NEW PASSWORD
        # =================================================

        hashed_password = generate_password_hash(
            new_password
        )

        # =================================================
        # UPDATE ADMIN
        # =================================================

        conn.execute(
            """
            UPDATE admins
            SET username = ?, password = ?
            WHERE id = ?
            """,
            (
                username,
                hashed_password,
                session["admin_id"]
            )
        )

        conn.commit()
        conn.close()

        # Update session
        session["admin_username"] = username

        return redirect(
            url_for("admin_dashboard")
        )

    conn.close()

    return render_template(
        "admin_settings.html",
        username=admin["username"]
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    print("===================================")
    print("        QuizMaster Started")
    print("===================================")

    print("Student Portal:")
    print("http://127.0.0.1:5000")

    print("")

    print("Admin Portal:")
    print("http://127.0.0.1:5000/admin/login")

    print("===================================")

    app.run(debug=True)