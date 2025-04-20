from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import os
import json
from dotenv import load_dotenv
from helpers import getBasicInfo, getFieldMatch, fillPDF

app = Flask(__name__)
CORS(app)

# Load environment variables from .env file
load_dotenv()

# Get database API base url
BASE_API_URL = os.getenv('BASE_API_URL')

# Get list of table names
TABLE_NAMES_STRING = os.getenv('TABLE_NAMES')
TABLE_NAMES = [table.strip() for table in TABLE_NAMES_STRING.split(',')] if TABLE_NAMES_STRING else []

# Get pdf mappings
with open('field_config.json', 'r') as f:
    FIELD_CONFIG = json.load(f)

MAX_OTHER_TESTS = 11

SAVE_FOLDER = 'generated_files'
os.makedirs(SAVE_FOLDER, exist_ok=True) # Ensure folder exists

# Load valid IDs once when app starts
with open('valid_ids.json', 'r') as f:
    valid_ids = json.load(f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def receive_text():
    # Data received from front end
    data = request.get_json()
    inputs = data.get('inputs', [])
    patient_id = data.get('patient_id')
    doctor_id = data.get('doctor_id')

    # Check that patient_id and doctor_id are integers
    try:
        patient_id = int(patient_id)
        doctor_id = int(doctor_id)
    except (ValueError, TypeError):
        return jsonify({"message": "Error: Patient ID and Doctor ID must be integers"}), 400
    
    errors = []
    # Validate IDs
    if patient_id not in valid_ids['patients']:
        errors.append(f"Invalid patient ID: {patient_id}")
    if doctor_id not in valid_ids['doctors']:
        errors.append(f"Invalid doctor ID: {doctor_id}")
    if errors:
        return jsonify({"message": "; ".join(errors)}), 400  # Return combined error messages

    if not isinstance(inputs, list):
        return jsonify({"message": "Error: Expected a list of inputs"}), 400

    print("Received transcription list:")
    for idx, entry in enumerate(inputs, 1):
        print(f"{idx}: {entry}")

    # Prepare data to fill the form with
    basic_info = getBasicInfo(doctor_id, patient_id, BASE_API_URL, TABLE_NAMES, FIELD_CONFIG)
    entries = {}
    count = 0
    for line in inputs:
        entry = getFieldMatch(line, FIELD_CONFIG, basic_info)
        if entry: # If we get a match, append to dictionary
            entries = entries | entry
        else: # Address other tests not mapped in config
            if count < MAX_OTHER_TESTS:
                count = count + 1
                entries[FIELD_CONFIG["fields"]["other_tests" + str(count)]["field_xref"]] = line

    field_data = basic_info | entries
    print(field_data)

    # Fill pdf and send generated form as attachment
    filled_pdf_path = fillPDF(SAVE_FOLDER, field_data)
    print(filled_pdf_path)
    return send_file(filled_pdf_path, as_attachment=True)

    

if __name__ == '__main__':
    app.run(debug=True)
    # Testing basic data retrieval and printing
