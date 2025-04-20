from flask import jsonify
import requests
from datetime import datetime
import time
import shutil
import os
import fitz

# HELPER FUNCTIONS

# Function to request database tables
def fetch_tables(table_names, base_api_url):
    """
        table_names (list): List of data base tables to retrieve
        base_api_url (string): base API URL to interact with database; to be combined with a table name
        tables (dict): dictionary of database tables
    """
    tables = {}
    try:
        for table_name in table_names: # iterate through list of tables
            final_api_url = base_api_url + table_name # set final request URL
            print(final_api_url) # print to verify
            response = requests.get(final_api_url) # get HTTP response
            table = response.json() # parse JSON data
            tables[table_name] = table # store table in dictionary of tables; Key = table_name, Value = table data
            print("Successfully retrieved table entries.")
            
    except requests.exceptions.HTTPError as http_err:
        return jsonify({"message": f"HTTP error occurred: {str(http_err)}"}), 502
    except requests.exceptions.Timeout as timeout_err:
        return jsonify({"message": f"Request timed out: {str(timeout_err)}"}), 504
    except requests.exceptions.InvalidURL as url_err:
        return jsonify({"message": f"The database URL provided was somehow Invalid: {str(url_err)}"}), 400
    except requests.exceptions.InvalidJSONError as json_err:
        return jsonify({"message": f"A JSON error occurred: {str(json_err)}"}), 502
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}"), 500

    return tables

# Matching list indices to id numbers for easier searching
def index_tables(table_names, tables):
    """
        table_names (list): List of data tables to index
        Note: Assumes that patient or doctor ids are stored with key 'id'
        Note: Assumes all patient-related tables are sorted the same
    """
    table_indexers = {name: {} for name in table_names} # dynamically create dictionary for each table

    for table_name in table_names: # Iterate through list of tables
        index = 0
        for entry in tables[table_name]: # Iterate through each table entry
            table_indexers[table_name][entry['id']] = index
            index = index+1

    return table_indexers

# Function to abbreviate provinces to 2 letter code
def getProvAbbrv(province):
    """
        province (string): name of province from database
    """
    if len(province) == 2:
        return province # return if already 2 letters

    if province == "Alberta":
        return "AB"
    elif province == "British Columbia":
        return "BC"
    elif province == "Manitoba":
        return "MB"
    elif province == "New Brunswick":
        return "NB"
    elif province == "Newfoundland and Labrador":
        return "NL"
    elif province == "Nova Scotia":
        return "NS"
    elif province == "Northwest Territories":
        return "NT"
    elif province == "Nunavut":
        return "NU"
    elif province == "Ontario":
        return "ON"
    elif province == "Prince Edward Island":
        return "PE"
    elif province == "Quebec":
        return "QC"
    elif province == "Saskatchewan":
        return "SK"
    elif province == "Yukon":
        return "YK"
    else:
        return "NA"
    
# Function to parse date of birth in database
def parseDoB(date):
    """
        date (string): date stored in database in form: 2023-04-06T00:00:00.00Z
        date_dict (dict): dictionary storing year, month, and day
    """
    if date == None:
        return {
            'year': '0000',
            'month': '00',
            'day': '00'
        }

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception as e:
        print(f"Warning: Failed to parse date '{date}")
        return {
            'year': '0000',
            'month': '00',
            'day': '00'
        }

    date_dict = {
        'year': str(date_obj.year),
        'month': str(date_obj.month),
        'day': str(date_obj.day)
    }
    return date_dict

# Function to return F or M based on patient sex
def getSex(sex):
    """
        sex (string): string denoting sex, 'Male' or 'Female' stored in database
    """
    if sex == "Male":
        return "M"
    elif sex == "Female":
        return "F"
    else:
        return "Off"
    
# Function to retrieve basic patient and doctor info, returned as a dictionary
def getBasicInfo(doctor_id, patient_id, BASE_API_URL, TABLE_NAMES, FIELD_CONFIG):
    """
        doctor_id (int): id corresponding to doctor in database
        patient_id (int): id corresponding to patient in database
    """
    tables = fetch_tables(TABLE_NAMES, BASE_API_URL)
    table_indexers = index_tables(TABLE_NAMES, tables)
    print("Successfully retrieved tables.")

    # Retrieve dictionaries of information
    try:
        doctor = tables["doctors_registration"][table_indexers["doctors_registration"][doctor_id]]
        patient = tables["patients_registration"][table_indexers["patients_registration"][patient_id]]
        patient_health_info = tables["patients_pathology"][table_indexers["patients_registration"][patient_id]] # Assume patient sorting lines up
    except IndexError as e:
        return jsonify({"message": "Data index out of range. Please check the ID indexer."}), 500
    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred: {str(e)}"}), 500
    
    if FIELD_CONFIG:
        # A field is config["fields"]["field_name"] where field_name is e.g. "doctor_full_name"
        # Access field_xref like field_xref = config["fields"]["field_name"]["field_xref"]
        basicInfo = {
            FIELD_CONFIG["fields"]["doctor_full_name"]["field_xref"]: doctor["Fname"] + " " + doctor["Mname"] + " " + doctor["Lname"],
            FIELD_CONFIG["fields"]["doctor_phone"]["field_xref"]: doctor["MobileNumber"],
            FIELD_CONFIG["fields"]["doctor_full_address"]["field_xref"]: doctor["Location2"] + " " + doctor["Location1"] + ", " + doctor["City"] + ", " + getProvAbbrv(doctor["Province"]) + ", " + doctor["PostalCode"],
            FIELD_CONFIG["fields"]["doctor_license_number"]["field_xref"]: doctor["Medical_LICENSE_Number"],
            FIELD_CONFIG["fields"]["patient_health_no"]["field_xref"]: patient["HCardNumber"],
            FIELD_CONFIG["fields"]["patient_birth_year"]["field_xref"]: parseDoB(patient["date_of_birth"])['year'],
            FIELD_CONFIG["fields"]["patient_birth_month"]["field_xref"]: parseDoB(patient["date_of_birth"])['month'],
            FIELD_CONFIG["fields"]["patient_birth_day"]["field_xref"]: parseDoB(patient["date_of_birth"])['day'],
            FIELD_CONFIG["fields"]["patient_province"]["field_xref"]: getProvAbbrv(patient["Province"]),
            FIELD_CONFIG["fields"]["patient_prnumber"]["field_xref"]: patient["PRNumber"],
            FIELD_CONFIG["fields"]["patient_phone"]["field_xref"]: patient["MobileNumber"],
            FIELD_CONFIG["fields"]["patient_health_info"]["field_xref"]: patient_health_info["pathology"],
            FIELD_CONFIG["fields"]["patient_last_name"]["field_xref"]: patient["LName"],
            FIELD_CONFIG["fields"]["patient_first_name"]["field_xref"]: patient["FName"],
            FIELD_CONFIG["fields"]["patient_middle_name"]["field_xref"]: patient["MName"],
            FIELD_CONFIG["fields"]["patient_sex"]["field_xref"]: getSex(patient["Gender"]),
            FIELD_CONFIG["fields"]["patient_full_address"]["field_xref"]: patient["Location"] + " " + patient["Address"] + ", " + patient["City"] + ", " + getProvAbbrv(patient["Province"]) + ", " + patient["PostalCode"]
        }
    else:
        print("Error: No config")
        return
    
    return basicInfo

# Function to match a transcribed voice input to a pdf field
def getFieldMatch(text, config, basicInfo):
    """
        text (string): string representing a voice input transcription
        config (dict): dictionary of mappings from loaded json config
        basicInfo (dict): dictionary of basic patient and doctor information
    """
    text = text.lower().strip() # remove spaces and make lower case
    fields = {}

    # Check one by one for matching pdf fields
    if text.find("glucose") >= 0: # Glucose found
        fields[config["fields"]["glucose"]["field_xref"]] = config["fields"]["glucose"]["on_state"]
        if text.find("random") >= 0: # Random glucose test
            fields[config["fields"]["glucose_test_random"]["field_xref"]] = config["fields"]["glucose_test_random"]["on_state"]
        elif text.find("fasting") >= 0: # Fasting glucose test
            fields[config["fields"]["glucose_test_fasting"]["field_xref"]] = config["fields"]["glucose_test_random"]["on_state"]
        return fields
    elif text.find("hba1c") >= 0: # HbA1C test
        fields[config["fields"]["hba1c"]["field_xref"]] = config["fields"]["hba1c"]["on_state"]
        return fields
    elif text.find("creatinine") >= 0 and text.find("albumin") == -1: # Creatinine (eGFR) test
        fields[config["fields"]["creatinine"]["field_xref"]] = config["fields"]["creatinine"]["on_state"]
        return fields
    elif text.find("uric") >= 0: # Uric acid test
        fields[config["fields"]["uric_acid"]["field_xref"]] = config["fields"]["uric_acid"]["on_state"]
        return fields
    elif text.find("sodium") >= 0: # Sodium test
        fields[config["fields"]["sodium"]["field_xref"]] = config["fields"]["sodium"]["on_state"]
        return fields
    elif text.find("potassium") >= 0: # Potassium test
        fields[config["fields"]["potassium"]["field_xref"]] = config["fields"]["potassium"]["on_state"]
        return fields
    elif text.find("alt") >= 0: # ALT test
        fields[config["fields"]["alt"]["field_xref"]] = config["fields"]["alt"]["on_state"]
        return fields
    elif text.find("phosphatase") >= 0: # Alk. Phosphatase test
        fields[config["fields"]["alk_phosphatase"]["field_xref"]] = config["fields"]["alk_phosphatase"]["on_state"]
        return fields
    elif text.find("bilirubin") >= 0 and text.find("neonatal") == -1: # Bilirubin test
        fields[config["fields"]["bilirubin"]["field_xref"]] = config["fields"]["bilirubin"]["on_state"]
        return fields
    elif text.find("albumin") >= 0 and text.find("creatinine") == -1: # Albumin test
        fields[config["fields"]["albumin"]["field_xref"]] = config["fields"]["albumin"]["on_state"]
        return fields
    elif text.find("lipid assessment") >= 0: # Lipid assessment test
        fields[config["fields"]["lipid_assessment"]["field_xref"]] = config["fields"]["lipid_assessment"]["on_state"]
        return fields
    elif text.find("albumin") >= 0 and text.find("creatinine") >= 0 or text.find("albumin") >= 0 and text.find("ratio") >= 0 or text.find("creatinine") >= 0 and text.find("ratio") >= 0: # Albumin / Creatinine ratio test
        fields[config["fields"]["albumin_creatinine_ratio"]["field_xref"]] = config["fields"]["albumin_creatinine_ratio"]["on_state"]
        return fields
    elif text.find("urinalysis") >= 0: # Urinalysis (chemical) test
        fields[config["fields"]["urinalysis"]["field_xref"]] = config["fields"]["urinalysis"]["on_state"]
        return fields
    elif text.find("neonatal") >= 0: # Neonatal bilirubin test
        fields[config["fields"]["neonatal_bilirubin"]["field_xref"]] = config["fields"]["neonatal_bilirubin"]["on_state"]
        fields[config["fields"]["neonatal_doctor_phone"]["field_xref"]] = basicInfo[config["fields"]["doctor_phone"]["field_xref"]]
        fields[config["fields"]["neonatal_patient_phone"]["field_xref"]] = basicInfo[config["fields"]["patient_phone"]["field_xref"]]
        return fields
    elif text.find("therapeutic") >= 0: # Therapeutic drug monitoring
        fields[config["fields"]["therapeutic_drug"]["field_xref"]] = config["fields"]["therapeutic_drug"]["on_state"]
        return fields
    elif text.find("cbc") >= 0: # CBC test
        fields[config["fields"]["cbc"]["field_xref"]] = config["fields"]["cbc"]["on_state"]
        return fields
    elif text.find("prothrombin") >= 0: # Prothrombin time test
        fields[config["fields"]["prothrombin_time"]["field_xref"]] = config["fields"]["prothrombin_time"]["on_state"]
        return fields
    elif text.find("pregnancy") >= 0: # Pregnancy (Urine) test
        fields[config["fields"]["pregnancy_urine"]["field_xref"]] = config["fields"]["pregnancy_urine"]["on_state"]
        return fields
    elif text.find("mononucleosis") >= 0: # Mononucleosis screen
        fields[config["fields"]["mononucleosis_screen"]["field_xref"]] = config["fields"]["mononucleosis_screen"]["on_state"]
        return fields
    elif text.find("rubella") >= 0: # Rubella test
        fields[config["fields"]["rubella"]["field_xref"]] = config["fields"]["rubella"]["on_state"]
        return fields
    elif text.find("prenatal") >= 0 and text.find("antibody") >= 0 or text.find("prenatal") >= 0 and text.find("screen") >= 0 or text.find("antibody") >= 0 and text.find("screen") >= 0: # Prenatal: ABO, RhD...
        fields[config["fields"]["prenatal"]["field_xref"]] = config["fields"]["prenatal"]["on_state"]
        return fields
    elif text.find("prenatal") >= 0 and text.find("repeat") >= 0: # Repeat prenatal antibodies
        fields[config["fields"]["repeat_prenatal_antibodies"]["field_xref"]] = config["fields"]["repeat_prenatal_antibodies"]["on_state"]
        return fields
    elif text.find("cervical") >= 0: # Cervical test
        fields[config["fields"]["cervical"]["field_xref"]] = config["fields"]["cervical"]["on_state"]
        return fields
    elif text.find("vaginal") >= 0:
        if text.find("rectal") >= 0 or text.find("group") >= 0 or text.find("strep") >= 0: # Vaginal / Rectal - Group B Strep
            fields[config["fields"]["vaginal_rectal"]["field_xref"]] = config["fields"]["vaginal_rectal"]["on_state"]
            return fields
        else: # Vaginal test
            fields[config["fields"]["vaginal"]["field_xref"]] = config["fields"]["vaginal"]["on_state"]
            return fields
    elif text.find("rectal") >= 0: # Vaginal / Rectal - Group B Strep
        fields[config["fields"]["vaginal_rectal"]["field_xref"]] = config["fields"]["vaginal_rectal"]["on_state"]
        return fields
    elif text.find("chlamydia") >= 0: # Chlamydia test
        fields[config["fields"]["chlamydia"]["field_xref"]] = config["fields"]["chlamydia"]["on_state"]
        return fields
    elif text.find("gc") >= 0: # GC test
        fields[config["fields"]["gc"]["field_xref"]] = config["fields"]["gc"]["on_state"]
        return fields
    elif text.find("sputum") >= 0: # Sputum test
        fields[config["fields"]["sputum"]["field_xref"]] = config["fields"]["sputum"]["on_state"]
        return fields
    elif text.find("throat") >= 0: # Throat test
        fields[config["fields"]["throat"]["field_xref"]] = config["fields"]["throat"]["on_state"]
        return fields
    elif text.find("wound") >= 0: # Wound test
        fields[config["fields"]["wound"]["field_xref"]] = config["fields"]["wound"]["on_state"]
        specificWound = ""
        for word in text.split("wound"):
            specificWound = specificWound + word.strip() + " "
        fields[config["fields"]["specify_wound"]["field_xref"]] = specificWound
        return fields
    elif text.find("urine") >= 0 and text.find("albumin") == -1 and text.find("creatinine") == -1 and text.find("ratio") == -1 and text.find("pregnancy") == -1: # Urine test
        fields[config["fields"]["urine"]["field_xref"]] = config["fields"]["urine"]["on_state"]
        return fields
    elif text.find("culture") >= 0: # Stool culture
        fields[config["fields"]["stool_culture"]["field_xref"]] = config["fields"]["stool_culture"]["on_state"]
        return fields
    elif text.find("stool") >= 0 and text.find("ova") >= 0 or text.find("stool") >= 0 and text.find("parasites") >= 0: # Stool Ova & Parasites
        fields[config["fields"]["stool_ova_parasites"]["field_xref"]] = config["fields"]["stool_ova_parasites"]["on_state"]
        return fields
    elif text.find("swabs") >= 0: # Other swabs
        fields[config["fields"]["other_swabs"]["field_xref"]] = config["fields"]["other_swabs"]["on_state"]
        return fields
    elif text.find("acute") >= 0: # Acute Hepatitis
        fields[config["fields"]["viral_hep_acute"]["field_xref"]] = config["fields"]["viral_hep_acute"]["on_state"]
        return fields
    elif text.find("chronic") >= 0: # Chronic Hepatisis
        fields[config["fields"]["viral_hep_chronic"]["field_xref"]] = config["fields"]["viral_hep_chronic"]["on_state"]
        return fields
    elif text.find("status") >= 0 or text.find("exposure") >= 0: # Immune Status / Previous Exposure
        fields[config["fields"]["viral_hep_immune"]["field_xref"]] = config["fields"]["viral_hep_immune"]["on_state"]
        if text.find("hepatitis a") >= 0:
            fields[config["fields"]["viral_hep_immune_a"]["field_xref"]] = config["fields"]["viral_hep_immune_a"]["on_state"]
        elif text.find("hepatitis b") >= 0:
            fields[config["fields"]["viral_hep_immune_b"]["field_xref"]] = config["fields"]["viral_hep_immune_b"]["on_state"]
        elif text.find("hepatitis c") >= 0:
            fields[config["fields"]["viral_hep_immune_c"]["field_xref"]] = config["fields"]["viral_hep_immune_c"]["on_state"]
        return fields
    elif text.find("total") >= 0: # Total PSA
        fields[config["fields"]["total_psa"]["field_xref"]] = config["fields"]["total_psa"]["on_state"]
        return fields
    elif text.find("free") >= 0: # Free PSA
        fields[config["fields"]["free_psa"]["field_xref"]] = config["fields"]["free_psa"]["on_state"]
        return fields
    elif text.find("vitamin") >= 0 or text.find("hydroxy") >= 0: # Vitamin D (25-Hydroxy)
        if text.find("insured") >= 0:
            fields[config["fields"]["insured_vitd"]["field_xref"]] = config["fields"]["insured_vitd"]["on_state"]
        elif text.find("uninsured") >= 0:
            fields[config["fields"]["uninsured_vitd"]["field_xref"]] = config["fields"]["uninsured_vitd"]["on_state"]
        return fields

# Function to write a pdf copy and return the filepath
def fillPDF(SAVE_FOLDER, field_data):
    """
        SAVE_FOLDER (string): directory to save temporary files to
        field_data (dict): dictionary of data to fill the pdf with
    """

    # Define copy path
    original_path = "requisition_form.pdf"
    temp_copy_path = os.path.join(SAVE_FOLDER, "rquisition_form_copy.pdf")
    filled_pdf_path = ""

    try:
        # Step 1: Copy the original PDF
        shutil.copy(original_path, temp_copy_path)
        print(f"Created a working copy: {temp_copy_path}")

        # Step 2: Open the temporary copy
        doc = fitz.open(temp_copy_path)

        # Step 3: Fill the fields
        for page in doc:
            for widget in page.widgets():
                if widget.xref in field_data:
                    print(f"Updating field: {widget.xref}")
                    widget.field_value = field_data[widget.xref]
                    widget.update()

        # Step 4: Save the filled PDF
        filled_pdf_path = os.path.join(
            SAVE_FOLDER,
            f"requisition_form_filled_{int(time.time())}.pdf"
        )

        doc.save(filled_pdf_path, garbage=0)
        print(f"Filled PDF saved to {filled_pdf_path}")

    except Exception as e:
        return jsonify({"message": f"An unexpected error occurred during PDF processing: {str(e)}"}), 500

    finally:
        # Always close document if opened
        try:
            doc.close()
        except:
            pass
        # Always attempt to remove the temp copy
        if os.path.exists(temp_copy_path):
            try:
                os.remove(temp_copy_path)
                print(f"Temporary copy {temp_copy_path} deleted.")
            except Exception as e:
                print(f"Warning: Could not delete temp copy. {e}")

    return filled_pdf_path

    