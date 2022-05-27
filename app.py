import os
from tempfile import mkdtemp

from dotenv import load_dotenv
from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from flask_session import Session
from sqlalchemy import create_engine, text
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

load_dotenv()

# CONNECTION TO MYSQL DATABASE
host = os.getenv('HOST')
user = os.getenv('USER')
password = os.getenv('PWD')
db = os.getenv('DB')

uri = f'mysql+pymysql://{user}:{password}@{host}:3306/{db}'
engine = create_engine(uri)
conn = engine.connect()

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # look up the current user
    users = conn.execute(text(
        f"SELECT cash FROM users WHERE id = {session['user_id']}")).fetchall()
    stocks = conn.execute(text(
        f"SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = {session['user_id']} GROUP BY symbol HAVING total_shares > 0")).fetchall()
    quotes = {}

    for stock in stocks:
        quotes[stock["symbol"]] = lookup(stock["symbol"])

    cash_remaining = users[0]["cash"]
    total = cash_remaining

    return render_template("portfolio.html", quotes=quotes, stocks=stocks, total=total, cash_remaining=cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if the symbol exists
        if quote == None:
            return apology("invalid symbol", 400)

        # Check if shares was a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer", 400)

        # Check if # of shares requested was 0
        if shares <= 0:
            return apology("can't buy less than or 0 shares", 400)

        # Query database for username
        rows = conn.execute(text(
            f"SELECT cash FROM users WHERE id = {session['user_id']}")).fetchall()

        # How much $$$ the user still has in her account
        cash_remaining = rows[0]["cash"]
        price_per_share = quote["price"]

        # Calculate the price of requested shares
        total_price = price_per_share * shares

        if total_price > cash_remaining:
            return apology("not enough funds")

        # Book keeping (TODO: should be wrapped with a transaction)
        conn.execute(text(
            f"UPDATE users SET cash = cash - {total_price} WHERE id = {session['user_id']}"))
        conn.execute(text(
            f"INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES({session['user_id']}, '{request.form.get('symbol')}', {shares}, {price_per_share})"))

        flash("Bought!")

        return redirect(url_for("index"))

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = conn.execute(text(
        f"SELECT symbol, shares, price_per_share, created_at FROM transactions WHERE user_id = {session['user_id']} ORDER BY created_at ASC")).fetchall()

    return render_template("history.html", transactions=transactions)


@app.route("/funds/add", methods=["GET", "POST"])
@login_required
def add_funds():

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except:
            return apology("amount must be a real number", 400)

        conn.execute(
            text(f"UPDATE users SET cash = cash + {amount} WHERE id = {session['user_id']}"))

        return redirect(url_for("index"))
    else:
        return render_template("add_funds.html")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change her password"""

    if request.method == "POST":

        # Ensure current password is not empty
        if not request.form.get("current_password"):
            return apology("must provide current password", 400)

        # Query database for user_id
        rows = conn.execute(text(
            f"SELECT hash FROM users WHERE id = {session['user_id']}")).fetchall()

        # Ensure current password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("current_password")):
            return apology("invalid password", 400)

        # Ensure new password is not empty
        if not request.form.get("new_password"):
            return apology("must provide new password", 400)

        # Ensure new password confirmation is not empty
        elif not request.form.get("new_password_confirmation"):
            return apology("must provide new password confirmation", 400)

        # Ensure new password and confirmation match
        elif request.form.get("new_password") != request.form.get("new_password_confirmation"):
            return apology("new password and confirmation must match", 400)

        # Update database
        hash = generate_password_hash(request.form.get("new_password"))
        rows = conn.execute(
            text(f"UPDATE users SET hash = '{hash}' WHERE id = {session['user_id']}"))

        # Show flash
        flash("Changed!")

    return render_template("change_password.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = conn.execute(text(
            f"SELECT * FROM users WHERE username = '{request.form.get('username')}'")).fetchone()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect(url_for("index"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redi)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password and confirmation match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # hash the password and insert a new user in the database
        hash = generate_password_hash(request.form.get("password"))
        new_user_id = conn.execute(text(
            f"INSERT INTO users (username, hash) VALUES('{request.form.get('username')}', '{hash}')")).rowcount

        # unique username constraint violated?
        if not new_user_id:
            return apology("username taken", 400)

        # Remember which user has logged in
        session["user_id"] = new_user_id

        # Display a flash message
        flash("Registered!")

        # Redirect user to home page
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if the symbol exists
        if quote == None:
            return apology("invalid symbol", 400)

        # Check if shares was a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer", 400)

        # Check if # of shares requested was 0
        if shares <= 0:
            return apology("can't sell less than or 0 shares", 400)

        # Check if we have enough shares
        stock = conn.execute(text(
            f"SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = {session['user_id']} AND symbol = '{request.form.get('symbol')}' GROUP BY symbol")).fetchall()

        if len(stock) != 1 or stock[0]["total_shares"] <= 0 or stock[0]["total_shares"] < shares:
            return apology("you can't sell less than 0 or more than you own", 400)

        # Query database for username
        rows = conn.execute(text(
            f"SELECT cash FROM users WHERE id = {session['user_id']}")).fetchall()

        # How much $$$ the user still has in her account
        cash_remaining = rows[0]["cash"]
        price_per_share = quote["price"]

        # Calculate the price of requested shares
        total_price = price_per_share * shares

        # Book keeping (TODO: should be wrapped with a transaction)
        conn.execute(text(
            f"UPDATE users SET cash = cash + {total_price} WHERE id = {session['user_id']}"))
        conn.execute(text(
            f"INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES({session['user_id']}, '{request.form.get('symbol')}', {shares}, {price_per_share})"))
        # shares=-shares``

        flash("Sold!")

        return redirect(url_for("index"))

    else:
        stocks = conn.execute(text(
            f"SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = {session['user_id']} GROUP BY symbol HAVING total_shares > 0")).fetchall()

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
