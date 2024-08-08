#!/usr/bin/env python3

#Script: google_rag_query.py
#Description: This script queries a corpus using RAG from Vertex AI.
# It can be used as module from other scripts. Or run as a standalone script.

# Author: Mike Tremaine 
# Date: 2024-07-17 
# Version: 1.0
# License: MIT

import argparse, os, time
import json
from vertexai.preview import rag
from vertexai.preview.generative_models import GenerativeModel, Tool
import vertexai
import mysql.connector
import pandas as pd

#Import the shared functions
from contact_utils import load_json_config, connect_to_mysql

# Define a global default location
DEFAULT_LOCATION = 'us-central1'

def fetch_submission_details(config, contact_id):
    mysql_conn = connect_to_mysql(config)
    mem_cursor = mysql_conn.cursor()
    try:
        mem_cursor.execute(f"SELECT * FROM contact_queue WHERE Contact_ID = {contact_id}")
        field_names = [desc[0] for desc in mem_cursor.description]
        record = mem_cursor.fetchone()
        submission_info = process_record(record, field_names)
    except:
        submission_info = {}

    # close the cursor
    mem_cursor.close()
    #close connection
    mysql_conn.close()
    return submission_info

def get_member_data(config, record_dict):
    mysql_conn = connect_to_mysql(config)
    # Get some possible identifying information
    email = record_dict["Contact_Email"]
    name = record_dict["Contact_Fname"] + " " + record_dict["Contact_Lname"]
    dob = record_dict["Contact_DOB"]
    # Write your query using the identifying information beware that you will be passing this
    # to the LLM as additional context if there is PII in the data
    mem_cursor = mysql_conn.cursor()
    # handle no results with a try except block
    try:
        mem_cursor.execute(
            f"SELECT * FROM Member_Data WHERE `Email_Address` = '{email}' OR `Member_Name` = '{name}'"
        )
        field_names = [desc[0] for desc in mem_cursor.description]

        # return the data as JSON string with the field names as keys
        record = mem_cursor.fetchone()
        known_info = process_record(record, field_names)
    except:
        known_info = {}

    # close the cursor
    mem_cursor.close()
    #close connection
    mysql_conn.close()
    return known_info

def initialize_vertex_ai(project_id, location=DEFAULT_LOCATION, credentials_path=None):
    if credentials_path:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    """Initializes Vertex AI with the given project ID and location."""
    vertexai.init(project=project_id, location=location)

def load_json_config(config_path):
    with open(config_path, 'r') as file:
        return json.load(file)

def process_record(record, field_names):
    """
    Process a record fetched from the database and return a dictionary with field names as keys.
    """
    if record is None:
        return {}
            
    processed_record = {}
    for i, value in enumerate(record):
        processed_record[field_names[i]] = value
            
    return processed_record

def query_corpus(corpus_config, credentials_path, query_text):
    rag_name = corpus_config['corpus_name']
    response = rag.retrieval_query(
        rag_resources=[
            rag.RagResource(
                rag_corpus=rag_name,
                # Supply IDs from `rag.list_files()`.
                #rag_file_ids=["rag-file-1", "rag-file-2", ...],
            )
        ],
        text=query_text,
        similarity_top_k=3,  # Optional
        vector_distance_threshold=0.5,  # Optional
    )
    return response 

def enhanced_query_corpus(corpus_config, credentials_path, known_info, myquestion):

    # Create a RAG retrieval tool
    rag_retrieval_tool = Tool.from_retrieval(
        retrieval=rag.Retrieval(
            source=rag.VertexRagStore(
                rag_resources=[
                    rag.RagResource(
                        rag_corpus=corpus_config['corpus_name'],  # Currently only 1 corpus is allowed.
                )
            ],
            similarity_top_k=3,  # Optional
            vector_distance_threshold=0.5,  # Optional
            ),
        )
    )

    #Set System
    system_list = [ 
        "You are an expert assistance extracting information from context provided.",
        "Answer the question based on the context. Be concise and do not hallucinate.",
        "Respond with the information you have in polite and professional manner.",
        "If you do not have the information just say so and start the reply with [NONE].",
        "Any query for Member ID or Member Number should use Brand_Member_ID as context but refer to it as Member ID.",
        "Responsed in markdown format to make it easy to read.",
    ]
    # Set prompt
    prompt = f"""
        Context:  Additional data {known_info}
        Question:  
        {myquestion}
        Answer: '
    """
    content = [ prompt ]

    #Make system_list + prompt a single string this is missing the RAG context
    full_prompt = ' '.join(system_list) + prompt

    # Create a gemini-pro model instance
        #model_name="gemini-1.5-flash-001", tools=[rag_retrieval_tool]
    rag_model = GenerativeModel(
        model_name="gemini-1.5-pro-001", tools=[rag_retrieval_tool], 
        system_instruction=system_list,
    )

    # Generate response
    response = rag_model.generate_content(content)
    #return prompt and response
    return full_prompt, response

def get_rag_prompt(corpus_config_path, credentials_path, config, contact_id):
    # Load the corpus configuration
    corpus_config = load_json_config(corpus_config_path)

    #Initialize Vertex AI API
    initialize_vertex_ai(corpus_config['project_id'], corpus_config['location'], credentials_path)

    # Get the record from the database
    submission_info = fetch_submission_details(config, contact_id)
    myquestion = submission_info['Contact_Question']

    # Get additional information from the database
    known_info = get_member_data(config, submission_info)

    # Query the corpus
    answer = query_corpus(corpus_config, credentials_path, submission_info['Contact_Question'])
    rag_reply = ""
    contexts_list = answer.contexts.contexts
    if contexts_list:
        rag_reply = contexts_list[0].text  # Get the first context
    else:
        rag_reply = ""

    #Set System
    system_list = [ 
        "You are an expert assistance extracting information from context provided.",
        "Answer the question based on the context. Be concise and do not hallucinate.",
        "Respond with the information you have in polite and professional manner.",
        "If you do not have the information just say so and start the reply with [NONE].",
        "Any query for Member ID or Member Number should use Brand_Member_ID as context but refer to it as Member ID.",
        "Responsed in markdown format to make it easy to read.",
    ]
    # Set prompt
    prompt = f"""
        Context: {rag_reply} with Additional data {known_info}
        Question:  
        {myquestion}
        Answer: '
    """

    #Make system_list + prompt a single string this is missing the RAG context
    full_prompt = ' '.join(system_list) + prompt

    return full_prompt

def get_rag_response(corpus_config_path, credentials_path, config, contact_id):
    # Load the corpus configuration
    corpus_config = load_json_config(corpus_config_path)

    #Initialize Vertex AI API
    initialize_vertex_ai(corpus_config['project_id'], corpus_config['location'], credentials_path)

    # Get the record from the database
    submission_info = fetch_submission_details(config, contact_id)

    # Get additional information from the database
    known_info = get_member_data(config, submission_info)

    # Query the corpus
    prompt, answer = enhanced_query_corpus(corpus_config, credentials_path, known_info, submission_info['Contact_Question'])
    reply = ""
    #return answer.content.parts.text
    for candidate in answer.candidates:
        print(candidate)
        if candidate.content.role == "model":
            for part in candidate.content.parts:
                reply = part.text
        break  # Assuming you only need the first match

    return prompt, reply

def main():
    parser = argparse.ArgumentParser(description='Query a corpus using RAG from Vertex AI.')
    parser.add_argument('-i', '--contact_id', required=True, help='Contact_ID from contact_queue table.')
    args = parser.parse_args()

    #Load the config.json with db setttings
    app_config = load_json_config("config.json")
    # Load the corpus configuration
    corpus_config = load_json_config("vsp-genai_corpus_config.json")
    #Set path to credentials (current directory) + /key.json
    credentials = os.path.join(os.getcwd(), 'key.json')

    # Initialize Vertex AI API
    initialize_vertex_ai(corpus_config['project_id'], corpus_config['location'], credentials)

    # Get the record from the database
    submission_info = fetch_submission_details(app_config, args.contact_id)

    # Get additional information from the database
    known_info = get_member_data(app_config, submission_info)

    # Query the corpus
    #results = query_corpus(corpus_config, args.credentials, args.query)
    #results = query_corpus(corpus_config, credentials, submission_info['Contact_Question'])
    #contexts_list = results.contexts.contexts
    #prompt_context = ""
    #prompt_context = contexts_list[0].text  # Get the first context
    prompt, answer = enhanced_query_corpus(corpus_config, credentials, known_info, submission_info['Contact_Question'])
    for candidate in answer.candidates:
        if candidate.content.role == "model":
            for part in candidate.content.parts:
                print(part.text)
        break  # Assuming you only need the first match

    print(prompt)
    print(answer)

if __name__ == "__main__":
    main()