# ============================================================
# WEEK 3 UPDATE - SOCIAL FEATURES
# ============================================================
#
# New Week 3 features:
#
#   ❤️ Like screenshots
#   😭 Cry reaction
#   😊 Smile reaction
#   💬 Comment on screenshots
#   🗑️ Delete your own comments
#
# Reactions and comments are saved in Neon PostgreSQL.
#
# Existing features preserved:
#
#   - Register
#   - Login / Logout
#   - User Profiles
#   - Screenshot Upload
#   - Neon PostgreSQL
#   - Neon Object Storage
#   - Presigned image URLs
#   - Edit Screenshot
#   - Delete Screenshot
#
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
# FLASK APPLICATION
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

    database_url = os.environ.get(
        "DATABASE_URL"
    )

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

    bucket = os.environ.get(
        "STORAGE_BUCKET"
    )

    if not bucket:

        raise RuntimeError(
            "STORAGE_BUCKET is not configured."
        )

    return bucket


# ============================================================
# CREATE TEMPORARY IMAGE URL
# ============================================================
#
# IMPORTANT:
#
# Images are stored privately in Neon Object Storage.
# The database stores the object filename.
#
# Every time the gallery loads, this function creates a
# temporary signed URL that the browser can use to display
# the image.
#
# ============================================================

def create_image_url(filename):

    # ========================================================
    # WEEK 3 - IMAGE STORAGE DEBUG / FIX
    # ========================================================

    if not filename:
        print("IMAGE DEBUG: filename is empty")
        return None

    try:

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

        bucket = os.environ.get(
            "STORAGE_BUCKET"
        )

        # Safe debugging.
        # We DO NOT print the actual credentials.
        print(
            "IMAGE DEBUG:",
            "filename =", filename,
            "| endpoint =", bool(endpoint_url),
            "| access_key =", bool(access_key),
            "| secret_key =", bool(secret_key),
            "| region =", region,
            "| bucket =", bucket
        )

        if not endpoint_url:
            raise RuntimeError(
                "AWS_ENDPOINT_URL_S3 is missing"
            )

        if not access_key:
            raise RuntimeError(
                "AWS_ACCESS_KEY_ID is missing"
            )

        if not secret_key:
            raise RuntimeError(
                "AWS_SECRET_ACCESS_KEY is missing"
            )

        if not bucket:
            raise RuntimeError(
                "STORAGE_BUCKET is missing"
            )

        storage = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        image_url = storage.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": filename
            },
            ExpiresIn=3600
        )

        print(
            "IMAGE DEBUG: signed URL created for",
            filename
        )

        return image_url

    except Exception as error:

        print(
            "IMAGE URL ERROR:",
            type(error).__name__,
            str(error)
        )

        return None


    try:

        storage = get_storage_client()
        bucket = get_bucket_name()

        image_url = storage.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": filename
            },
            ExpiresIn=3600
        )

        return image_url

    except Exception as error:

        print(
            "Could not create image URL:",
            error
        )

        return None


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def init_db():

    db = get_db()
    cursor = db.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # SCREENSHOTS
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

    # Make sure older databases also have these columns.

    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS filename TEXT
    """)

    cursor.execute("""
        ALTER TABLE screenshots
        ADD COLUMN IF NOT EXISTS image_url TEXT
    """)

    # ========================================================
    # WEEK 3 UPDATE - REACTIONS
    # ========================================================
    #
    # reaction_type can be:
    #
    # like
    # cry
    # smile
    #
    # Each user gets one reaction per screenshot.
    #
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
    # WEEK 3 UPDATE - USER COMMENTS
    # ========================================================
    #
    # IMPORTANT:
    #
    # screenshots.comment
    # = description entered during upload
    #
    # comments.comment_text
    # = comments posted by other users
    #
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
# HOME PAGE / GALLERY
# ============================================================

@app.route("/")
def index():

    db = get_db()
    cursor = db.cursor()

    # ========================================================
    # WEEK 3 UPDATE
    #
    # Load screenshots plus reaction totals.
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
                WHERE
                    reactions.screenshot_id =
                    screenshots.id
                AND reactions.reaction_type = 'like'
            ) AS like_count,

            (
                SELECT COUNT(*)
                FROM reactions
                WHERE
                    reactions.screenshot_id =
                    screenshots.id
                AND reactions.reaction_type = 'cry'
            ) AS cry_count,

            (
                SELECT COUNT(*)
                FROM reactions
                WHERE
                    reactions.screenshot_id =
                    screenshots.id
                AND reactions.reaction_type = 'smile'
            ) AS smile_count,

            (
                SELECT COUNT(*)
                FROM comments
                WHERE
                    comments.screenshot_id =
                    screenshots.id
            ) AS comment_count

        FROM screenshots

        JOIN users
            ON screenshots.user_id = users.id

        ORDER BY screenshots.created_at DESC
    """)

    screenshots = cursor.fetchall()


    # ========================================================
    # WEEK 3 UPDATE
    # FIND CURRENT USER'S REACTIONS
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
    # WEEK 3 UPDATE
    # LOAD COMMENTS
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

    for user_comment in comment_rows:

        screenshot_id = user_comment[
            "screenshot_id"
        ]

        if screenshot_id not in comments_by_screenshot:

            comments_by_screenshot[
                screenshot_id
            ] = []

        comments_by_screenshot[
            screenshot_id
        ].append(
            user_comment
        )


    cursor.close()
    db.close()


    # ========================================================
    # IMPORTANT - RESTORE SCREENSHOT IMAGES
    # ========================================================
    #
    # Generate a NEW temporary signed URL for every image.
    #
    # Without this section the database records will load,
    # but the browser will display the image placeholder.
    #
    # ========================================================

    for screenshot in screenshots:

        filename = screenshot.get(
            "filename"
        )

        if filename:

            signed_url = create_image_url(
                filename
            )

            screenshot[
                "image_url"
            ] = signed_url


    return render_template(
        "index.html",

        screenshots=screenshots,

        # WEEK 3
        user_reactions=user_reactions,

        # WEEK 3
        comments_by_screenshot=comments_by_screenshot
    )

# ============================================================
# WEEK 4 UPDATE - SCREENSHOT VIEWING MODE
# ============================================================

@app.route("/view/<int:screenshot_id>")
def view_screenshot(screenshot_id):

    db = get_db()
    cursor = db.cursor()

    # --------------------------------------------------------
    # LOAD SCREENSHOT AND REACTION COUNTS
    # --------------------------------------------------------

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
            ) AS smile_count

        FROM screenshots

        JOIN users
            ON screenshots.user_id = users.id

        WHERE screenshots.id = %s
    """, (
        screenshot_id,
    ))

    screenshot = cursor.fetchone()

    # Screenshot does not exist
    if screenshot is None:

        cursor.close()
        db.close()

        flash("Screenshot not found.")

        return redirect(
            url_for("index")
        )

    # --------------------------------------------------------
    # CREATE TEMPORARY IMAGE URL
    # --------------------------------------------------------

    if screenshot["filename"]:

        screenshot["image_url"] = create_image_url(
            screenshot["filename"]
        )

    # --------------------------------------------------------
    # FIND CURRENT USER'S REACTION
    # --------------------------------------------------------

    user_reaction = None

    if "user_id" in session:

        cursor.execute("""
            SELECT reaction_type
            FROM reactions

            WHERE user_id = %s
            AND screenshot_id = %s
        """, (
            session["user_id"],
            screenshot_id
        ))

        reaction = cursor.fetchone()

        if reaction:
            user_reaction = reaction["reaction_type"]

    # --------------------------------------------------------
    # LOAD COMMENTS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT
            comments.id,
            comments.user_id,
            comments.comment_text,
            comments.created_at,
            users.username

        FROM comments

        JOIN users
            ON comments.user_id = users.id

        WHERE comments.screenshot_id = %s

        ORDER BY comments.created_at ASC
    """, (
        screenshot_id,
    ))

    comments = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "view.html",
        screenshot=screenshot,
        user_reaction=user_reaction,
        comments=comments
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

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

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

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

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


    # ========================================================
    # IMPORTANT
    # CREATE IMAGE URLS FOR PROFILE PAGE TOO
    # ========================================================

    for screenshot in screenshots:

        filename = screenshot.get(
            "filename"
        )

        if filename:

            screenshot[
                "image_url"
            ] = create_image_url(
                filename
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

        title = request.form.get(
            "title",
            ""
        ).strip()

        comment = request.form.get(
            "comment",
            ""
        ).strip()

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


        if not allowed_file(
            image.filename
        ):

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


        # ====================================================
        # UPLOAD IMAGE TO NEON OBJECT STORAGE
        # ====================================================

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


        # The actual display URL is generated later.
        image_url = None


        # ====================================================
        # SAVE SCREENSHOT INFORMATION
        # ====================================================

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

            # Remove uploaded image if DB save fails.

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
# ❤️ like
# 😭 cry
# 😊 smile
#
# Behavior:
#
# Click a reaction = add it
#
# Click same reaction again = remove it
#
# Click a different reaction = change reaction
#
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


    # Check for existing reaction.

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

        # Same reaction clicked again.
        # Remove it.

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

            # User selected a different reaction.

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

        # First reaction from this user.

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
        url_for("index") + "#gallery"
    )


# ============================================================
# WEEK 3 UPDATE - ADD COMMENT
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
            url_for("index") + "#gallery"
        )


    if len(comment_text) > 500:

        flash(
            "Comments must be 500 characters or less."
        )

        return redirect(
            url_for("index") + "#gallery"
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


    # Save comment.

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
        url_for("index") + "#gallery"
    )


# ============================================================
# WEEK 3 UPDATE - DELETE COMMENT
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

    user_comment = cursor.fetchone()


    if user_comment is None:

        cursor.close()
        db.close()

        flash(
            "Comment not found."
        )

        return redirect(
            url_for("index")
        )


    # Only comment owner can delete it.

    if (
        user_comment["user_id"]
        != session["user_id"]
    ):

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
        url_for("index") + "#gallery"
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


    if (
        screenshot["user_id"]
        != session["user_id"]
    ):

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

        title = request.form.get(
            "title",
            ""
        ).strip()

        comment = request.form.get(
            "comment",
            ""
        ).strip()


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


    # ========================================================
    # IMPORTANT - IMAGE ON EDIT PAGE
    # ========================================================

    if screenshot["filename"]:

        screenshot[
            "image_url"
        ] = create_image_url(
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


    if (
        screenshot["user_id"]
        != session["user_id"]
    ):

        cursor.close()
        db.close()

        flash(
            "You can only delete "
            "your own screenshots."
        )

        return redirect(
            url_for("index")
        )


    # ========================================================
    # DELETE IMAGE FROM NEON OBJECT STORAGE
    # ========================================================

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


    # ========================================================
    # DELETE DATABASE RECORD
    # ========================================================
    #
    # Because Week 3 reaction/comment foreign keys use
    # ON DELETE CASCADE, related social data is automatically
    # removed when the screenshot is deleted.
    #
    # ========================================================

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
