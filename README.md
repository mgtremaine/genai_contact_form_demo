# genai_contact_form_demo
Generative AI backed Contact Form written in Python/Streamlit.

## Setup Instructions

### Step 1: Create Corpus via `create_google_rag.py`

To create a corpus and generate a `<project_id>_config_corpus.json` file, follow these steps:

1. Ensure you have the necessary dependencies installed. You can install them using:
    ```sh
    pip install -r requirements.txt
    ```

2. Run the `create_google_rag.py` script with the required arguments:
    ```sh
    python create_google_rag.py -d <directory> -p <project_id> -c <credentials_path> -n <corpus_display_name> -g <gcs_source_uri> -l <location>
    ```

    - `-d, --directory`: Directory to upload files from (default: [`./upload`])
    - `-p, --project_id`: Your Google Cloud project ID (default: [`vsp-genai`])
    - `-c, --credentials_path`: Path to your service account key.json (default: [`./key.json`])
    - `-n, --corpus_display_name`: Display name for your dataset
    - `-g, --gcs_source_uri`: GCS URI for your data file (default: [`gs://vision_benefits_docs`])
    - `-l, --location`: Location for the operation (default: [`us-central1`])

3. This script will:
    - Upload files to Google Cloud Storage (GCS)
    - Create a RAG Corpus
    - Import files into the RAG Corpus
    - Generate a `config_corpus.json` file for use in the query script

### Step 2: Query the Corpus off the comand-line via [`google_rag_query.py`] google_rag_query.py")

To query the corpus using the generated `config_corpus.json` file, follow these steps:

1. Run the [`google_rag_query.py`] script with the required arguments:
    ```sh
    python google_rag_query.py -c <config_corpus.json> -q <query_text>
    ```

    - `-c, --corpus_config`: Path to the corpus configuration file
    - `-q, --query_text`: The query text to search in the corpus

2. This script will:
    - Initialize Vertex AI
    - Query the corpus using the provided query text
    - Return the response from the RAG model and Gemini using Vertex AI form google.

### Additional Scripts 

- [`contact_helpdesk.py`] contact_helpdesk.py"): Handles the contact form submission and response.
    This is full demo in streamlit and can use OpenAI via Baserun. It includes as `google_rag_query.py` as 
    an import.
- [`contact_utils.py`] Contains utility functions for loading configurations and connecting to MySQL.

### License

This project is licensed under the MIT License.# genai_contact_form_demo
Generative AI backed Contact Form written in Python/Streamlit.
