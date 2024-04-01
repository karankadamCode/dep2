from flask import Flask, render_template, request, redirect, url_for, session
import re
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
import openai
from langchain.chains import RetrievalQA
from langchain.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
import pandas as pd
import requests
import smtplib
from email.message import EmailMessage



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)


# Hardcoded root user credentials
ROOT_USERNAME = 'admin'
ROOT_PASSWORD = 'pladmin@123'



# api_fetch -->
def api_fetch(api_url, query, access_token):
    """
    Function to make a POST request to the API endpoint.

    Parameters:
        - api_url (str): The URL of the API endpoint.
        - input_data (dict): The input data to be sent to the API endpoint.
        - access_token (str): The access token for authorization.

    Returns:
        - dict: The JSON response from the API.
    """

    input_data = {
        "msg": query
    }

    # Prepare headers with the access token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        # Make POST request to the API endpoint
        response = requests.post(api_url, headers=headers, json=input_data)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Return the JSON response
            return response.json()
        else:
            # Print error message if request was unsuccessful
            print(f"Error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        # Print error message if an exception occurs
        print(f"Error: {str(e)}")
        return None

# Example usage:
api_url = "http://20.84.101.4:8080/case-classifier"
access_token ="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTcxMTk1MjUxNX0.SXcFcaGCv7n8xvbYQwkFky_99Brjw3ABamxCUUvU2Q4"



# Login route
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the user is the hardcoded root user
        if username == ROOT_USERNAME and password == ROOT_PASSWORD:
            # Root user logged in successfully
            session['user_id'] = 1  # You can set any user ID for the root user
            return redirect(url_for('home'))
        else:
            return render_template('login.html',
                                   error='Invalid username or password. Please try again.'
                                   )

    return render_template('login.html')


# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            print("User not logged in. Redirecting to index.")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function



# submit route
@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if request.method == "POST":
        user_query = request.form.get("description")
        query= user_query 

        response =  api_fetch(api_url, query, access_token)
        print("Input description :", user_query)
        print(response)
        response_dict = json.loads(response)


        if user_query:
            # Extract data from the response_dict
            handling_firm = response_dict["Handling Firm"]
            primary_case_type = response_dict.get("PrimaryCaseType")
            secondary_case_type = response_dict.get("SecondaryCaseType")
            confidence = response_dict.get("Confidence(%)")
            explanation = response_dict.get("Explanation")
            case_rating = response_dict.get("CaseRating")
            Is_WC = response_dict.get("Is Workers Compensation (Yes/No)?")
            case_state = response_dict.get("Case State")
 
        return render_template("test6.html", primary_case_type=primary_case_type,
                               secondary_case_type=secondary_case_type,
                               case_rating=case_rating,
                               Is_WC=Is_WC,
                               confidence=confidence,
                               explanation=explanation,
                               user_input=user_query,
                               case_state = case_state,
                               handling_firm = handling_firm,
                               result=response
                               )
    return render_template("test6.html")


# home route
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():

    if request.method == "POST":
        user_query = request.form.get("description")
        query = user_query 

        response =  api_fetch(api_url, query, access_token)
        print("Input description :", user_query)
        print(response)
        response_dict = json.loads(response)


        if user_query:
            handling_firm = response_dict["Handling Firm"]
            primary_case_type = response_dict.get("PrimaryCaseType")
            secondary_case_type = response_dict.get("SecondaryCaseType")
            confidence = response_dict.get("Confidence(%)")
            explanation = response_dict.get("Explanation")
            case_rating = response_dict.get("CaseRating")
            Is_WC = response_dict.get("Is Workers Compensation (Yes/No)?")
            case_state = response_dict.get("Case State")

            # Creating a dictionary with the data
            data = {
                "Description": [user_query],
                "Primary Case Type": [primary_case_type],
                "Secondary Case Type": secondary_case_type,
                "Case Rating": [case_rating],
                "Is WC": [Is_WC],
                "Case state": [case_state],
                "Handling Firm":[handling_firm],
                "Confidence": [confidence],
                "Explanation": [explanation],
            }

            # Creating a DataFrame from the dictionary
            df = pd.DataFrame(data)

            # Appending the data to the existing CSV file or create a new file if it doesn't exist
            df.to_csv("correct_case_data.csv", mode="a", index=False, header=not os.path.exists("correct_case_data.csv"))
            case_tier = re.search(r'\d+', case_rating).group()
            if int(case_tier) == 5 or int(case_tier) == 4:
                msg = case_tier
                print(msg)
                body = "There is a high case rating " + case_tier + "."
                message = "High case rating detected. Check your email for an alert."
                email_sent = True
        else:
            primary_case_type = ''
            secondary_case_type = ''
            confidence = ''
            explanation = ''
            case_rating = ''
            Is_WC = ''
            case_state = ''
            handling_firm = ''

        return render_template("test6.html",
                               primary_case_type=primary_case_type,
                               secondary_case_type=secondary_case_type,
                               case_rating=case_rating,
                               Is_WC=Is_WC,
                               confidence=confidence,
                               explanation=explanation,
                               user_input=user_query,
                               result=response,
                               message=message,
                               email_sent = email_sent,
                               case_state = case_state,
                               handling_firm = handling_firm
                               )
    return render_template("test6.html")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)