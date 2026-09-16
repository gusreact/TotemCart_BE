from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from send_email import send_email
import urllib.parse

app = Flask(__name__) # Initialize the Flask application, __name__ helps to locate resources
DB_USER = "gusvillagran"
DB_PASS = "mysql123456"  # <-- if this contains non-ASCII chars
DB_PASS_ENC = urllib.parse.quote_plus(DB_PASS)  # percent-encode unsafe chars
DB_HOST = "gusvillagran.mysql.pythonanywhere-services.com"
DB_NAME = "gusvillagran$default"
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}" # Configure the database URI for SQLite
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable modification tracking to save resources
db = SQLAlchemy(app) # Initialize SQLAlchemy with the Flask app

class Data(db.Model): # Define a model for the data table
    __tablename__ = 'data' # Specify the table name
    id = db.Column(db.Integer, primary_key=True) # Primary key column
    email = db.Column(db.String(120), unique=True) # Email column
    height = db.Column(db.Integer) # Height column

    def __init__(self, email, height): # Constructor to initialize email and height
        self.email = email
        self.height = height

@app.route('/') # Define the route for the home page
def index():
    return render_template('index.html') # Render the index.html template

@app.route('/success', methods=['POST']) # Define the route for the success page
def success():
    if request.method == 'POST': # Check if the request method is GET
        email = request.form['email'] # Get the email from query parameters
        height = request.form['height'] # Get the height from query parameters
        print(email, height) # Print email and height to the console
        if db.session.query(Data).filter(Data.email == email).count() == 0: # Check if email already exists in the database
            db.session.add(Data(email, height)) # Add new Data entry to the session
            db.session.commit() # Commit the session to save changes to the database
            average_height = db.session.query(db.func.avg(Data.height)).scalar() # Calculate average height
            average_height = round(average_height, 1) # Round average height to one decimal place
            count = db.session.query(Data).count() # Get the total count of entries
            send_email(email, height, average_height, count) # Send email with the provided email and height
            return render_template('success.html', email=email, height=height) # Render success.html with email and height
        return render_template('index.html', message="Email already exists!")
    else:
        return "Invalid request method", 400 # Return error for invalid request methods

def create_tables():
    with app.app_context():
        db.create_all() # Create database tables

if __name__ == '__main__': # Run the application
    create_tables()
    app.run(debug=True) # Enable debug mode for development purposes

