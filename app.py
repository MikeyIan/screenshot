from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import os
import uuid

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# ============================================================
# SCREENSHOT WEBSITE
# ============================================================
# This is the main Python file for the SCREENSHOT website.
#
# The website allows users to:
# 1. Register an account
# 2. Login
# 3. Logout
# 4. Upload video game screenshots
# 5. Add comments to screenshots
# 6. Edit their screenshots
# 7. Delete their screenshots
#
# Flask handles the website.
# SQLite handles the database.
# ============================================================


# ------------------------------------------------------------
# CREATE THE FLASK APPLICATION
# ------------------------------------------------------------

app = Flask(__name__)

# This key protects the user's login session.
# Change this later to a long random secret.
app.secret_key = "screenshot-secret-key-change-this"


# ------------------------------------------------------------
# DATABASE SETTINGS
# ------------------------------------------------------------

DATABASE = "screenshot.db"

# Uploaded screenshots will be stored here.
UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# Create the uploads folder if it does not exist.
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------------------------------------------------
# ALLOWED IMAGE TYPES
# ------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp"
}


# ------------------------------------------------------------
# DATABASE CONNECTION
# ------------------------------------------------------------

def get_db():

    # Connect to our SQLite database.
    db = sqlite3.connect(DATABASE)

    # This allows us to access database columns by name.
    db.row_factory = sqlite3.Row

    return db


# ------------------------------------------------------------
# CREATE DATABASE
# ------------------------------------------------------------

def init_db():

    db = get_db()

    # --------------------------------------------------------
    # USERS TABLE
    # --------------------------------------------------------
    #
    # Stores registered users.
    #
    # We store a password HASH rather than the actual
    # password.
    # --------------------------------------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password_hash TEXT NOT NULL
        )
    """)


    # --------------------------------------------------------
    # SCREENSHOTS TABLE
    # --------------------------------------------------------
    #
    # Stores information about uploaded screenshots.
    # --------------------------------------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            title TEXT NOT NULL,

            comment TEXT,

            filename TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
        )
    """)

    db.commit()

    db.close()


# ------------------------------------------------------------
# CHECK FILE TYPE
# ------------------------------------------------------------

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    db = get_db()

    # Get every screenshot and the username of the person
    # who uploaded it.
    screenshots = db.execute("""
        SELECT
            screenshots.id,
            screenshots.user_id,
            screenshots.title,
            screenshots.comment,
            screenshots.filename,
            screenshots.created_at,
            users.username

        FROM screenshots

        JOIN users
        ON screenshots.user_id = users.id

        ORDER BY screenshots.created_at DESC
    """).fetchall()

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

    # If the user submitted the registration form...
    if request.method == "POST":

        username = request.form["username"].strip()

        password = request.form["password"]


        # Make sure the user entered both fields.
        if not username or not password:

            flash("Username and password are required.")

            return redirect(url_for("register"))


        # Turn the password into a secure hash.
        password_hash = generate_password_hash(password)


        db = get_db()

        try:

            # Add the new user to the database.
            db.execute("""
                INSERT INTO users (
                    username,
                    password_hash
                )

                VALUES (?, ?)
            """, (
                username,
                password_hash
            ))

            db.commit()

        except sqlite3.IntegrityError:

            # Username already exists.
            db.close()

            flash("That username is already taken.")

            return redirect(url_for("register"))

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

        # Find the username.
        user = db.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()

        db.close()


        # Check the password against the stored hash.
        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            # Store the user's ID in the login session.
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

    # Remove login information.
    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("index"))


# ============================================================
# UPLOAD SCREENSHOT
# ============================================================

@app.route("/upload", methods=["GET", "POST"])
def upload():

    # --------------------------------------------------------
    # USER MUST BE LOGGED IN
    # --------------------------------------------------------

    if "user_id" not in session:

        flash("You must login before uploading.")

        return redirect(url_for("login"))


    if request.method == "POST":

        # Get information from the form.
        title = request.form["title"].strip()

        comment = request.form["comment"].strip()

        image = request.files.get("image")


        # ----------------------------------------------------
        # CHECK TITLE
        # ----------------------------------------------------

        if not title:

            flash("Please enter a title.")

            return redirect(url_for("upload"))


        # ----------------------------------------------------
        # CHECK IMAGE
        # ----------------------------------------------------

        if not image or image.filename == "":

            flash("Please choose an image.")

            return redirect(url_for("upload"))


        # ----------------------------------------------------
        # CHECK IMAGE TYPE
        # ----------------------------------------------------

        if not allowed_file(image.filename):

            flash(
                "Invalid image type. "
                "Use PNG, JPG, JPEG, GIF, or WEBP."
            )

            return redirect(url_for("upload"))


        # ----------------------------------------------------
        # CREATE SAFE UNIQUE FILE NAME
        # ----------------------------------------------------

        original_filename = secure_filename(
            image.filename
        )

        extension = original_filename.rsplit(
            ".",
            1
        )[1].lower()


        # UUID prevents files from overwriting each other.
        filename = str(uuid.uuid4()) + "." + extension


        # Create the complete file path.
        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )


        # Save the screenshot.
        image.save(filepath)


        # ----------------------------------------------------
        # SAVE SCREENSHOT INFORMATION TO DATABASE
        # ----------------------------------------------------

        db = get_db()

        db.execute("""
            INSERT INTO screenshots (
                user_id,
                title,
                comment,
                filename
            )

            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            comment,
            filename
        ))

        db.commit()

        db.close()


        flash("Screenshot uploaded successfully!")

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

    # User must be logged in.
    if "user_id" not in session:

        flash("Please login first.")

        return redirect(url_for("login"))


    db = get_db()


    # Find the screenshot.
    screenshot = db.execute("""
        SELECT *
        FROM screenshots
        WHERE id = ?
    """, (screenshot_id,)).fetchone()


    # Screenshot does not exist.
    if screenshot is None:

        db.close()

        flash("Screenshot not found.")

        return redirect(url_for("index"))


    # --------------------------------------------------------
    # SECURITY CHECK
    # --------------------------------------------------------
    #
    # Make sure the current user owns this screenshot.
    # --------------------------------------------------------

    if screenshot["user_id"] != session["user_id"]:

        db.close()

        flash(
            "You can only edit your own screenshots."
        )

        return redirect(url_for("index"))


    # --------------------------------------------------------
    # SAVE CHANGES
    # --------------------------------------------------------

    if request.method == "POST":

        title = request.form["title"].strip()

        comment = request.form["comment"].strip()


        if not title:

            db.close()

            flash("Title cannot be empty.")

            return redirect(
                url_for(
                    "edit",
                    screenshot_id=screenshot_id
                )
            )


        db.execute("""
            UPDATE screenshots

            SET title = ?,
                comment = ?

            WHERE id = ?
        """, (
            title,
            comment,
            screenshot_id
        ))


        db.commit()

        db.close()


        flash("Screenshot updated!")

        return redirect(url_for("index"))


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

    # User must be logged in.
    if "user_id" not in session:

        flash("Please login first.")

        return redirect(url_for("login"))


    db = get_db()


    # Find screenshot.
    screenshot = db.execute("""
        SELECT *
        FROM screenshots
        WHERE id = ?
    """, (screenshot_id,)).fetchone()


    if screenshot is None:

        db.close()

        flash("Screenshot not found.")

        return redirect(url_for("index"))


    # --------------------------------------------------------
    # SECURITY CHECK
    # --------------------------------------------------------

    if screenshot["user_id"] != session["user_id"]:

        db.close()

        flash(
            "You can only delete your own screenshots."
        )

        return redirect(url_for("index"))


    # --------------------------------------------------------
    # DELETE IMAGE FILE
    # --------------------------------------------------------

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        screenshot["filename"]
    )


    if os.path.exists(filepath):

        os.remove(filepath)


    # --------------------------------------------------------
    # DELETE DATABASE RECORD
    # --------------------------------------------------------

    db.execute("""
        DELETE FROM screenshots
        WHERE id = ?
    """, (screenshot_id,))


    db.commit()

    db.close()


    flash("Screenshot deleted.")

    return redirect(url_for("index"))


# ============================================================
# DISPLAY UPLOADED IMAGES
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# START WEBSITE
# ============================================================

if __name__ == "__main__":

    # Create the database and tables.
    init_db()

    # Start the website.
    app.run(
        debug=True
    )