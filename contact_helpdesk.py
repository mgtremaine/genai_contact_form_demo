#!/usr/bin/env python

# contact_helpdesk.py
# This script is a Streamlit app for a member contact form.
# It allows users to submit questions or comments and view responses.
# It also allows the helpdesk to respond to inquiries and close submissions.

#Be sure to configure the email_from and email_to variables with valid email addresses.
#This script assumes that the database schema has a table named contact_queue with the following columns:
#Contact_ID, Contact_Type, Contact_Fname, Contact_Lname, Contact_Email, Contact_DOB, Contact_Question, Contact_Response, Final_Prompt, Final_Response, Evaluation, Creation_Date, Processed_Date, Status, Payload

# Author: Mike Tremaine 
# Date: 2024-07-17 
# Version: 1.0
# License: MIT

#Import the necessary libraries
import streamlit as st
import pandas as pd
import json
import mysql.connector

#Import the shared functions
from contact_utils import load_json_config, connect_to_mysql, initialize_baserun, send_generic_baserun_message, send_email_via_sendgrid, send_baserun_openai_query, send_baserun_tag

# Import the function from google_rag_query.py
from google_rag_query import get_rag_response, get_rag_prompt 

# Global variables
corpus_config_path = 'corpus_config.json' #This is generated by create_google_rag.py rename it as needed
credentials_path = 'key.json' #Google Service Account key file
config_path = "config.json" #Main configuration file database, sendgrid, baserun, etc.

# Email variable needs CC/BCC and email_to if from database. -mgt
email_from = "user@example.com"
email_to = "user@example.com"
subject = "Response to your inquiry"

def clicked_close_submission(config, submission_id, submission_details):
    """
    Closes a submission and sends an email notification via sendgrid. 
    Build alternet email function for other email services.

    Parameters:
    - config (dict): Configuration settings.
    - submission_id (int): The ID of the submission to be closed.
    - submission_details (dict): Details of the submission.

    Returns:
    None
    """
    update_submission(config, submission_id, "Status", "Closed")
    response = submission_details['Final_Response'];
    email_body = return_template(submission_details, response)
    # Assuming there's a function to send emails
    send_email_via_sendgrid(config['sendgrid_key'], email_from, email_to, subject, email_body)
    st.success("Submission closed, Email Sent.")

def clicked_get_rag(config, corpus_config_path, credentials_path, submission_id):
    """
    Fetches RAG/LLM response and updates the submission.

    Args:
        config (str): The configuration.
        corpus_config_path (str): The path to the corpus configuration.
        credentials_path (str): The path to the credentials.
        submission_id (str): The ID of the submission.

    Returns:
        None
    """
    #print to console debug info
    print("Fetching RAG/LLM response...")
    rag_prompt, rag_response = get_rag_response(corpus_config_path, credentials_path, config, submission_id)  # Assuming this function exists and returns the response
    print(rag_response)
    update_submission(config, submission_id, "Contact_Response", rag_response)
    update_submission(config, submission_id, "Final_Prompt", rag_prompt)
    update_submission(config, submission_id, "Status", "Processed")
    update_submission(config, submission_id, "Payload", "JSON_INSERT(@`Payload`, '$.llm', 'gemini-1.5-pro-001')")
    st.success("RAG/LLM response fetched and submission updated.")

def clicked_get_openai(config, corpus_config_path, credentials_path, submission_id, submission_details):
    """
    Fetches RAG response and OpenAI response, updates submission details, and prints OpenAI response.

    Parameters:
    - config (str): Configuration information.
    - corpus_config_path (str): Path to the corpus configuration file.
    - credentials_path (str): Path to the credentials file.
    - submission_id (str): ID of the submission.
    - submission_details (dict): Details of the submission.

    Returns:
    None
    """
    contact_id = submission_details['Contact_ID'] #double check this 
    #print to console debug info
    print("Fetching RAG response...")
    prompt = get_rag_prompt(corpus_config_path, credentials_path, config, contact_id)
    print("Fetching OpenAI response...")
    response, trace_id = send_baserun_openai_query(config, prompt)
    print(response)
    update_submission(config, submission_id, "Contact_Response", response)
    update_submission(config, submission_id, "Final_Prompt", prompt)
    update_submission(config, submission_id, "Status", "Processed")
    update_submission_payload(config, submission_id, "llm", "openai")
    update_submission_payload(config, submission_id, "trace_id", trace_id)
    st.success("OpenAI response fetched and submission updated.")

def clicked_submit_response(config, submission_id, submission_details, prompt):
    """
    Submit the response for a given submission.

    Parameters:
    - config (dict): Configuration settings.
    - submission_id (str): ID of the submission.
    - submission_details (dict): Details of the submission.
    - prompt (str): Prompt for the response.

    Returns:
    None
    """
    #decode json payload to payload
    try:
        if submission_details['Payload']:
            payload = json.loads(submission_details['Payload'])
        else:
            payload = {}
    except json.JSONDecodeError:
        payload = {}
        st.warning("Invalid JSON payload. Unable to parse.")
    response = st.session_state[f"final_{submission_id}"] 
    update_submission(config, submission_id, "Final_Response", response)
    evaluation = st.session_state[f"slider_{submission_id}"]
    update_submission(config, submission_id, "Evaluation", evaluation)
    #call baserun
    baserun_client = initialize_baserun(config) 
    model_name = "gemini-1.5-pro-001" # model name as global?
    print(payload)
    if 'llm' in payload and payload['llm'] == 'openai':
        send_baserun_tag(config, evaluation, payload)
    else:
        send_generic_baserun_message(baserun_client, model_name, prompt, response, evaluation)
    st.success("Response updated and email prepared.")

def display_email_details(submission_details, response):
    """
    Display the email details.

    Parameters:
    - submission_details (dict): A dictionary containing the submission details.
    - response (str): The response received.

    Returns:
    None
    """
    email_body = return_template(submission_details, response)
    st.title("Email Details")
    st.write("**From:**", email_from)
    st.write("**To:**", email_to)
    st.write("**Subject:**", subject)
    st.write("**Body:**")
    #email_body as markdown
    #escape dollar signs from email_body
    email_body = email_body.replace("$", "\$")
    st.markdown(email_body)


def display_submissions(config):
    """
    Display the waiting submissions.

    Parameters:
    - config: The configuration object.

    Returns:
    None
    """
    # Fetch the waiting submissions 
    df = fetch_waiting_submissions(config)
    st.title("Waiting Submissions")
    #loop through the submissions
    if not df.empty:
        for index, row in df.iterrows():
            # Use the Contact_ID as the button label and display additional info below if clicked
            if st.button(f"Contact ID: {row['Contact_ID']}", key=row['Contact_ID']):
            # Clear the placeholder to simulate clearing the screen
                placeholder = st.empty()
                placeholder.empty()
                load_submission_details(config, row['Contact_ID'])
    else:
        st.write("No waiting submissions.")

def fetch_submission_details(config, submission_id):
    """
    Fetches the details of a submission from the contact_queue table in the database.

    Args:
        config (dict): A dictionary containing the database configuration.
        submission_id (int): The ID of the submission to fetch.

    Returns:
        dict or None: A dictionary containing the details of the submission if found, 
                      or None if no submission with the given ID exists.
    """
    conn = connect_to_mysql(config)
    cursor = conn.cursor()
    query = "SELECT * FROM contact_queue WHERE Contact_ID = %s"
    cursor.execute(query, (submission_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return dict(zip(['Contact_ID', 'Contact_Type', 'Contact_Fname', 'Contact_Lname', 'Contact_Email', 'Contact_DOB', 'Contact_Question', 'Contact_Response','Final_Prompt','Final_Response','Evaluation','Creation_Date', 'Processed_Date', 'Status', 'Payload'], row))
    return None

# Function to fetch waiting submissions from the database
def fetch_waiting_submissions(config):
    """
    Fetches the waiting submissions from the contact_queue table in the database.

    Args:
        config (dict): A dictionary containing the configuration details for connecting to the database.

    Returns:
        pandas.DataFrame: A DataFrame containing the fetched rows from the contact_queue table.
            The DataFrame has the following columns:
            - Contact_ID: The ID of the contact.
            - Contact_Type: The type of contact.
            - Contact_Fname: The first name of the contact.
            - Contact_Lname: The last name of the contact.
            - Contact_Email: The email of the contact.
            - Contact_DOB: The date of birth of the contact.
            - Contact_Question: The question asked by the contact.
            - Contact_Response: The response given to the contact.
            - Final_Prompt: The final prompt given to the contact.
            - Final_Response: The final response given to the contact.
            - Evaluation: The evaluation of the contact.
            - Creation_Date: The date of creation of the contact.
            - Processed_Date: The date when the contact was processed.
            - Status: The status of the contact.
            - Payload: The payload of the contact.
    """
    conn = connect_to_mysql(config)
    cursor = conn.cursor()
    query = "SELECT * FROM contact_queue WHERE Status <> 'Closed'"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    # Adjust column names based on the actual database schema
    return pd.DataFrame(rows, columns=['Contact_ID', 'Contact_Type', 'Contact_Fname', 'Contact_Lname', 'Contact_Email', 'Contact_DOB', 'Contact_Question', 'Contact_Response','Final_Prompt','Final_Response','Evaluation','Creation_Date', 'Processed_Date', 'Status', 'Payload'])

def insert_submission(config, contact_type, fname, lname, email, dob, comment, date):
    """
    Insert a submission into the contact_queue table.

    Args:
        config (str): The configuration for connecting to the database.
        contact_type (str): The type of contact.
        fname (str): The first name of the contact.
        lname (str): The last name of the contact.
        email (str): The email of the contact.
        dob (str): The date of birth of the contact.
        comment (str): The comment/question of the contact.
        date (datetime): The creation date of the submission.

    Returns:
        None
    """
    date = date.strftime('%Y-%m-%d %H:%M:%S')
    conn = connect_to_mysql(config)
    cursor = conn.cursor()
    query = "INSERT INTO contact_queue (Contact_Type, Contact_Fname, Contact_Lname, Contact_Email, Contact_DOB, Contact_Question, Creation_Date) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (contact_type, fname, lname, email, dob, comment, date))
    conn.commit()
    cursor.close()
    conn.close()

def load_submission_details(config, submission_id):
    """
    Loads the submission details for a given submission ID.

    Parameters:
    - config (dict): The configuration settings.
    - submission_id (str): The ID of the submission.

    Returns:
    - None
    """
    submission_details = fetch_submission_details(config, submission_id)
    evaluation_key = f"evaluation_{submission_id}"
    submitted_key = f"submitted_{submission_id}"
    response_key = f"response_{submission_id}"
    final_key = f"final_{submission_id}"
    slider_key = f"slider_{submission_id}"

    if submission_details:
        # Custom CSS to modify the textarea width and height
        custom_css = '''
        <style>
            .stTextArea textarea {
                font-size: 16px !important;
                font-color: black !important;
                font-weight: bold !important;
                width: 800px !important;
                height: 400px !important;
            }
        </style>
        '''
        st.write(custom_css, unsafe_allow_html=True)

        st.title("Submission Details")

        with st.form(f"submission_{submission_id}"):

            if submission_details['Final_Response']:
                display_email_details(submission_details, submission_details['Final_Response'])
                # Button to close submission entry.
                st.form_submit_button("Send Email/Close Submission", on_click=clicked_close_submission, args=(config, submission_id, submission_details))
            else: 
                st.write(f"ID: {submission_details['Contact_ID']}")
                st.write(f"First Name: {submission_details['Contact_Fname']} ")
                st.write(f"Last Name: {submission_details['Contact_Lname']} ")
                st.write(f"Email: {submission_details['Contact_Email']} ")

                st.write("Question:")
                st.markdown(submission_details['Contact_Question'])

                st.write("Prompt:")
                #escape dollar signs from prompt
                if submission_details['Final_Prompt']:
                    prompt = st.markdown(submission_details['Final_Prompt'].replace("$", "\$"))
                else: 
                    prompt = st.markdown(submission_details['Final_Prompt'])

                st.write("Raw Response:")
                st.markdown(submission_details['Contact_Response'])

                st.text_area("Response", value=submission_details.get('Contact_Response', ''), key=final_key)
                st.session_state[response_key] = submission_details['Contact_Response']
                # Show this if Final_Response is empty
                if not st.session_state[response_key] or st.session_state[response_key] == "":
                    #st.form_submit_button("Get RAG/LLM Response", on_click=clicked_get_rag, args=(config, corpus_config_path, credentials_path, submission_id)) 
                    st.form_submit_button("Get RAG/LLM Response", on_click=clicked_get_openai, args=(config, corpus_config_path, credentials_path, submission_id, submission_details))
                else:
                    st.slider("Evaluation [Scale 1-5 with 1=Bad 5=Great]", min_value=1, max_value=5, value=submission_details['Evaluation'], key=slider_key)

                # Button to submit response
                if not submission_details['Final_Response']:
                    st.session_state[submitted_key] = st.form_submit_button("Submit Response", on_click=clicked_submit_response, args=(config, submission_id, submission_details, prompt))


def member_contact_form(config):
    """
    Renders a member contact form using Streamlit.

    Parameters:
    - config (str): The configuration for the form.

    Returns:
    None
    """
    st.title("Member Contact Form")
    # The rest of your main function code
    with st.form("contact_form", clear_on_submit=True):
        contact_type = st.selectbox("Contact Type", ["", "Claim", "Benefits", "Doctor List", "Eligibility", "ID Card", "Other", "Website Navigation"], index=0)
        fname = st.text_input("First Name")
        lname = st.text_input("Last Name")
        email = st.text_input("Email")
        dob = st.date_input("Date of Birth")
        comment = st.text_area("Question or Comment?", height=100)
        date = pd.to_datetime("today")
        submitted = st.form_submit_button("Submit")

        if submitted and contact_type and fname and lname and email and comment:
            insert_submission(config, contact_type, fname, lname, email, dob, comment, date)
            st.success("Submission successful!")
        
def return_template(submission_details, response):
    """
    Generates a template for a helpdesk response.

    Args:
        submission_details (dict): A dictionary containing the submission details.
            - 'Contact_Fname' (str): The first name of the contact.
            - 'Contact_Lname' (str): The last name of the contact.
            - 'Contact_Question' (str): The question asked by the contact.
        response (str): The response to the contact's question.

    Returns:
        str: The generated template for the helpdesk response.
    """






    user_name = submission_details['Contact_Fname'] + " " + submission_details['Contact_Lname']
    question = submission_details['Contact_Question']
    content = f"""Dear {user_name},

Thank you for your inquiry.

You asked our helpdesk the following question:
{question}

{response}

If you have any further questions, please feel free to contact us.

Best regards,
Your Helpdesk Team"""

    return content

def update_submission_payload(config, submission_id, key, value):
    """
    Update the payload of a submission in the contact_queue table.

    Args:
        config (dict): The configuration settings for connecting to the MySQL database.
        submission_id (int): The ID of the submission to update.
        key (str): The key of the payload to update.
        value (str): The new value for the payload key.

    Raises:
        ValueError: If no submission is found with the given ID.
    """
    conn = connect_to_mysql(config)
    cursor = conn.cursor()
    query = "SELECT Payload FROM contact_queue WHERE Contact_ID = %s"
    cursor.execute(query, (submission_id,))
    row = cursor.fetchone()
    if row:
        if row[0]:
            payload = json.loads(row[0])
        else:
            payload = {}
        payload[key] = value
        payload_json = json.dumps(payload)
        update_query = "UPDATE contact_queue SET Payload = %s WHERE Contact_ID = %s"
        cursor.execute(update_query, (payload_json, submission_id))
        conn.commit()
        cursor.close()
        conn.close()
    else:
        cursor.close()
        conn.close()
        raise ValueError(f"No submission found with ID: {submission_id}")

def update_submission(config, submission_id, field_name, input_value):
    """
    Update a submission in the contact_queue table with the specified field value.

    Args:
        config (dict): A dictionary containing the configuration details for connecting to the MySQL database.
        submission_id (int): The ID of the submission to update.
        field_name (str): The name of the field to update.
        input_value: The new value to set for the specified field.

    Returns:
        None
    """
    print(f"Updating submission {submission_id} with {field_name} = {input_value}")
    conn = connect_to_mysql(config)
    cursor = conn.cursor()
    query = f"UPDATE contact_queue SET {field_name} = %s WHERE Contact_ID = %s"
    cursor.execute(query, (input_value, submission_id))
    conn.commit()
    cursor.close()
    conn.close()

# Streamlit app main function
def main():
    # Load the configuration settings
    config = load_json_config(config_path)
    #Page navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Go to", ["Member Contact Form", "Submission Details"])

    if page == "Member Contact Form":
        member_contact_form(config)
    elif page == "Submission Details":
        display_submissions(config)
    
    #Could make Review Closed Submissions a separate page

if __name__ == "__main__":
    print("Starting Streamlit app...")
    main()