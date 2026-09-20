# ============================================================
# WEEK 3 UPDATE
# ============================================================
# New social features added during Week 3:
#
#   ❤️ Like reaction
#   😭 Cry reaction
#   😊 Smile reaction
#   💬 User comment system
#   🗑️ Delete your own comments
#
# Reactions and comments are stored in Neon PostgreSQL.
# Each user can have one reaction per screenshot.
#
# Existing features kept:
#   - Register / Login / Logout
#   - User profiles
#   - Screenshot uploads
#   - Neon Object Storage
#   - Edit screenshots
#   - Delete screenshots
# ============================================================


from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

import os
import uuid
import boto3

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename


# ============================================================
# SCREENSHOT WEBSITE
# Flask + Neon PostgreSQL + Neon Object Storage
# ============================================================

app = Flask(__name__)

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
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ============================================================
# DATABASE CONNECTION
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
# NEON OBJECT STORAGE
# ============================================================

def get_storage_client():

    endpoint_url = os.environ.get(
        "AWS_ENDPOINT_URL_S3"
    )

    access_key = os.environ.get(
        "AWS_ACCESS_KEY_ID"
    )

    secret_key = os.environ.get(
        "AWS_SECRET_ACCESS_KEY"
    )

    region = os.environ.get(
        "AWS_REGION",
        "us-east-1"
    )

    if not endpoint_url:

        raise RuntimeError(
            "AWS_ENDPOINT_URL_S3 is not configured."
        )

    if not access_key:

        raise RuntimeError(
            "AWS_ACCESS_KEY_ID is not configured."
        )

    if not secret_key:

        raise RuntimeError(
            "AWS_SECRET_ACCESS_KEY is not configured."
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )


def get_bucket_name():

    bucket = os.environ.get("STORAGE_BUCKET")

    if not bucket:

        raise RuntimeError(
            "STORAGE_BUCKET is not configured."
        )

    return bucket


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def init_db():

    db = get_db()
    cursor = db.cursor()

    # --------------------------------------------------------
    # USERS TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # SCREENSHOTS TABLE
    # --------------------------------------------------------

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

    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS filename TEXT
    """)

    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS image_url TEXT
    """)

    # ========================================================
    # WEEK 3 UPDATE - REACTIONS TABLE
    # ========================================================
    #
    # Stores:
    #   like
    #   cry
    #   smile
    #
    # UNIQUE(user_id, screenshot_id) means each user can
    # only have ONE active reaction on each screenshot.
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
            id SERIAL PRIMARY KEY,

            user_id INTEGER NOT NULL,
            screenshot_id INTEGER NOT NULL,

            reaction_type TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_reaction_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_reaction_screenshot
                FOREIGN KEY (screenshot_id)
                REFERENCES screenshots(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_user_reaction
                UNIQUE (user_id, screenshot_id)
        )
    """)

    # ========================================================
    # WEEK 3 UPDATE - COMMENTS TABLE
    # ========================================================
    #
    # This table is DIFFERENT from screenshots.comment.
    #
    # screenshots.comment = description from uploader
    #
    # comments.comment_text = replies posted by users
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,

            user_id INTEGER NOT NULL,
            screenshot_id INTEGER NOT NULL,

            comment_text TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_comment_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_comment_screenshot
                FOREIGN KEY (screenshot_id)
                REFERENCES screenshots(id)
                ON DELETE CASCADE
        )
    """)

    db.commit()

    cursor.close()
    db.close()


# ============================================================
# CREATE TEMPORARY IMAGE URL
# ============================================================

def create_image_url(filename):

    if not filename:

        return None

    try:

        storage = get_storage_client()
        bucket = get_bucket_name()

        return storage.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": filename
            },
            ExpiresIn=3600
        )

    except Exception as error:

        print(
            "Could not create image URL:",
            error
        )

        return None


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    db = get_db()
    cursor = db.cursor()

    # ========================================================
    # WEEK 3 UPDATE
    #
    # The subqueries count each reaction independently.
    # This avoids multiplying counts when comments and
    # reactions are displayed together.
    # ========================================================

    cursor.execute("""
        SELECT
            screenshots.id,
            screenshots.user_id,
            screenshots.title,
            screenshots.comment,
            screenshots.filename,
            screenshots.image_url,
            screenshots.created_at,
            users.username,

            (
                SELECT COUNT(*)
                FROM reactions
                WHERE reactions.screenshot_id = screenshots.id
                AND reactions.reaction_type = 'like'
            ) AS like_count,

            (
                SELECT COUNT(*)
                FROM reactions
                WHERE reactions.screenshot_id = screenshots.id
                AND reactions.reaction_type = 'cry'
            ) AS cry_count,

            (
                SELECT COUNT(*)
                FROM reactions
                WHERE reactions.screenshot_id = screenshots.id
                AND reactions.reaction_type = 'smile'
            ) AS smile_count,

            (
                SELECT COUNT(*)
                FROM comments
                WHERE comments.screenshot_id = screenshots.id
            ) AS comment_count

        FROM screenshots

        JOIN users
            ON screenshots.user_id = users.id

        ORDER BY screenshots.created_at DESC
    """)

    screenshots = cursor.fetchall()

    # ========================================================
    # WEEK 3 UPDATE - CURRENT USER REACTIONS
    # ========================================================
    #
    # Store the logged-in user's reaction for each screenshot.
    #
    # Example:
    #
    # {
    #     1: "like",
    #     5: "smile"
    # }
    #
    # ========================================================

    user_reactions = {}

    if "user_id" in session:

        cursor.execute("""
            SELECT
                screenshot_id,
                reaction_type

            FROM reactions

            WHERE user_id = %s
        """, (
            session["user_id"],
        ))

        reaction_rows = cursor.fetchall()

        for reaction in reaction_rows:

            user_reactions[
                reaction["screenshot_id"]
            ] = reaction["reaction_type"]

    # ========================================================
    # WEEK 3 UPDATE - LOAD USER COMMENTS
    # ========================================================

    cursor.execute("""
        SELECT
            comments.id,
            comments.user_id,
            comments.screenshot_id,
            comments.comment_text,
            comments.created_at,
            users.username

        FROM comments

        JOIN users
            ON comments.user_id = users.id

        ORDER BY comments.created_at ASC
    """)

    comment_rows = cursor.fetchall()

    comments_by_screenshot = {}

    for comment in comment_rows:

        screenshot_id = comment[
            "screenshot_id"
        ]

        if screenshot_id not in comments_by_screenshot:

            comments_by_screenshot[
                screenshot_id
            ] = []

        comments_by_screenshot[
            screenshot_id
        ].append(
            comment
        )

    cursor.close()
    db.close()

    # --------------------------------------------------------
    # CREATE TEMPORARY IMAGE URLS
    # --------------------------------------------------------

    for screenshot in screenshots:

        if screenshot["filename"]:

            screenshot["image_url"] = create_image_url(
                screenshot["filename"]
            )

    return render_template(
        "index.html",

        screenshots=screenshots,

        # WEEK 3 UPDATE
        user_reactions=user_reactions,

        # WEEK 3 UPDATE
        comments_by_screenshot=comments_by_screenshot
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        if not username or not password:

            flash(
                "Username and password are required."
            )

            return redirect(
                url_for("register")
            )

        password_hash = generate_password_hash(
            password
        )

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

            flash(
                "That username is already taken."
            )

            return redirect(
                url_for("register")
            )

        cursor.close()
        db.close()

        flash(
            "Account created successfully!"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form[
            "username"
        ].strip()

        password = request.form[
            "password"
        ]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username = %s
        """, (
            username,
        ))

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if (
            user
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash(
                "Login successful!"
            )

            return redirect(
                url_for("index")
            )

        flash(
            "Incorrect username or password."
        )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out."
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# USER PROFILE
# ============================================================

@app.route("/profile/<username>")
def profile(username):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            id,
            username

        FROM users

        WHERE username = %s
    """, (
        username,
    ))

    profile_user = cursor.fetchone()

    if profile_user is None:

        cursor.close()
        db.close()

        flash(
            "User not found."
        )

        return redirect(
            url_for("index")
        )

    cursor.execute("""
        SELECT
            id,
            user_id,
            title,
            comment,
            filename,
            image_url,
            created_at

        FROM screenshots

        WHERE user_id = %s

        ORDER BY created_at DESC
    """, (
        profile_user["id"],
    ))

    screenshots = cursor.fetchall()

    cursor.close()
    db.close()

    for screenshot in screenshots:

        if screenshot["filename"]:

            screenshot["image_url"] = create_image_url(
                screenshot["filename"]
            )

    return render_template(
        "profile.html",
        profile_user=profile_user,
        screenshots=screenshots
    )


# ============================================================
# UPLOAD SCREENSHOT
# ============================================================

@app.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():

    if "user_id" not in session:

        flash(
            "You must login before uploading."
        )

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        comment = request.form[
            "comment"
        ].strip()

        image = request.files.get(
            "image"
        )

        if not title:

            flash(
                "Please enter a title."
            )

            return redirect(
                url_for("upload")
            )

        if not image or image.filename == "":

            flash(
                "Please choose an image."
            )

            return redirect(
                url_for("upload")
            )

        if not allowed_file(image.filename):

            flash(
                "Invalid image type. "
                "Use PNG, JPG, JPEG, GIF, or WEBP."
            )

            return redirect(
                url_for("upload")
            )

        original_filename = secure_filename(
            image.filename
        )

        extension = original_filename.rsplit(
            ".",
            1
        )[1].lower()

        filename = (
            str(uuid.uuid4())
            + "."
            + extension
        )

        # ----------------------------------------------------
        # UPLOAD IMAGE TO NEON OBJECT STORAGE
        # ----------------------------------------------------

        try:

            storage = get_storage_client()
            bucket = get_bucket_name()

            image.stream.seek(0)

            storage.upload_fileobj(
                image.stream,
                bucket,
                filename,
                ExtraArgs={
                    "ContentType":
                        image.mimetype
                        or "application/octet-stream"
                }
            )

        except Exception as error:

            print(
                "IMAGE UPLOAD ERROR:",
                error
            )

            flash(
                "The screenshot could not be "
                "uploaded to image storage."
            )

            return redirect(
                url_for("upload")
            )

        image_url = None

        # ----------------------------------------------------
        # SAVE SCREENSHOT RECORD
        # ----------------------------------------------------

        db = get_db()
        cursor = db.cursor()

        try:

            cursor.execute("""
                INSERT INTO screenshots (
                    user_id,
                    title,
                    comment,
                    filename,
                    image_url
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                session["user_id"],
                title,
                comment,
                filename,
                image_url
            ))

            db.commit()

        except Exception as error:

            db.rollback()

            try:

                storage.delete_object(
                    Bucket=bucket,
                    Key=filename
                )

            except Exception:

                pass

            cursor.close()
            db.close()

            print(
                "DATABASE SAVE ERROR:",
                error
            )

            flash(
                "The image uploaded, but the "
                "screenshot information could "
                "not be saved."
            )

            return redirect(
                url_for("upload")
            )

        cursor.close()
        db.close()

        flash(
            "Screenshot uploaded successfully!"
        )

        return redirect(
            url_for("index")
        )

    return render_template(
        "upload.html"
    )


# ============================================================
# WEEK 3 UPDATE - REACTION SYSTEM
# ============================================================
#
# Supported reactions:
#
# ❤️ like
# 😭 cry
# 😊 smile
#
# If the user clicks their current reaction again,
# the reaction is removed.
#
# If they select another reaction, their existing
# reaction is changed.
# ============================================================

@app.route(
    "/react/<int:screenshot_id>/<reaction_type>",
    methods=["POST"]
)
def react(screenshot_id, reaction_type):

    if "user_id" not in session:

        flash(
            "Please login to react to screenshots."
        )

        return redirect(
            url_for("login")
        )

    # WEEK 3 UPDATE:
    # Only allow our three supported reaction types.
    allowed_reactions = {
        "like",
        "cry",
        "smile"
    }

    if reaction_type not in allowed_reactions:

        flash(
            "Invalid reaction."
        )

        return redirect(
            url_for("index")
        )

    db = get_db()
    cursor = db.cursor()

    # Make sure screenshot exists.
    cursor.execute("""
        SELECT id
        FROM screenshots
        WHERE id = %s
    """, (
        screenshot_id,
    ))

    screenshot = cursor.fetchone()

    if screenshot is None:

        cursor.close()
        db.close()

        flash(
            "Screenshot not found."
        )

        return redirect(
            url_for("index")
        )

    # Find the user's existing reaction.
    cursor.execute("""
        SELECT
            id,
            reaction_type

        FROM reactions

        WHERE user_id = %s
        AND screenshot_id = %s
    """, (
        session["user_id"],
        screenshot_id
    ))

    existing_reaction = cursor.fetchone()

    if existing_reaction:

        # ----------------------------------------------------
        # WEEK 3 UPDATE
        #
        # Clicking the same reaction again removes it.
        # ----------------------------------------------------

        if (
            existing_reaction["reaction_type"]
            == reaction_type
        ):

            cursor.execute("""
                DELETE FROM reactions

                WHERE user_id = %s
                AND screenshot_id = %s
            """, (
                session["user_id"],
                screenshot_id
            ))

        else:

            # ------------------------------------------------
            # WEEK 3 UPDATE
            #
            # User picked a different reaction.
            # Change the old reaction to the new one.
            # ------------------------------------------------

            cursor.execute("""
                UPDATE reactions

                SET reaction_type = %s

                WHERE user_id = %s
                AND screenshot_id = %s
            """, (
                reaction_type,
                session["user_id"],
                screenshot_id
            ))

    else:

        # ----------------------------------------------------
        # WEEK 3 UPDATE
        #
        # First reaction from this user on this screenshot.
        # ----------------------------------------------------

        cursor.execute("""
            INSERT INTO reactions (
                user_id,
                screenshot_id,
                reaction_type
            )

            VALUES (%s, %s, %s)
        """, (
            session["user_id"],
            screenshot_id,
            reaction_type
        ))

    db.commit()

    cursor.close()
    db.close()

    return redirect(
        url_for("index")
    )


# ============================================================
# WEEK 3 UPDATE - ADD USER COMMENT
# ============================================================
#
# Allows a logged-in user to leave a comment
# underneath a screenshot.
# ============================================================

@app.route(
    "/comment/<int:screenshot_id>",
    methods=["POST"]
)
def add_comment(screenshot_id):

    if "user_id" not in session:

        flash(
            "Please login to leave a comment."
        )

        return redirect(
            url_for("login")
        )

    comment_text = request.form.get(
        "comment_text",
        ""
    ).strip()

    if not comment_text:

        flash(
            "Comment cannot be empty."
        )

        return redirect(
            url_for("index")
        )

    # WEEK 3 UPDATE:
    # Prevent extremely large comments.
    if len(comment_text) > 500:

        flash(
            "Comments must be 500 characters or less."
        )

        return redirect(
            url_for("index")
        )

    db = get_db()
    cursor = db.cursor()

    # Make sure screenshot exists.
    cursor.execute("""
        SELECT id
        FROM screenshots
        WHERE id = %s
    """, (
        screenshot_id,
    ))

    screenshot = cursor.fetchone()

    if screenshot is None:

        cursor.close()
        db.close()

        flash(
            "Screenshot not found."
        )

        return redirect(
            url_for("index")
        )

    # WEEK 3 UPDATE:
    # Save user comment in Neon PostgreSQL.
    cursor.execute("""
        INSERT INTO comments (
            user_id,
            screenshot_id,
            comment_text
        )

        VALUES (%s, %s, %s)
    """, (
        session["user_id"],
        screenshot_id,
        comment_text
    ))

    db.commit()

    cursor.close()
    db.close()

    flash(
        "Comment posted!"
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# WEEK 3 UPDATE - DELETE USER COMMENT
# ============================================================
#
# Users can only delete comments that belong to them.
# ============================================================

@app.route(
    "/comment/delete/<int:comment_id>",
    methods=["POST"]
)
def delete_comment(comment_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM comments
        WHERE id = %s
    """, (
        comment_id,
    ))

    comment = cursor.fetchone()

    if comment is None:

        cursor.close()
        db.close()

        flash(
            "Comment not found."
        )

        return redirect(
            url_for("index")
        )

    # WEEK 3 UPDATE:
    # Prevent one user from deleting another
    # user's comment.
    if comment["user_id"] != session["user_id"]:

        cursor.close()
        db.close()

        flash(
            "You can only delete your own comments."
        )

        return redirect(
            url_for("index")
        )

    cursor.execute("""
        DELETE FROM comments
        WHERE id = %s
    """, (
        comment_id,
    ))

    db.commit()

    cursor.close()
    db.close()

    flash(
        "Comment deleted."
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# EDIT SCREENSHOT
# ============================================================

@app.route(
    "/edit/<int:screenshot_id>",
    methods=["GET", "POST"]
)
def edit(screenshot_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM screenshots
        WHERE id = %s
    """, (
        screenshot_id,
    ))

    screenshot = cursor.fetchone()

    if screenshot is None:

        cursor.close()
        db.close()

        flash(
            "Screenshot not found."
        )

        return redirect(
            url_for("index")
        )

    if screenshot["user_id"] != session["user_id"]:

        cursor.close()
        db.close()

        flash(
            "You can only edit "
            "your own screenshots."
        )

        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        title = request.form[
            "title"
        ].strip()

        comment = request.form[
            "comment"
        ].strip()

        if not title:

            cursor.close()
            db.close()

            flash(
                "Title cannot be empty."
            )

            return redirect(
                url_for(
                    "edit",
                    screenshot_id=screenshot_id
                )
            )

        cursor.execute("""
            UPDATE screenshots

            SET
                title = %s,
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

        flash(
            "Screenshot updated!"
        )

        return redirect(
            url_for("index")
        )

    if screenshot["filename"]:

        screenshot["image_url"] = create_image_url(
            screenshot["filename"]
        )

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

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT *
        FROM screenshots
        WHERE id = %s
    """, (
        screenshot_id,
    ))

    screenshot = cursor.fetchone()

    if screenshot is None:

        cursor.close()
        db.close()

        flash(
            "Screenshot not found."
        )

        return redirect(
            url_for("index")
        )

    if screenshot["user_id"] != session["user_id"]:

        cursor.close()
        db.close()

        flash(
            "You can only delete "
            "your own screenshots."
        )

        return redirect(
            url_for("index")
        )

    # --------------------------------------------------------
    # DELETE IMAGE FROM OBJECT STORAGE
    # --------------------------------------------------------

    if screenshot["filename"]:

        try:

            storage = get_storage_client()
            bucket = get_bucket_name()

            storage.delete_object(
                Bucket=bucket,
                Key=screenshot["filename"]
            )

        except Exception as error:

            print(
                "IMAGE DELETE ERROR:",
                error
            )

            # Continue deleting database record even
            # if object storage deletion fails.

    # --------------------------------------------------------
    # DELETE DATABASE RECORD
    # --------------------------------------------------------
    #
    # WEEK 3:
    # Reactions and user comments are automatically
    # removed because their foreign keys use
    # ON DELETE CASCADE.
    # --------------------------------------------------------

    cursor.execute("""
        DELETE FROM screenshots
        WHERE id = %s
    """, (
        screenshot_id,
    ))

    db.commit()

    cursor.close()
    db.close()

    flash(
        "Screenshot deleted."
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# START WEBSITE LOCALLY
# ============================================================

if __name__ == "__main__":

    app.run(debug=True)
