# ai_service/src/agentic/tools/medical_db_search_tool.py
import sys
import sqlite3
import json
import os
from typing import List, Type, Optional, Any
from ..logger import logging
from ..exception import CustomException
from ..models import (MedicalDBSearchInput, MedicalDBSearchOutput,HospitalDetails, TreatmentDetails, DoctorDetails)
from langchain_core.tools import BaseTool
from pydantic import ValidationError
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

class MedicalDBSearchTool(BaseTool):
    """
    An "adaptive RAG" tool for searching a local medical database.
    It decides whether to use
    (1) vector search (ChromaDB)
    (2) SQL search (SQLite)
    (3) hybrid search (Vector + SQL)
    based on whether the query is "semantic" or "structured".
    """
    name: str = "medical_db_search"
    description: str = (
        """Useful for searching the local medical database for hospital information, treatment details, and doctor information.
        Input MUST be a JSON object conforming to MedicalDBSearchInput schema with 'type' and specific query conditions.
        'type' can be 'hospital', 'treatment', or 'doctor'.

        For 'hospital' type, keys can include: 'name' (semantic), 'specialty' (semantic/SQL), 'location' (SQL), 'international_services' (boolean, SQL), 'accessibility_features' (SQL), 'min_rating' (SQL), 'treatment_id' (SQL).
        Example 1 (Semantic): {"type": "hospital", "name": "best hospital for heart surgery in Kuala Lumpur"}
        Example 2 (Structured): {"type": "hospital", "location": "Kuala Lumpur", "min_rating": 4.5}
        Example 3 (Hybrid): {"type": "hospital", "name": "quiet hospital for recovery", "location": "Malaysia", "min_rating": 4.0}
        """
    )

    args_schema: Type[MedicalDBSearchInput] = MedicalDBSearchInput

    _vector_store: Chroma = None
    _embedding_model: GoogleGenerativeAIEmbeddings = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'db')
            CHROMA_DB_PATH = os.path.join(DB_DIR, 'chroma_vector_store')

            self._embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            
            if not os.path.exists(CHROMA_DB_PATH):
                logging.error(f"ChromaDB path not found: {CHROMA_DB_PATH}. Did you run rag_setup.py?")
                raise FileNotFoundError(f"ChromaDB not found at {CHROMA_DB_PATH}")

            self._vector_store = Chroma(
                persist_directory=CHROMA_DB_PATH,
                embedding_function=self._embedding_model
            )
            logging.info(f"MedicalDBSearchTool: ChromaDB vector store loaded from {CHROMA_DB_PATH}")
        except Exception as e:
            logging.error(f"Failed to initialize ChromaDB in MedicalDBSearchTool: {e}", exc_info=True)
            raise CustomException(sys, e)

    def _get_db_connection(self):
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'medical_rag.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    @staticmethod
    def safe_json_load(value, default=None):
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default if default is not None else value
        return value
    
    @staticmethod
    def ensure_list(obj):
        return obj if isinstance(obj, list) else []

    @staticmethod
    def ensure_dict(obj):
        return obj if isinstance(obj, dict) else {}
    
    def _normalize_fields(self, data: dict, config: dict):
        """
        Normalize JSON/dict/list fields according to config.
        Supports nested fields via nested dict.
        """
        for field, field_type in config.items():
            if isinstance(field_type, dict):
                # nested dict: recursive normalization
                if field not in data or not isinstance(data[field], dict):
                    data[field] = {}
                data[field] = self._normalize_fields(data[field], field_type)
            elif field_type == 'dict':
                data[field] = self.safe_json_load(data.get(field), {})
            elif field_type == 'list':
                val = self.safe_json_load(data.get(field), [])
                data[field] = self.ensure_list(val)
        return data
    
    async def _fetch_hospital_data(self, id_list: Optional[List[str]] = None, **kwargs) -> List[HospitalDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM hospitals WHERE 1=1"
            params = []

            # ID filtering for hybrid search
            if id_list:
                if not id_list: return [] # If the ID list is empty, return immediately
                query += f" AND id IN ({','.join('?' for _ in id_list)})"
                params.extend(id_list)

            if kwargs.get('name') and not id_list: 
                query += " AND name LIKE ?"
                params.append(f"%{kwargs['name']}%")
            if kwargs.get('specialty'):
                query += " AND (medical_professionalism LIKE ? OR specialties LIKE ?)"
                params.extend([f'%"{kwargs["specialty"]}"%', f'%"{kwargs["specialty"]}"%'])
            if kwargs.get('treatment_id'):
                query += " AND treatments_offered LIKE ?"
                params.append(f'%"{kwargs["treatment_id"]}"%')
            if kwargs.get('location'):
                query += " AND (city LIKE ? OR country LIKE ?)"
                params.extend([f"%{kwargs['location']}%", f"%{kwargs['location']}%"])
            if kwargs.get('international_services') is not None:
                query += " AND international_services = ?" 
                params.append(int(kwargs["international_services"]))
            if kwargs.get('accessibility_features'):
                query += " AND accessibility_features LIKE ?"
                params.append(f"%{kwargs['accessibility_features']}%")
            if kwargs.get('min_rating'):
                query += " AND CAST(json_extract(brand_reputation, '$.average_rating') AS REAL) >= ?"
                params.append(kwargs['min_rating'])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            columns = [desc[0] for desc in cursor.description]
            normalize_config = {
                'geo_location': 'dict', 
                'contact': 'dict',
                'medical_professionalism': {'certifications': 'list', 'key_specializations': 'list', 'advanced_technology_overview': 'list'},
                'international_patient_services': {'languages_supported': 'list', 'cultural_accommodations': 'list'},
                'brand_reputation': 'dict', 
                'treatments_offered': 'list', 
                'geographical_convenience': 'dict',
                'cost_and_value': 'dict', 
                'famous_doctors': 'list', 
                'equipment_list': 'list',
                'tourism_packages': 'list', 
                'accessibility_features': 'list'
            }
            for row in rows:
                data = dict(zip(columns, row))
                data = self._normalize_fields(data, normalize_config)
                results.append(HospitalDetails(**data))
            logging.debug(f"[fetch_hospital_data] Matched results: {len(results)}")
            return results
        except Exception as e:
            logging.error(f"Error fetching hospital data: {e}", exc_info=True)
            raise CustomException(sys, e)

    async def _fetch_treatment_data(self, id_list: Optional[List[str]] = None, **kwargs) -> List[TreatmentDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM treatments WHERE 1=1"
            params = []

            # ID filtering for hybrid search
            if id_list:
                if not id_list: return []
                query += f" AND id IN ({','.join('?' for _ in id_list)})"
                params.extend(id_list)

            if kwargs.get('name') and not id_list:
                query += " AND name LIKE ?"
                params.append(f"%{kwargs['name']}%")
            if kwargs.get('specialty'):
                query += " AND associated_specialties LIKE ?"
                params.append(f'%"{kwargs["specialty"]}"%')
            if kwargs.get('min_cost'):
                query += " AND estimated_market_cost_usd_min >= ?"
                params.append(kwargs['min_cost'])
            if kwargs.get('max_cost'):
                query += " AND estimated_market_cost_usd_max <= ?"
                params.append(kwargs['max_cost'])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            columns = [desc[0] for desc in cursor.description]
            normalize_config = {
                'associated_specialties': 'list',
                'typical_hospital_stay': 'dict',
                'estimated_recovery_time': 'dict', 
                'common_benefits': 'list', 
                'potential_risks': 'list',
                'pre_procedure_requirements': 'list', 
                'post_procedure_follow_ups': 'list'
            }
            for row in rows:
                data = dict(zip(columns, row))
                data = self._normalize_fields(data, normalize_config)
                results.append(TreatmentDetails(**data))
            logging.debug(f"[fetch_treatment_data] Matched results: {len(results)}")
            return results
        except Exception as e:
            logging.error(f"Error fetching treatment data: {e}", exc_info=True)
            raise CustomException(sys, e)

    async def _fetch_doctor_data(self, id_list: Optional[List[str]] = None, **kwargs) -> List[DoctorDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM doctors WHERE 1=1"
            params = []

            # ID filtering for hybrid search
            if id_list:
                if not id_list: return []
                query += f" AND id IN ({','.join('?' for _ in id_list)})"
                params.extend(id_list)

            if kwargs.get('name') and not id_list:
                query += " AND name LIKE ?"
                params.append(f"%{kwargs['name']}%")
            if kwargs.get('specialty'):
                query += " AND specialty LIKE ?"
                params.append(f"%{kwargs['specialty']}%")
            if kwargs.get('affiliated_hospital_id'):
                query += " AND affiliated_hospital_ids LIKE ?"
                params.append(f'%"{kwargs["affiliated_hospital_id"]}"%')
            if kwargs.get('min_experience_years'):
                query += " AND experience_years >= ?"
                params.append(kwargs['min_experience_years'])
            if kwargs.get('min_rating'):
                query += " AND average_rating >= ?"
                params.append(kwargs['min_rating'])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            columns = [desc[0] for desc in cursor.description]
            normalize_config = {
                'contact_info': 'dict', 
                'affiliated_hospital_ids': 'list',
                'languages_spoken': 'list', 
                'certifications': 'list', 
                'awards': 'list'
            }
            for row in rows:
                data = dict(zip(columns, row))
                data = self._normalize_fields(data, normalize_config)
                results.append(DoctorDetails(**data))
            logging.debug(f"[fetch_doctor_data] Matched results: {len(results)}")
            return results
        except Exception as e:
            logging.error(f"Error fetching doctor data: {e}", exc_info=True)
            raise CustomException(sys, e)

    # --- Vector search function ---
    async def _fetch_vector_search_ids(self, query: str, search_type: str, k_results: int = 10) -> List[str]:
        """
        Perform a semantic search and return a list of source_ids for matching documents.
        """
        if not query:
            return []
            
        logging.info(f"Executing vector search for type '{search_type}' with query: '{query}'")
        try:
            # Using both query and metadata filtering allows ChromaDB to perform powerful searches
            retriever = self._vector_store.as_retriever(
                search_kwargs={"k": k_results, "filter": {"type": search_type}}
            )
            docs = await retriever.ainvoke(query)
            
            ids = [doc.metadata["source_id"] for doc in docs if "source_id" in doc.metadata]
            logging.info(f"Vector search found {len(ids)} matching IDs.")
            return ids
        except Exception as e:
            logging.error(f"Error during vector search: {e}", exc_info=True)
            return []


    async def _arun(self, **kwargs: Any) -> MedicalDBSearchOutput:
        message = ""
        error = None
        hospital_results = []
        treatment_results = []
        doctor_results = []

        try:
            tool_input = self.args_schema(**kwargs)
        except ValidationError as e:
            logging.error(f"Input validation failed for MedicalDBSearchTool: {e}", exc_info=True)
            return MedicalDBSearchOutput(message="Input validation failed.", error=str(e))

        try:
            # Convert Pydantic input into a dictionary
            query_kwargs = tool_input.model_dump(exclude_unset=True)
            search_type = query_kwargs.pop('type', None)
            
            # --- Adaptive RAG Routing Logic ---
            # 1. Determine the search strategy, defining a "semantic" query as one that uses the 'name' field.
            semantic_query = query_kwargs.get('name')
            # A "structured" query refers to any field other than 'name'
            structured_filters = {k: v for k, v in query_kwargs.items() if k != 'name'}

            vector_search_ids: Optional[List[str]] = None

            if semantic_query:
                # Strategy 2 (semantic) or 3 (hybrid): If there is a semantic query, perform vector search first.
                search_query_text = semantic_query
                # Add some structured filters to the text to get better results.
                if query_kwargs.get('specialty'):
                    search_query_text += f" (specialty: {query_kwargs['specialty']})"
                if query_kwargs.get('location'):
                    search_query_text += f" (location: {query_kwargs['location']})"
                
                vector_search_ids = await self._fetch_vector_search_ids(search_query_text, search_type)
            
            # 2. Executing the query – `vector_search_ids` (from vector search) and `structured_filters` (from SQL) will be passed to the `fetch` function.
            
            if search_type == "hospital":
                hospital_results = await self._fetch_hospital_data(
                    id_list=vector_search_ids, 
                    **structured_filters
                )
                message = f"Found {len(hospital_results)} hospitals."
            elif search_type == "treatment":
                treatment_results = await self._fetch_treatment_data(
                    id_list=vector_search_ids, 
                    **structured_filters
                )
                message = f"Found {len(treatment_results)} treatments."
            elif search_type == "doctor":
                doctor_results = await self._fetch_doctor_data(
                    id_list=vector_search_ids, 
                    **structured_filters
                )
                message = f"Found {len(doctor_results)} doctors."
            else:
                message = "Invalid search type."
                error = "Type must be 'hospital', 'treatment', or 'doctor'."

        except ValidationError as e:
            error = f"Input validation error: {e}"
            message = "Invalid input for search operation."
            logging.error(f"Input validation error in _arun: {e}", exc_info=True)
        except CustomException as e:
            error = str(e)
            message = "An error occurred during database query."
            logging.error(f"CustomException caught in _arun: {error}", exc_info=True)
        except Exception as e:
            error = f"An unexpected error occurred: {e}"
            message = "An unexpected error occurred during search operation."
            logging.error(f"Unexpected error in _arun: {e}", exc_info=True)

        return MedicalDBSearchOutput(
            hospital_results=hospital_results,
            treatment_results=treatment_results,
            doctor_results=doctor_results,
            message=message,
            error=error
        )
    
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous run method (not recommended for this async-first tool)."""
        raise NotImplementedError("This tool is async-first. Please use .ainvoke() or await ._arun()")