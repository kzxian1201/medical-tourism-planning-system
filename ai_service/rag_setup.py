import sqlite3
import json
import os
import sys
import logging
import datetime # Import datetime for timestamps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'src', 'db')
DB_FILE = os.path.join(DB_DIR, 'medical_rag.db')
DATA_DIR = os.path.join(BASE_DIR, 'src', 'data')

# Define paths to JSON data files
TREATMENTS_JSON_FILE = os.path.join(DATA_DIR, 'treatments.json')
HOSPITALS_JSON_FILE = os.path.join(DATA_DIR, 'hospitals.json')
DOCTORS_JSON_FILE = os.path.join(DATA_DIR, 'doctors.json')
ACCOMMODATIONS_JSON_FILE = os.path.join(DATA_DIR, 'accommodations.json')
VISA_RULES_JSON_FILE = os.path.join(DATA_DIR, 'visa_rules.json')

def setup_database():
    """
    Creates the SQLite database file and defines table schemas based on the JSON examples.
    This function will also add new columns if they don't exist, to support schema evolution
    without dropping existing data (though it's safer to drop and recreate for major changes).
    """
    # Ensure the directory for the database file exists
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        logging.info(f"Connecting to database: {DB_FILE}")
        logging.info("Ensuring tables are created or updated.")

        # --- 1. Create/Alter 'hospitals' table ---
        # Added accessibility_features and timestamp columns
        # famous_doctors now intended to store doctor IDs as JSON array
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hospitals (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT,
                city TEXT,
                country TEXT,
                geo_location TEXT,          
                contact TEXT,               
                description_overview TEXT,
                medical_professionalism TEXT,   
                international_services INTEGER, 
                geographical_convenience TEXT, 
                brand_reputation TEXT,          
                cost_and_value TEXT,          
                specialties TEXT,               
                treatments_offered TEXT,      
                famous_doctors TEXT,            -- Stores JSON array of doctor IDs
                equipment_list TEXT,            
                tourism_packages TEXT,
                accessibility_features TEXT,    -- New: To store JSON array of accessibility features
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add new columns if they don't exist (for schema evolution without data loss)
        # Note: Adding NOT NULL to existing columns needs default value or careful migration
        # For simplicity, we add them as potentially NULL initially.
        try:
            cursor.execute("ALTER TABLE hospitals ADD COLUMN accessibility_features TEXT")
            logging.info("Added 'accessibility_features' column to 'hospitals' table.")
        except sqlite3.OperationalError:
            pass # Column already exists
        try:
            cursor.execute("ALTER TABLE hospitals ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logging.info("Added 'created_at' column to 'hospitals' table.")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE hospitals ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logging.info("Added 'updated_at' column to 'hospitals' table.")
        except sqlite3.OperationalError:
            pass
        logging.info("Hospitals table schema ensured.")

        # --- 2. Create/Alter 'treatments' table ---
        # associated_specialties is now always a JSON array
        # average_cost_range_usd is split into min/max REAL columns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                associated_specialties TEXT NOT NULL, -- Now stores JSON array of specialties
                description TEXT,
                procedure_complexity_level TEXT,
                typical_hospital_stay TEXT,
                typical_duration TEXT, 
                common_benefits TEXT, 
                potential_risks TEXT, 
                pre_procedure_requirements TEXT, 
                post_procedure_follow_ups TEXT, 
                estimated_market_cost_usd_min REAL, -- New: Min cost as REAL
                estimated_market_cost_usd_max REAL, -- New: Max cost as REAL
                price_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add new columns/alter types if they don't exist
        # For existing data, renaming and adding new columns is complex, but for new columns it's straightforward
        try:
            cursor.execute("ALTER TABLE treatments ADD COLUMN estimated_market_cost_usd_min REAL")
            logging.info("Added 'estimated_market_cost_usd_min' column to 'treatments' table.")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE treatments ADD COLUMN estimated_market_cost_usd_max REAL")
            logging.info("Added 'estimated_market_cost_usd_max' column to 'treatments' table.")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE treatments ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logging.info("Added 'created_at' column to 'treatments' table.")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE treatments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logging.info("Added 'updated_at' column to 'treatments' table.")
        except sqlite3.OperationalError:
            pass
        logging.info("Treatments table schema ensured.")

        # --- 3. Create 'doctors' table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT,                 -- Main specialty
                education TEXT,
                experience_years INTEGER,
                affiliated_hospital_ids TEXT,   -- JSON array of hospital IDs
                contact_info TEXT,              -- JSON object for contact
                bio TEXT,
                languages_spoken TEXT,          -- JSON array for languages
                certifications TEXT,            -- JSON array for certifications
                awards TEXT,                    -- JSON array for awards
                average_rating REAL,
                review_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logging.info("Doctors table schema ensured.")

        # --- 4. Create 'accommodations' table ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accommodations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT,
                country TEXT,
                city TEXT,
                cost_per_night_usd TEXT,        -- Can be TEXT if varied or ranges
                total_cost_estimate_usd TEXT,
                accessibility_features TEXT,    -- JSON array of features
                availability TEXT,
                contact_info TEXT,
                booking_link TEXT,
                notes TEXT,
                nearby_landmarks TEXT,          -- JSON array of landmarks
                image_url TEXT,
                star_rating INTEGER,            -- e.g., 3, 4, 5+ (for prompt q14)
                accommodation_type TEXT,        -- e.g., 'hotel', 'serviced_apartment' (for prompt q13)
                with_kitchen INTEGER,           -- 0 or 1 (for prompt q13)
                pet_friendly INTEGER,           -- 0 or 1 (for prompt q13)
                near_hospital_flag INTEGER,     -- 0 or 1 (for prompt q13)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logging.info("Accommodations table schema ensured.")

        # --- 5. Create 'visa_rules' table ---
        # This table will store visa requirements based on nationality, destination, and purpose
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visa_rules (
                id TEXT PRIMARY KEY, -- e.g., chinese_malaysia_medical
                nationality TEXT NOT NULL,
                destination_country TEXT NOT NULL,
                purpose TEXT NOT NULL, -- e.g., 'medical', 'tourism'
                visa_required TEXT, -- Yes/No/Consult Embassy
                visa_type TEXT,
                stay_duration_notes TEXT,
                required_documents TEXT, -- JSON array
                processing_time_days TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logging.info("Visa Rules table schema ensured.")

        conn.commit()
        logging.info("Database tables created/checked/updated successfully.")

    except sqlite3.Error as e:
        logging.error(f"SQLite error during database setup: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during database setup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def import_data():
    """
    Imports data from JSON files into the SQLite database with proper transformations.
    This function performs an "upsert" (INSERT OR REPLACE) for existing records,
    and updates the 'updated_at' timestamp for each processed record.
    """
    os.makedirs(DATA_DIR, exist_ok=True) # Ensure the data directory exists

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Optimize performance for large imports if needed
        # cursor.execute('PRAGMA journal_mode=WAL;') 
        # cursor.execute('PRAGMA synchronous=NORMAL;')

        total_imported_treatments = 0
        total_imported_hospitals = 0
        total_imported_doctors = 0
        total_imported_accommodations = 0

        logging.info(f"Starting data import from '{DATA_DIR}' to '{DB_FILE}'")

        # --- Import treatments data ---
        logging.info("--- Importing Treatments Data ---")
        treatments_data = []
        if os.path.exists(TREATMENTS_JSON_FILE):
            try:
                with open(TREATMENTS_JSON_FILE, 'r', encoding='utf-8') as f:
                    treatments_data = json.load(f)
                logging.info(f"Found {len(treatments_data)} treatments in {TREATMENTS_JSON_FILE}.")
            except json.JSONDecodeError as jde:
                logging.error(f"Error decoding JSON from {TREATMENTS_JSON_FILE}: {jde}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading {TREATMENTS_JSON_FILE}: {e}. Skipping.", exc_info=True)
        else:
            logging.warning(f"Treatments JSON file not found at {TREATMENTS_JSON_FILE}. Skipping treatment data population.")

        for treatment in treatments_data:
            try:
                # Ensure associated_specialties is always a list, then dump to JSON
                associated_specialties_val = treatment.get('associated_specialties', [])
                if not isinstance(associated_specialties_val, list):
                    associated_specialties_val = [associated_specialties_val]
                associated_specialties_str = json.dumps(associated_specialties_val)

                # Split estimated_market_cost_range_usd_min/max into REAL columns
                estimated_market_cost_usd_min = treatment.get('estimated_market_cost_range_usd_min')
                estimated_market_cost_usd_max = treatment.get('estimated_market_cost_range_usd_max')

                # Handle potential None or non-numeric values for costs
                estimated_market_cost_usd_min = float(estimated_market_cost_usd_min) if estimated_market_cost_usd_min is not None else None
                estimated_market_cost_usd_max = float(estimated_market_cost_usd_max) if estimated_market_cost_usd_max is not None else None

                common_benefits_str = json.dumps(treatment.get('common_benefits', []))
                potential_risks_str = json.dumps(treatment.get('potential_risks', []))
                pre_procedure_requirements_str = json.dumps(treatment.get('pre_procedure_requirements', []))
                post_procedure_follow_ups_str = json.dumps(treatment.get('post_procedure_follow_ups', []))
                
                # Convert typical_hospital_stay and estimated_recovery_time to JSON strings
                typical_hospital_stay_str = json.dumps(treatment.get('typical_hospital_stay', {}))
                typical_duration_str = json.dumps(treatment.get('estimated_recovery_time', {})) # Correctly map to typical_duration

                current_timestamp = datetime.datetime.now().isoformat()

                # Check if record exists to determine if created_at should be preserved
                cursor.execute("SELECT created_at FROM treatments WHERE id = ?", (treatment['id'],))
                existing_created_at = cursor.fetchone()
                created_at_to_insert = existing_created_at[0] if existing_created_at else current_timestamp

                cursor.execute("""
                    INSERT OR REPLACE INTO treatments (
                        id, name, associated_specialties, description, procedure_complexity_level,
                        typical_hospital_stay, typical_duration, common_benefits, potential_risks,
                        pre_procedure_requirements, post_procedure_follow_ups,
                        estimated_market_cost_usd_min, estimated_market_cost_usd_max, price_notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    treatment['id'],
                    treatment.get('name'),
                    associated_specialties_str,
                    treatment.get('description'),
                    treatment.get('procedure_complexity_level'),
                    typical_hospital_stay_str, # Use the JSON string here
                    typical_duration_str, # Use the JSON string here
                    common_benefits_str,
                    potential_risks_str,
                    pre_procedure_requirements_str,
                    post_procedure_follow_ups_str,
                    estimated_market_cost_usd_min,
                    estimated_market_cost_usd_max,
                    treatment.get('price_notes'),
                    created_at_to_insert,
                    current_timestamp
                ))
                total_imported_treatments += 1
            except KeyError as ke:
                logging.error(f"Missing essential key in treatment data for ID {treatment.get('id', 'N/A')}: {ke}. Skipping record.")
            except Exception as e:
                logging.error(f"Error processing treatment ID {treatment.get('id', 'N/A')}: {e}", exc_info=True)
        logging.info(f"Successfully populated {total_imported_treatments} treatments.")

        # --- Import hospitals data ---
        logging.info("--- Importing Hospitals Data ---")
        hospitals_data = []
        if os.path.exists(HOSPITALS_JSON_FILE):
            try:
                with open(HOSPITALS_JSON_FILE, 'r', encoding='utf-8') as f:
                    hospitals_data = json.load(f)
                logging.info(f"Found {len(hospitals_data)} hospitals in {HOSPITALS_JSON_FILE}.")
            except json.JSONDecodeError as jde:
                logging.error(f"Error decoding JSON from {HOSPITALS_JSON_FILE}: {jde}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading {HOSPITALS_JSON_FILE}: {e}. Skipping.", exc_info=True)
        else:
            logging.warning(f"Hospitals JSON file not found at {HOSPITALS_JSON_FILE}. Skipping hospital data population.")

        for hospital in hospitals_data:
            try:
                geo_location_str = json.dumps(hospital.get('geo_location', {}))
                contact_str = json.dumps(hospital.get('contact', {}))
                
                # medical_professionalism is an object, store as JSON
                medical_professionalism_str = json.dumps(hospital.get('medical_professionalism', {}))
                
                international_patient_services_data = hospital.get('international_patient_services', {})
                international_services_int = int(international_patient_services_data.get('has_international_patient_center', False))
                
                geographical_convenience_str = json.dumps(hospital.get('geographical_convenience', {}))
                brand_reputation_str = json.dumps(hospital.get('brand_reputation', {}))
                cost_and_value_str = json.dumps(hospital.get('cost_and_value', {}))

                # Extract key_specializations directly, store as JSON array
                specialties_str = json.dumps(hospital.get('medical_professionalism', {}).get('key_specializations', []))
                
                # treatments_offered (list of dicts) -> JSON array string
                treatments_offered_str = json.dumps(hospital.get('treatments_offered', []))

                # famous_doctors is now expected to be a list of doctor IDs
                famous_doctors_str = json.dumps(hospital.get('famous_doctors', [])) 
                
                equipment_list_str = json.dumps(hospital.get('equipment_list', []))
                tourism_packages_str = json.dumps(hospital.get('tourism_packages', []))
                
                # New: Accessibility features
                accessibility_features_str = json.dumps(hospital.get('accessibility_features', []))

                current_timestamp = datetime.datetime.now().isoformat()

                cursor.execute("SELECT created_at FROM hospitals WHERE id = ?", (hospital['id'],))
                existing_created_at = cursor.fetchone()
                created_at_to_insert = existing_created_at[0] if existing_created_at else current_timestamp

                cursor.execute("""
                    INSERT OR REPLACE INTO hospitals (
                        id, name, address, city, country, geo_location, contact, description_overview,
                        medical_professionalism, international_services, geographical_convenience,
                        brand_reputation, cost_and_value, specialties,
                        treatments_offered, famous_doctors, equipment_list, tourism_packages,
                        accessibility_features, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hospital['id'],
                    hospital.get('name'),
                    hospital.get('address'),
                    hospital.get('city'),
                    hospital.get('country'),
                    geo_location_str,
                    contact_str,
                    hospital.get('description_overview'),
                    medical_professionalism_str,
                    international_services_int,
                    geographical_convenience_str,
                    brand_reputation_str,
                    cost_and_value_str,
                    specialties_str,
                    treatments_offered_str,
                    famous_doctors_str,
                    equipment_list_str,
                    tourism_packages_str,
                    accessibility_features_str,
                    created_at_to_insert,
                    current_timestamp
                ))
                total_imported_hospitals += 1
            except KeyError as ke:
                logging.error(f"Missing essential key in hospital data for ID {hospital.get('id', 'N/A')}: {ke}. Skipping record.")
            except Exception as e:
                logging.error(f"Error processing hospital ID {hospital.get('id', 'N/A')}: {e}", exc_info=True)
        logging.info(f"Successfully populated {total_imported_hospitals} hospitals.")

        # --- Import doctors data ---
        logging.info("--- Importing Doctors Data ---")
        doctors_data = []
        if os.path.exists(DOCTORS_JSON_FILE):
            try:
                with open(DOCTORS_JSON_FILE, 'r', encoding='utf-8') as f:
                    doctors_data = json.load(f)
                logging.info(f"Found {len(doctors_data)} doctors in {DOCTORS_JSON_FILE}.")
            except json.JSONDecodeError as jde:
                logging.error(f"Error decoding JSON from {DOCTORS_JSON_FILE}: {jde}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading {DOCTORS_JSON_FILE}: {e}. Skipping.", exc_info=True)
        else:
            logging.warning(f"Doctors JSON file not found at {DOCTORS_JSON_FILE}. Skipping doctor data population.")

        for doctor in doctors_data:
            try:
                affiliated_hospital_ids_str = json.dumps(doctor.get('affiliated_hospital_ids', []))
                contact_info_str = json.dumps(doctor.get('contact_info', {}))
                languages_spoken_str = json.dumps(doctor.get('languages_spoken', []))
                certifications_str = json.dumps(doctor.get('certifications', []))
                awards_str = json.dumps(doctor.get('awards', []))

                current_timestamp = datetime.datetime.now().isoformat()
                
                cursor.execute("SELECT created_at FROM doctors WHERE id = ?", (doctor['id'],))
                existing_created_at = cursor.fetchone()
                created_at_to_insert = existing_created_at[0] if existing_created_at else current_timestamp

                cursor.execute("""
                    INSERT OR REPLACE INTO doctors (
                        id, name, specialty, education, experience_years, affiliated_hospital_ids,
                        contact_info, bio, languages_spoken, certifications, awards,
                        average_rating, review_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doctor['id'],
                    doctor.get('name'),
                    doctor.get('specialty'),
                    doctor.get('education'),
                    doctor.get('experience_years'),
                    affiliated_hospital_ids_str,
                    contact_info_str,
                    doctor.get('bio'),
                    languages_spoken_str,
                    certifications_str,
                    awards_str,
                    doctor.get('average_rating'),
                    doctor.get('review_count'),
                    created_at_to_insert,
                    current_timestamp
                ))
                total_imported_doctors += 1
            except KeyError as ke:
                logging.error(f"Missing essential key in doctor data for ID {doctor.get('id', 'N/A')}: {ke}. Skipping record.")
            except Exception as e:
                logging.error(f"Error processing doctor ID {doctor.get('id', 'N/A')}: {e}", exc_info=True)
        logging.info(f"Successfully populated {total_imported_doctors} doctors.")

        # --- Import accommodations data ---
        logging.info("--- Importing Accommodations Data ---")
        accommodations_data = [] # Initialize as an empty list
        if os.path.exists(ACCOMMODATIONS_JSON_FILE):
            try:
                with open(ACCOMMODATIONS_JSON_FILE, 'r', encoding='utf-8') as f:
                    raw_accommodations_data = json.load(f) # Load the entire JSON content
                
                # Iterate through the top-level list and extract accommodations from each block
                if isinstance(raw_accommodations_data, list):
                    for country_city_block in raw_accommodations_data:
                        if isinstance(country_city_block, dict) and 'accommodations' in country_city_block and isinstance(country_city_block['accommodations'], list):
                            accommodations_data.extend(country_city_block['accommodations'])
                        else:
                            logging.warning(f"Skipping malformed block in {ACCOMMODATIONS_JSON_FILE}: {country_city_block.get('country', 'N/A')} - {country_city_block.get('city', 'N/A')}. Missing 'accommodations' list or invalid format.")
                    logging.info(f"Found {len(accommodations_data)} accommodations in {ACCOMMODATIONS_JSON_FILE}.")
                else:
                    logging.error(f"Root of '{ACCOMMODATIONS_JSON_FILE}' is not a list as expected. Skipping accommodation data population.")

            except json.JSONDecodeError as jde:
                logging.error(f"Error decoding JSON from {ACCOMMODATIONS_JSON_FILE}: {jde}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading {ACCOMMODATIONS_JSON_FILE}: {e}. Skipping.", exc_info=True)
        else:
            logging.warning(f"Accommodations JSON file not found at {ACCOMMODATIONS_JSON_FILE}. Skipping accommodation data population.")

        for acc in accommodations_data:
            try:
                # ... (rest of your existing for loop code for processing each accommodation)
                accessibility_features_str = json.dumps(acc.get('accessibility_features', []))
                nearby_landmarks_str = json.dumps(acc.get('nearby_landmarks', []))

                # Infer star_rating from name or notes if not explicit, otherwise set to None
                star_rating = None
                if 'min_cost_per_night_usd' in acc and 'max_cost_per_night_usd' in acc:
                    # Assuming cost range implies certain quality, or use other heuristics
                    # For a more robust solution, ensure star_rating is explicitly in your JSON
                    if acc.get('star_rating') is not None:
                        star_rating = acc['star_rating']
                    elif '5-star' in acc.get('name', '').lower() or 'luxury' in acc.get('name', '').lower():
                        star_rating = 5
                    elif '4-star' in acc.get('name', '').lower() or 'premium' in acc.get('name', '').lower():
                        star_rating = 4
                    elif '3-star' in acc.get('name', '').lower() or 'standard' in acc.get('name', '').lower():
                        star_rating = 3

                # Infer accommodation_type based on name or notes
                accommodation_type = acc.get('accommodation_type', 'not_specified') # Prefer existing key
                if accommodation_type == 'not_specified': # Fallback to heuristic if not specified
                    if 'hotel' in acc.get('name', '').lower():
                        accommodation_type = 'hotel'
                    elif 'apartment' in acc.get('name', '').lower() or 'serviced apartment' in acc.get('name', '').lower():
                        accommodation_type = 'serviced_apartment'
                    elif 'guesthouse' in acc.get('name', '').lower():
                        accommodation_type = 'guesthouse'
                    elif 'residence' in acc.get('name', '').lower() and 'medical' in acc.get('name', '').lower():
                        accommodation_type = 'medical_residence' # Custom type
                
                # Infer boolean flags (0 or 1) - prefer existing key if present
                with_kitchen = acc.get('with_kitchen', 0)
                if with_kitchen == 0 and ('kitchen' in acc.get('notes', '').lower() or 'kitchenette' in acc.get('notes', '').lower()):
                    with_kitchen = 1

                pet_friendly = acc.get('pet_friendly', 0)
                if pet_friendly == 0 and 'pet-friendly' in acc.get('notes', '').lower():
                    pet_friendly = 1

                near_hospital_flag = acc.get('near_hospital_flag', 0)
                if near_hospital_flag == 0 and ('near hospital' in acc.get('notes', '').lower() or acc.get('nearby_landmarks')):
                    near_hospital_flag = 1

                current_timestamp = datetime.datetime.now().isoformat()
                
                cursor.execute("SELECT created_at FROM accommodations WHERE id = ?", (acc['id'],))
                existing_created_at = cursor.fetchone()
                created_at_to_insert = existing_created_at[0] if existing_created_at else current_timestamp

                cursor.execute("""
                    INSERT OR REPLACE INTO accommodations (
                        id, name, location, country, city, cost_per_night_usd, total_cost_estimate_usd,
                        accessibility_features, availability, contact_info, booking_link, notes,
                        nearby_landmarks, image_url, star_rating, accommodation_type, 
                        with_kitchen, pet_friendly, near_hospital_flag, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    acc['id'],
                    acc.get('name'),
                    acc.get('location'),
                    acc.get('country'),
                    acc.get('city'),
                    f"{acc.get('min_cost_per_night_usd', 'N/A')} - {acc.get('max_cost_per_night_usd', 'N/A')}" if acc.get('min_cost_per_night_usd') is not None else acc.get('cost_per_night_usd'), # Adjust based on your actual data structure
                    acc.get('total_cost_estimate_usd'),
                    accessibility_features_str,
                    acc.get('availability'),
                    acc.get('contact_info'),
                    acc.get('booking_link'),
                    acc.get('notes'),
                    nearby_landmarks_str,
                    acc.get('image_url'),
                    star_rating,
                    accommodation_type,
                    with_kitchen,
                    pet_friendly,
                    near_hospital_flag,
                    created_at_to_insert,
                    current_timestamp
                ))
                total_imported_accommodations += 1
            except KeyError as ke:
                logging.error(f"Missing essential key in accommodation data for ID {acc.get('id', 'N/A')}: {ke}. Skipping record.")
            except Exception as e:
                logging.error(f"Error processing accommodation ID {acc.get('id', 'N/A')}: {e}", exc_info=True)
        logging.info(f"Successfully populated {total_imported_accommodations} accommodations.")

        # --- Import visa_rules data ---
        logging.info("--- Importing Visa Rules Data ---")
        visa_rules_data = {}
        if os.path.exists(VISA_RULES_JSON_FILE):
            try:
                with open(VISA_RULES_JSON_FILE, 'r', encoding='utf-8') as f:
                    visa_rules_data = json.load(f)
                logging.info(f"Found {len(visa_rules_data)} visa rules entries in {VISA_RULES_JSON_FILE}.")
            except json.JSONDecodeError as jde:
                logging.error(f"Error decoding JSON from {VISA_RULES_JSON_FILE}: {jde}. Skipping.")
            except Exception as e:
                logging.error(f"Error reading {VISA_RULES_JSON_FILE}: {e}. Skipping.", exc_info=True)
        else:
            logging.warning(f"Visa Rules JSON file not found at {VISA_RULES_JSON_FILE}. Skipping visa rules data population.")

        total_imported_visa_rules = 0
        for key, rule in visa_rules_data.items():
            try:
                # Extract nationality, destination_country, purpose from the key
                parts = key.split('_')
                if len(parts) >= 3:
                    nationality = parts[0]
                    destination_country = parts[1]
                    purpose = parts[2]
                else:
                    logging.warning(f"Skipping malformed visa rule key: {key}")
                    continue

                required_documents_str = json.dumps(rule.get('required_documents', []))

                current_timestamp = datetime.datetime.now().isoformat()
                
                cursor.execute("SELECT created_at FROM visa_rules WHERE id = ?", (key,))
                existing_created_at = cursor.fetchone()
                created_at_to_insert = existing_created_at[0] if existing_created_at else current_timestamp

                cursor.execute("""
                    INSERT OR REPLACE INTO visa_rules (
                        id, nationality, destination_country, purpose, visa_required, visa_type,
                        stay_duration_notes, required_documents, processing_time_days, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    nationality,
                    destination_country,
                    purpose,
                    rule.get('visa_required'),
                    rule.get('visa_type'),
                    rule.get('stay_duration_notes'),
                    required_documents_str,
                    rule.get('processing_time_days'),
                    rule.get('notes'),
                    created_at_to_insert,
                    current_timestamp
                ))
                total_imported_visa_rules += 1
            except KeyError as ke:
                logging.error(f"Missing essential key in visa rule data for ID {key}: {ke}. Skipping record.")
            except Exception as e:
                logging.error(f"Error processing visa rule ID {key}: {e}", exc_info=True)
        logging.info(f"Successfully populated {total_imported_visa_rules} visa rules.")

        conn.commit()
        logging.info("All data import processes completed successfully.")

    except sqlite3.Error as e:
        logging.error(f"SQLite error during data import transaction: {e}", exc_info=True)
        conn.rollback() # Rollback in case of a database error during import
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during data import: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logging.info("Starting database setup and data import script.")
    setup_database()
    import_data()
    logging.info("Script execution finished.")