from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# ============================================================
# SCREENSHOT WEBSITE
# Flask + Neon PostgreSQL
# ============================================================

app = Flask(__name__)

# Store SECRET_KEY in Vercel later. A fallback is provided for local testing.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "screenshot-secret-key-change-this"
)


# ============================================================
# ALLOWED IMAGE TYPES
# ============================================================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ============================================================
# DATABASE CONNECTION - NEON POSTGRESQL
# ============================================================

def get_db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set."
        )

    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            comment TEXT,
            filename TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    # These ALTER statements make the code friendlier if a screenshots
    # table was created during an earlier version of the project.
    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS filename TEXT
    """)

    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS image_url TEXT
    """)

    db.commit()
    cursor.close()
    db.close()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            screenshots.id,
            screenshots.user_id,
            screenshots.title,
            screenshots.comment,
            screenshots.filename,
            screenshots.image_url,
            screenshots.created_at,
            users.username
        FROM screenshots
        JOIN users
            ON screenshots.user_id = users.id
        ORDER BY screenshots.created_at DESC
    """)

    screenshots = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "index.html",
        screenshots=screenshots
    )


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (
                    username,
                    password_hash
                )
                VALUES (%s, %s)
            """, (
                username,
                password_hash
            ))

            db.commit()

        except IntegrityError:
            db.rollback()
            cursor.close()
            db.close()

            flash("That username is already taken.")
            return redirect(url_for("register"))

        cursor.close()
        db.close()

        flash("Account created successfully!")
        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Login successful!")
            return redirect(url_for("index"))

        flash("Incorrect username or password.")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("index"))


# ============================================================
# UPLOAD SCREENSHOT
# ============================================================

@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "user_id" not in session:
        flash("You must login before uploading.")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"].strip()
        comment = request.form["comment"].strip()
        image = request.files.get("image")

        if not title:
            flash("Please enter a title.")
            return redirect(url_for("upload"))

        if not image or image.filename == "":
            flash("Please choose an image.")
            return redirect(url_for("upload"))

        if not allowed_file(image.filename):
            flash(
                "Invalid image type. "
                "Use PNG, JPG, JPEG, GIF, or WEBP."
            )
            return redirect(url_for("upload"))

        original_filename = secure_filename(image.filename)
        extension = original_filename.rsplit(".", 1)[1].lower()
        filename = str(uuid.uuid4()) + "." + extension

        # ----------------------------------------------------
        # IMPORTANT:
        # Vercel cannot permanently store uploaded files in the
        # application's local filesystem.
        #
        # The next step is to upload `image` to Neon Object
        # Storage (or another object-storage provider) and obtain
        # its public URL.
        # ----------------------------------------------------

        image_url = None

        # We deliberately DO NOT call image.save(...) here.
        # That prevents the old Vercel read-only filesystem error.

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO screenshots (
                user_id,
                title,
                comment,
                filename,
                image_url
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session["user_id"],
            title,
            comment,
            filename,
            image_url
        ))

        db.commit()

        cursor.close()
        db.close()

        flash(
            "Screenshot information saved. "
            "Image storage still needs to be connected."
        )

        return redirect(url_for("index"))

    return render_template("upload.html")


# ============================================================
# EDIT SCREENSHOT
# ============================================================

@app.route(
    "/edit/<int:screenshot_id>",
    methods=["GET", "POST"]
)
def edit(screenshot_id):

    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM screenshots
        WHERE id = %s
    """, (screenshot_id,))

    screenshot = cursor.fetchone()

    if screenshot is None:
        cursor.close()
        db.close()

        flash("Screenshot not found.")
        return redirect(url_for("index"))

    if screenshot["user_id"] != session["user_id"]:
        cursor.close()
        db.close()

        flash("You can only edit your own screenshots.")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form["title"].strip()
        comment = request.form["comment"].strip()

        if not title:
            cursor.close()
            db.close()

            flash("Title cannot be empty.")
            return redirect(
                url_for(
                    "edit",
                    screenshot_id=screenshot_id
                )
            )

        cursor.execute("""
            UPDATE screenshots
            SET title = %s,
                comment = %s
            WHERE id = %s
        """, (
            title,
            comment,
            screenshot_id
        ))

        db.commit()

        cursor.close()
        db.close()

        flash("Screenshot updated!")
        return redirect(url_for("index"))

    cursor.close()
    db.close()

    return render_template(
        "edit.html",
        screenshot=screenshot
    )


# ============================================================
# DELETE SCREENSHOT
# ============================================================

@app.route(
    "/delete/<int:screenshot_id>",
    methods=["POST"]
)
def delete(screenshot_id):

    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM screenshots
        WHERE id = %s
    """, (screenshot_id,))

    screenshot = cursor.fetchone()

    if screenshot is None:
        cursor.close()
        db.close()

        flash("Screenshot not found.")
        return redirect(url_for("index"))

    if screenshot["user_id"] != session["user_id"]:
        cursor.close()
        db.close()

        flash("You can only delete your own screenshots.")
        return redirect(url_for("index"))

    # When object storage is connected, delete the stored image
    # from the bucket here before deleting the database record.

    cursor.execute("""
        DELETE FROM screenshots
        WHERE id = %s
    """, (screenshot_id,))

    db.commit()

    cursor.close()
    db.close()

    flash("Screenshot deleted.")
    return redirect(url_for("index"))


# ============================================================
# INITIALIZE DATABASE
# ============================================================

# Initialize the PostgreSQL tables when the application starts.
# If DATABASE_URL is unavailable (for example, before local
# environment variables are configured), the error will be shown
# clearly instead of silently falling back to SQLite.
init_db()


# ============================================================
# START WEBSITE LOCALLY
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
