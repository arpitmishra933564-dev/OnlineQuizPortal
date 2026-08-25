from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# =========================================================
# CONFIGURATION
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
# DATABASE INITIALIZATION + MIGRATION
# =========================================================

def init_db():

    conn = get_db()

    # -----------------------------------------------------
    # USERS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Check existing columns
    user_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    # IMPORTANT:
    # Existing quiz.db may not have username column.
    # Add it automatically.
    if "username" not in user_columns:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN username TEXT
        """)

        # Existing students ke liye email ko username
        # ke roop mein use karenge.
        conn.execute("""
            UPDATE users
            SET username = email
            WHERE username IS NULL
        """)

    # -----------------------------------------------------
    # QUESTIONS TABLE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # RESULTS TABLE
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ADMINS TABLE
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # DEFAULT ADMIN
    # -----------------------------------------------------

    admin = conn.execute("""
        SELECT *
        FROM admins
        WHERE username = ?
    """, ("admin",)).fetchone()

    if admin is None:

        hashed_password = generate_password_hash(
            "admin123"
        )

        conn.execute("""
            INSERT INTO admins
            (username, password)
            VALUES (?, ?)
        """, (
            "admin",
            hashed_password
        ))

    conn.commit()
    conn.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# STUDENT REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not username or not email or not password:

            return render_template(
                "register.html",
                error="Please fill all fields."
            )

        hashed_password = generate_password_hash(
            password
        )

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO users
                (username, email, password)
                VALUES (?, ?, ?)
            """, (
                username,
                email,
                hashed_password
            ))

            conn.commit()
            conn.close()

            return redirect(
                url_for("login")
            )

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                error="Email is already registered."
            )

    return render_template("register.html")


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["user_name"] = (
                user["username"]
                if user["username"]
                else user["email"]
            )

            session["user_email"] = user["email"]

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    conn = get_db()

    results = conn.execute("""
        SELECT *
        FROM results
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        session["user_id"],
    )).fetchall()

    total_quizzes = len(results)

    best_score = 0
    total_percentage = 0

    for result in results:

        if result["total_questions"] > 0:

            percentage = (
                result["score"]
                / result["total_questions"]
            ) * 100

            total_percentage += percentage

            if percentage > best_score:
                best_score = percentage

    if total_quizzes > 0:

        average_score = (
            total_percentage
            / total_quizzes
        )

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
# START QUIZ
# =========================================================

@app.route("/quiz/<category>")
def quiz(category):

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    conn = get_db()

    questions = conn.execute("""
        SELECT *
        FROM questions
        WHERE category = ?
        ORDER BY id
    """, (
        category,
    )).fetchall()

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
        return redirect(
            url_for("login")
        )

    category = request.form.get(
        "category",
        ""
    )

    conn = get_db()

    questions = conn.execute("""
        SELECT *
        FROM questions
        WHERE category = ?
        ORDER BY id
    """, (
        category,
    )).fetchall()

    score = 0

    for question in questions:

        answer = request.form.get(
            f"question_{question['id']}"
        )

        if answer == question["correct_answer"]:
            score += 1

    total_questions = len(questions)

    # Save result
    conn.execute("""
        INSERT INTO results
        (
            user_id,
            category,
            score,
            total_questions
        )
        VALUES (?, ?, ?, ?)
    """, (
        session["user_id"],
        category,
        score,
        total_questions
    ))

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        category=category,
        score=score,
        total=total_questions
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)

    return redirect(
        url_for("home")
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (
            email,
        )).fetchone()

        conn.close()

        if user is None:

            return render_template(
                "forgot_password.html",
                error="No account found with this email."
            )

        return redirect(
            url_for(
                "reset_password",
                email=email
            )
        )

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# RESET STUDENT PASSWORD
# =========================================================

@app.route(
    "/reset-password/<email>",
    methods=["GET", "POST"]
)
def reset_password(email):

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (
        email,
    )).fetchone()

    if user is None:

        conn.close()

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not new_password or not confirm_password:

            conn.close()

            return render_template(
                "reset_password.html",
                email=email,
                error="Please fill all fields."
            )

        if new_password != confirm_password:

            conn.close()

            return render_template(
                "reset_password.html",
                email=email,
                error="Passwords do not match."
            )

        hashed_password = generate_password_hash(
            new_password
        )

        conn.execute("""
            UPDATE users
            SET password = ?
            WHERE email = ?
        """, (
            hashed_password,
            email
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("login")
        )

    conn.close()

    return render_template(
        "reset_password.html",
        email=email
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        admin = conn.execute("""
            SELECT *
            FROM admins
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        conn.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["id"]

            session["admin_username"] = (
                admin["username"]
            )

            return redirect(
                url_for("admin_dashboard")
            )

        return render_template(
            "admin_login.html",
            error="Invalid admin username or password."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

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
# ADMIN RESULTS
# =========================================================

@app.route("/admin/results")
def admin_results():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    results = conn.execute("""
        SELECT
            results.id AS id,
            users.username AS username,
            users.email AS email,
            results.category AS category,
            results.score AS score,
            results.total_questions AS total_questions,
            results.date AS date
        FROM results
        LEFT JOIN users
        ON results.user_id = users.id
        ORDER BY results.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_results.html",
        results=results
    )


# =========================================================
# DELETE RESULT
# =========================================================

@app.route(
    "/admin/results/delete/<int:result_id>",
    methods=["POST"]
)
def delete_result(result_id):

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute("""
        DELETE FROM results
        WHERE id = ?
    """, (
        result_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_results")
    )


# =========================================================
# MANAGE QUESTIONS
# =========================================================

@app.route("/admin/questions")
def manage_questions():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    questions = conn.execute("""
        SELECT *
        FROM questions
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "manage_questions.html",
        questions=questions
    )


# =========================================================
# ADD QUESTION
# =========================================================

@app.route(
    "/admin/questions/add",
    methods=["GET", "POST"]
)
def add_question():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        question = request.form.get(
            "question",
            ""
        ).strip()

        option_a = request.form.get(
            "option_a",
            ""
        ).strip()

        option_b = request.form.get(
            "option_b",
            ""
        ).strip()

        option_c = request.form.get(
            "option_c",
            ""
        ).strip()

        option_d = request.form.get(
            "option_d",
            ""
        ).strip()

        correct_answer = request.form.get(
            "correct_answer",
            ""
        ).strip()

        if not all([
            category,
            question,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer
        ]):

            return render_template(
                "add_question.html",
                error="Please fill all fields."
            )

        conn = get_db()

        conn.execute("""
            INSERT INTO questions
            (
                category,
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            category,
            question,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("manage_questions")
        )

    return render_template(
        "add_question.html"
    )


# =========================================================
# EDIT QUESTION
# =========================================================

@app.route(
    "/admin/questions/edit/<int:question_id>",
    methods=["GET", "POST"]
)
def edit_question(question_id):

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    question = conn.execute("""
        SELECT *
        FROM questions
        WHERE id = ?
    """, (
        question_id,
    )).fetchone()

    if question is None:

        conn.close()

        return redirect(
            url_for("manage_questions")
        )

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        question_text = request.form.get(
            "question",
            ""
        ).strip()

        option_a = request.form.get(
            "option_a",
            ""
        ).strip()

        option_b = request.form.get(
            "option_b",
            ""
        ).strip()

        option_c = request.form.get(
            "option_c",
            ""
        ).strip()

        option_d = request.form.get(
            "option_d",
            ""
        ).strip()

        correct_answer = request.form.get(
            "correct_answer",
            ""
        ).strip()

        conn.execute("""
            UPDATE questions
            SET
                category = ?,
                question = ?,
                option_a = ?,
                option_b = ?,
                option_c = ?,
                option_d = ?,
                correct_answer = ?
            WHERE id = ?
        """, (
            category,
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer,
            question_id
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("manage_questions")
        )

    conn.close()

    return render_template(
        "edit_question.html",
        question=question
    )


# =========================================================
# DELETE QUESTION
# =========================================================

@app.route(
    "/admin/questions/delete/<int:question_id>",
    methods=["POST"]
)
def delete_question(question_id):

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    conn.execute("""
        DELETE FROM questions
        WHERE id = ?
    """, (
        question_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("manage_questions")
    )


# =========================================================
# ADMIN SETTINGS
# =========================================================

@app.route(
    "/admin/settings",
    methods=["GET", "POST"]
)
def admin_settings():

    if "admin_id" not in session:
        return redirect(
            url_for("admin_login")
        )

    conn = get_db()

    admin = conn.execute("""
        SELECT *
        FROM admins
        WHERE id = ?
    """, (
        session["admin_id"],
    )).fetchone()

    if admin is None:

        conn.close()

        session.pop("admin_id", None)
        session.pop("admin_username", None)

        return redirect(
            url_for("admin_login")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Current password check
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

        if not username:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="Username cannot be empty.",
                username=admin["username"]
            )

        if not new_password:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="New password cannot be empty.",
                username=admin["username"]
            )

        if new_password != confirm_password:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="New passwords do not match.",
                username=admin["username"]
            )

        # Check duplicate username
        existing_admin = conn.execute("""
            SELECT *
            FROM admins
            WHERE username = ?
            AND id != ?
        """, (
            username,
            session["admin_id"]
        )).fetchone()

        if existing_admin:

            conn.close()

            return render_template(
                "admin_settings.html",
                error="Username already exists.",
                username=admin["username"]
            )

        hashed_password = generate_password_hash(
            new_password
        )

        conn.execute("""
            UPDATE admins
            SET
                username = ?,
                password = ?
            WHERE id = ?
        """, (
            username,
            hashed_password,
            session["admin_id"]
        ))

        conn.commit()
        conn.close()

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
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    print()
    print("==========================================")
    print("          QUIZMASTER STARTED")
    print("==========================================")

    print()
    print("Website:")
    print("http://127.0.0.1:5000")

    print()
    print("Student Login:")
    print("http://127.0.0.1:5000/login")

    print()
    print("Admin Login:")
    print("http://127.0.0.1:5000/admin/login")

    print()
    print("Default Admin:")
    print("Username: admin")
    print("Password: admin123")

    print()
    print("==========================================")

    app.run(debug=True)