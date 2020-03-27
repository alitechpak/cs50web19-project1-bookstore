from flask import Flask, redirect, session
from functools import wraps
import requests
import os

def login_required(f): # For details http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("username") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def goodreadsapi(isbn):
    key = os.getenv("GR_KEY")
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
            params={"key": key, "isbns": isbn })
    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful")
    return res.json()
