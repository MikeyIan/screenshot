

# 🎮 SCREENSHOT

SCREENSHOT is a video game screenshot sharing website.

The goal of this project is to create a place where gamers can
upload their favorite video game screenshots, write comments,
and manage their own posts.

This project is being built with Python, Flask, HTML, CSS,
and SQLite.

---

## 📸 About the Project

SCREENSHOT allows users to create an account and share
screenshots from their favorite video games.

Users can:

- Create an account
- Login and logout
- Upload video game screenshots
- Add a title to their screenshots
- Add comments
- View screenshots uploaded by other users
- Edit their own screenshots
- Delete their own screenshots

---

## 🎮 Features

### User Accounts

Users can register with:

- Username
- Password

Passwords are securely hashed before being stored in the
database.

### Login System

Registered users can login to their account.

The website uses Flask sessions to keep track of the
currently logged-in user.

### Screenshot Uploads

Users can upload image files including:

- PNG
- JPG
- JPEG
- GIF
- WEBP

Each screenshot can have:

- A title
- A comment
- The username of the person who uploaded it

### Edit Screenshots

Users can edit the title and comment of screenshots
they uploaded.

Users cannot edit screenshots belonging to other users.

### Delete Screenshots

Users can delete their own screenshots.

Users cannot delete screenshots belonging to other users.

---

## 🛠️ Technologies Used

### Python

Python is used to run the main application.

### Flask

Flask is the web framework used to create the website.

### HTML

HTML creates the structure of the website pages.

### CSS

CSS will be used to control the appearance and design
of SCREENSHOT.

### SQLite

SQLite stores:

- User accounts
- Password hashes
- Screenshot information
- Comments
- Uploaded image filenames

### GitHub

GitHub is being used to store and manage the source code
for this project.

---

## 📁 Project Structure

```text
SCREENSHOT/
│
├── app.py
│
├── README.md
│
├── static/
│
├── templates/
│   ├── base.html
│   ├── register.html
│   ├── login.html
│   ├── index.html
│   ├── upload.html
│   └── edit.html
│
└── uploads/
````

---

## 🧠 How the Application Works

The application uses Flask to connect the website pages
to the Python backend.

The basic process is:

```text
User
  │
  ▼
Website
  │
  ▼
HTML Pages
  │
  ▼
Flask
  │
  ▼
Python
  │
  ├── SQLite Database
  │
  └── Uploaded Screenshots
```

---

## 🔐 Security

The application includes several basic security features.

### Password Hashing

User passwords are not stored as plain text.

Flask/Werkzeug hashes passwords before they are stored.

### User Ownership

Users can only edit or delete screenshots that belong
to their own account.

### Secure File Names

Uploaded files are given unique filenames so that uploaded
images do not overwrite each other.

### File Type Checking

The application checks uploaded files and only allows
supported image extensions.

---

## 🚧 Project Status

SCREENSHOT is currently under development.

### Completed

* [x] Flask application
* [x] SQLite database
* [x] User registration
* [x] User login
* [x] User logout
* [x] Screenshot upload system
* [x] Screenshot comments
* [x] Screenshot editing
* [x] Screenshot deletion
* [x] User ownership checks

### In Progress

* [ ] Website styling
* [ ] Gaming-themed design
* [ ] Responsive mobile design
* [ ] Screenshot search
* [ ] Screenshot categories
* [ ] Game titles
* [ ] User profiles

### Future Ideas

* [ ] Likes
* [ ] Favorites
* [ ] Tags
* [ ] Game-specific pages
* [ ] User avatars
* [ ] Follow other users
* [ ] Screenshot ratings
* [ ] Dark/light mode
* [ ] Steam-style screenshot gallery

---

## 💻 Running SCREENSHOT Locally

The project is designed to run locally on a Mac or
other computer with Python installed.

Install the required Python packages:

```bash
pip install flask werkzeug
```

Then start the application:

```bash
python3 app.py
```

The website should then be available at:

```text
http://127.0.0.1:5000
```

Open that address in a web browser to view SCREENSHOT.

---

## 🗃️ Database

SCREENSHOT uses SQLite.

The database is automatically created when the Flask
application starts.

The database contains tables for:

### Users

Stores:

* User ID
* Username
* Password hash

### Screenshots

Stores:

* Screenshot ID
* User ID
* Title
* Comment
* Filename
* Upload date

---

## 👨‍💻 Project Purpose

This project was created as a hands-on web development
project to practice:

* Python programming
* Flask web development
* HTML
* CSS
* Databases
* User authentication
* File uploads
* CRUD operations
* Git
* GitHub

CRUD stands for:

**Create**

**Read**

**Update**

**Delete**

SCREENSHOT uses CRUD operations to manage user
screenshots.

---

## 📌 Current Version

Version: 0.1

Status: Development

---

## 📜 License

This project is currently being developed for educational
and portfolio purposes.

---

## 🎮 SCREENSHOT

**Share the moment. Capture the game.**

````

### Save it

Press:

**⌘ Command + S**

---

## Then commit it to GitHub

Go back to **GitHub Desktop**.

You should now see `README.md` listed under the changed files.

At the bottom-left, you'll see something like:

```text
Summary (required)

Description
````

Put:

**Summary:**

```text
Add project README
```

Then click:

**Commit to main**

After that click:

**Push origin**

That will send your README **and the code you've created so far** to your GitHub repository.

### Your GitHub project will now have

```text
SCREENSHOT
│
├── README.md       ← Project explanation
├── app.py          ← Python/Flask backend
├── static/
└── templates/
    ├── base.html
    ├── register.html
    ├── login.html
    ├── index.html
    ├── upload.html
    └── edit.html
```

**Next, do you want to make `style.css` for a dark gaming design or run the website first?**
