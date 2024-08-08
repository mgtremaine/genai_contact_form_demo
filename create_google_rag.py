#!/usr/bin/env python3

# Refer to llamaindex_example.py for API usage.
# Author: Mike Tremaine 
# Date: 2024-07-15 
# Version: 1.0
# License: MIT

# Script: create_google_rag.py

"""Description: This script uploads files to GCS and creates a llamaindex RAG corpus.
    The idea is that you can create any number of corpus for different datasets.
    from any number of files. This script will upload the files to GCS and then
    create a RAG corpus in Vertex AI. The script will also write out a json file
    with the corpus config for use in the Query Script.

    Args:
        -p project_id (str): Your Google Cloud project ID.
        -n display_name (str): Display name for your dataset.
        -g gcs_source_uri (str): GCS URI for your data file.
        -l location (str): Google Server Location for the operation.
        -c credentials_path (str): Path to your service account key.json.
        -u source_dir (str): Directory to upload files from.
        This one is hardcode currenty to use the text-embedding-004 model.
        embedding_model (str): Embedding model to use (default: "text-embedding-004").
"""

import argparse, os, time
import json
from vertexai.preview import rag
import vertexai

# Define a global default location
DEFAULT_LOCATION = 'us-central1'

def initialize_vertex_ai(project_id, location=DEFAULT_LOCATION, credentials_path=None):
    if credentials_path:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    """Initializes Vertex AI with the given project ID and location."""
    vertexai.init(project=project_id, location=location)

def create_corpus_and_import_files(project_id, display_name, paths, embedding_model="text-embedding-004"):
    """Creates a RAG Corpus, imports files, and sets up for indexing."""

    # Configure embedding model
    embedding_model_config = rag.EmbeddingModelConfig(
        publisher_model=f"publishers/google/models/{embedding_model}"
    )

    # Create RagCorpus
    rag_corpus = rag.create_corpus(
        display_name=display_name,
        embedding_model_config=embedding_model_config,
    )

    # Import Files to the RagCorpus
    response = rag.import_files(
        rag_corpus.name,
        paths,
        chunk_size=512,  # Optional
        chunk_overlap=100,  # Optional
        max_embedding_requests_per_min=900,  # Optional
    )

    print(f"Files imported to corpus {rag_corpus.name} with response: {response}")
    return rag_corpus

def upload_files_to_gcs(bucket_name, display_name, source_dir, credentials_path):
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    uploaded_files = []

    for filename in os.listdir(source_dir):
        local_path = os.path.join(source_dir, filename)
        #Upload file to GCS    
        if os.path.isfile(local_path):
            blob = bucket.blob(f"{display_name}/{filename}")
            blob.upload_from_filename(local_path)
            uploaded_files.append(filename)
            print(f"Uploaded {filename} to {bucket_name}/{display_name}")

    return uploaded_files

def create_corpus_config(corpus_name, project_id, location):
    """Create a configuration file for the corpus."""
    config = {
        "corpus_name": corpus_name,
        "project_id": project_id,
        "location": location
    }
    with open(f"{project_id}_corpus_config.json", "w") as f:
        json.dump(config, f)


def main(project_id, display_name, gcs_source_uri, location, credentials_path, source_dir, embedding_model="text-embedding-004"):
    #Set some variables
    bucket_name = gcs_source_uri.split("//")[1].split("/")[0] 
    paths = [gcs_source_uri] #rag_corpus requires a list of paths
    # Initialize Vertex AI API
    initialize_vertex_ai(project_id, location, credentials_path)
    #Upload our files to GCS
    file_list = upload_files_to_gcs(bucket_name, display_name, source_dir, credentials_path)
    #Create the corpus and import the files
    rag_corpus = create_corpus_and_import_files(project_id, display_name, paths, embedding_model)
    #Write out a json file with the corpus config for use in the Query Script
    create_corpus_config(rag_corpus.name, project_id, location)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload files to GCS and create a llamaindex RAG corpus.")
    parser.add_argument("-d", "--directory", help="Directory to upload files from", default="./upload")
    parser.add_argument("-p", "--project_id", required=True, help="Your Google Cloud project ID", default="demo-genai")
    parser.add_argument("-c", "--credentials_path", required=True, help="Path to your service account key.json", default="./key.json")
    parser.add_argument("-n", "--corpus_display_name", required=True, help="Display name for your dataset")
    parser.add_argument("-g", "--gcs_source_uri", required=True, help="GCS URI for your data file", default="gs://demo_genai_docs")
    parser.add_argument("-l", "--location", type=str, default=DEFAULT_LOCATION, help='Location for the operation (default: %(default)s)')
    args = parser.parse_args()

    #Set the variables
    project_id = args.project_id
    display_name =  args.corpus_display_name
    gcs_source_uri = args.gcs_source_uri
    location = args.location
    credentials_path = args.credentials_path
    source_dir = args.directory

    #Call Main
    main(project_id, display_name, gcs_source_uri, location, credentials_path, source_dir)
