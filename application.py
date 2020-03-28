import os
import requests

from flask import Flask, session, render_template, request, jsonify, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, goodreadsapi

app = Flask(__name__)

if not os.getenv("DATABASE_URI"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URI"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():

    books = db.execute("SELECT * FROM books").fetchall()

    return render_template("index.html", books=books)


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    if request.method == "GET": # GET (get a webpage)
        return render_template("register.html")
    else: # POST (submit a data)
        username = request.form.get("username")
        if not username: # If name is left blank
            return render_template("register.html", message="You must provide a username.")
        password = request.form.get("password")
        password2 = request.form.get("password2")
        hash = generate_password_hash(password)
        if not password: # If email is left blank
            return render_template("register.html", message="You must provide a password")
        if password != password2:
            return render_template("register.html", message="Your password didn't match")


        checkusername = db.execute("SELECT username FROM users WHERE username = :username", {"username": username}).fetchone()
        if checkusername:
            return render_template("register.html", message="Username already exists, Try another")
        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", {"username": username, "password": hash})
        db.commit() # Without this insertions will be carried out temporarily

        return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any userid
    session.clear()

    username = request.form.get("username")
    password = request.form.get("password")
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", message="Must provide a valid username")

        # Ensure passoword was submitted
        if not request.form.get("password"):
            return render_template("login.html", message="Must provide a password")

        # Query database for Username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            {"username": request.form.get("username")}).fetchone()
        if rows == None:
            return render_template("login.html", message="No such user exists, Register first")

        if not check_password_hash(rows[2], password):
            return render_template("login.html", message="Your password is incorrect")

        # Remember which user has logged in
        session["username"] = rows[1]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


@app.route("/books", methods=["GET", "POST"])
@login_required
def books():
    # Get search information in lowercase
    name = request.form.get("search").lower()
    if not name:
        return render_template("apology.html", message="You must provide a valid ISBN, Title or Author name.")
    sqlname = '%' + name + '%' # Search query for sql
    if db.execute("SELECT * FROM books WHERE lower(isbn) LIKE :sqlname or lower(title) LIKE :sqlname or lower(author) LIKE :sqlname",
                    {"sqlname": sqlname}).rowcount == 0:
        return render_template("apology.html", message="No such book found")

    # Search query in sql database
    searchedbooks = db.execute("SELECT * FROM books WHERE lower(isbn) LIKE :sqlname or lower(title) LIKE :sqlname or lower(author) LIKE :sqlname",
                    {"sqlname": sqlname}).fetchall()
    # Count how many books has been found
    countofbooks = db.execute("SELECT COUNT(id) FROM books WHERE lower(isbn) LIKE :sqlname or lower(title) LIKE :sqlname or lower(author) LIKE :sqlname",
                    {"sqlname": sqlname}).fetchone()

    return render_template("books.html", searchedbooks=searchedbooks, countofbooks=countofbooks)



@app.route("/books/<isbn>", methods=["GET", "POST"])
@login_required
def book(isbn):
    """Lists details about a single book."""
    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return render_template("apology.html", message="No Such Book Found.")

    # Assign variable to username stored in session
    username = session["username"]
    # This search is performed to get id of user (Perhaps there will be a better way)
    rows = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
    book_id = book[0]
    user_id = rows[0]

    # This is form for rating and reviews submission
    if request.method == "POST":
        star = request.form.get("star")
        if not star: # If name is left blank
            return render_template("apology.html", message="for review submission rating is compulsory")
        comment = request.form.get("comment")
        if not comment: # If email is left blank
            return render_template("apology.html", message="You can't give a blank review")

        # Select review from current user
        user_review = db.execute("SELECT review FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                        {"user_id": user_id, "book_id": book_id}).fetchone()
        if user_review: # To avoid reviews more than one
            return render_template("apology.html", message="Sorry! You already have submitted a review and only one review is allowed")

        else: # Insert review into sql database
            db.execute("INSERT INTO reviews (review, rating, book_id, user_id) VALUES (:review, :rating, :book_id, :user_id)",
                        {"review": comment, "rating": star, "book_id": book_id, "user_id": user_id})
            db.commit() # Without this insertions will be carried out temporarily
    # Select all reviews with their user_id
    review_list = db.execute("SELECT * FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :book_id",
                    {"book_id": book_id}).fetchall()
    # Select average rating
    stars = db.execute("SELECT AVG(rating) FROM reviews WHERE book_id = :book_id", {"book_id": book_id}).fetchone()

    # Fetch data from goodreads website
    data = goodreadsapi(isbn)
    avrating = data["books"][0]["average_rating"]
    ratingscount = data["books"][0]["work_ratings_count"]
    return render_template("book.html", book=book, stars=stars, avrating=avrating, ratingscount=ratingscount, review_list=review_list)

@app.route("/api/<isbn>")
@login_required
def book_api(isbn):
    """Return details about a single book."""

    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return jsonify({"error": "Invalid isbn"}), 422
    # Fetch goodreads api data from goodreads website
    data = goodreadsapi(isbn)
    avrating = data["books"][0]["average_rating"]
    reviewcount = data["books"][0]["reviews_count"]

    return jsonify({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": reviewcount,
        "average_score": avrating
    })
