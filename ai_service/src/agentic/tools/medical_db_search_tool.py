# ai_service/src/agentic/tools/medical_db_search_tool.py
import sys
import sqlite3
import json
import asyncio
import nest_asyncio
import os
from typing import List, Type
from ..logger import logging
from ..exception import CustomException
from ..models import (MedicalDBSearchInput, MedicalDBSearchOutput,HospitalDetails, TreatmentDetails, DoctorDetails)
from langchain_core.tools import BaseTool
from pydantic import ValidationError

class MedicalDBSearchTool(BaseTool):
    """
    A tool to search the local SQLite database for medical treatments,
    hospital information, and related details.
    """
    name: str = "medical_db_search"
    description: str = (
        """Useful for searching the local medical database for hospital information, treatment details, and doctor information.
        Input MUST be a JSON object conforming to MedicalDBSearchInput schema with 'type' and specific query conditions.
        'type' can be 'hospital', 'treatment', or 'doctor'.

        For 'hospital' type, keys can include: 'name', 'specialty', 'location', 'international_services' (boolean), 'accessibility_features', 'min_rating', 'treatment_id'.
        Example: {"type": "hospital", "specialty": "Dentistry", "location": "Kuala Lumpur", "international_services": true, "min_rating": 4.5}

        For 'treatment' type, keys can include: 'name', 'specialty', 'min_cost', 'max_cost', 'cost_unit'.
        Example: {"type": "treatment", "name": "Rhinoplasty", "specialty": "Plastic Surgery", "min_cost": 4000, "max_cost": 8000, "cost_unit": "USD"}

        For 'doctor' type, keys can include: 'name', 'specialty', 'location', 'affiliated_hospital_id', 'min_experience_years', 'min_rating'.
        Example: {"type": "doctor", "specialty": "Orthopedic Surgery", "min_rating": 4.8}
        """
    )

    args_schema: Type[MedicalDBSearchInput] = MedicalDBSearchInput

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
    
    async def _fetch_hospital_data(self, **kwargs) -> List[HospitalDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM hospitals WHERE 1=1"
            params = []

            if kwargs.get('name'):
                query += " AND name LIKE ?"
                params.append(f"%{kwargs['name']}%")
            if kwargs.get('specialty'):
                query += " AND medical_professionalism LIKE ?"
                params.append(f'%"{kwargs["specialty"]}"%')
            if kwargs.get('treatment_name'):
                query += " AND treatments_offered LIKE ?"
                params.append(f'%"{kwargs["treatment_name"]}"%')
            if kwargs.get('treatment_id'):
                query += " AND treatments_offered LIKE ?"
                params.append(f'%"{kwargs["treatment_id"]}"%')
            if kwargs.get('location'):
                query += " AND (city LIKE ? OR country LIKE ?)"
                params.extend([f"%{kwargs['location']}%", f"%{kwargs['location']}%"])
            if kwargs.get('international_services') is not None:
                query += " AND international_patient_services LIKE ?"
                params.append(f'%\"has_international_patient_center\": {str(kwargs["international_services"]).lower()}%')
            if kwargs.get('accessibility_features'):
                query += " AND accessibility_features LIKE ?"
                params.append(f"%{kwargs['accessibility_features']}%")
            if kwargs.get('min_rating'):
                query += " AND average_rating >= ?"
                params.append(kwargs['min_rating'])
            if kwargs.get('doctor_id'):
                query += " AND famous_doctors LIKE ?"
                params.append(f'%"{kwargs["doctor_id"]}"%')

            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            columns = [desc[0] for desc in cursor.description]

            # Unified normalization config
            normalize_config = {
                'geo_location': 'dict',
                'contact': 'dict',
                'medical_professionalism': {
                    'certifications': 'list',
                    'key_specializations': 'list',
                    'advanced_technology_overview': 'list'
                },
                'international_patient_services': {
                    'languages_supported': 'list',
                    'cultural_accommodations': 'list'
                },
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

    async def _fetch_treatment_data(self, **kwargs) -> List[TreatmentDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM treatments WHERE 1=1"
            params = []

            if kwargs.get('name'):
                query += " AND name LIKE ?"
                params.append(f"%{kwargs['name']}%")
            if kwargs.get('specialty'):
                query += " AND associated_specialties LIKE ?"
                params.append(f'%"{kwargs["specialty"]}"%')
            if kwargs.get('min_cost'):
                query += " AND estimated_market_cost_range_usd_min >= ?"
                params.append(kwargs['min_cost'])
            if kwargs.get('max_cost'):
                query += " AND estimated_market_cost_range_usd_max <= ?"
                params.append(kwargs['max_cost'])
            if kwargs.get("cost_unit"):
                query += " AND LOWER(cost_unit) = ?"
                params.append(kwargs["cost_unit"].lower())

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

    async def _fetch_doctor_data(self, **kwargs) -> List[DoctorDetails]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM doctors WHERE 1=1"
            params = []

            if kwargs.get('name'):
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


    async def _arun(self, tool_input: MedicalDBSearchInput) -> MedicalDBSearchOutput:
        message = ""
        error = None
        hospital_results = []
        treatment_results = []
        doctor_results = []

        try:
            if tool_input.type == "hospital":
                hospital_results = await self._fetch_hospital_data(
                    name=tool_input.name,
                    specialty=tool_input.specialty,
                    location=tool_input.location,
                    international_services=tool_input.international_services,
                    accessibility_features=tool_input.accessibility_features,
                    min_rating=tool_input.min_rating,
                    treatment_id=tool_input.treatment_id
                )
                message = f"Found {len(hospital_results)} hospitals."
            elif tool_input.type == "treatment":
                treatment_results = await self._fetch_treatment_data(
                    name=tool_input.name,
                    specialty=tool_input.specialty,
                    min_cost=tool_input.min_cost,
                    max_cost=tool_input.max_cost,
                    cost_unit=tool_input.cost_unit
                )
                message = f"Found {len(treatment_results)} treatments."
            elif tool_input.type == "doctor":
                doctor_results = await self._fetch_doctor_data(
                    name=tool_input.name,
                    specialty=tool_input.specialty,
                    location=tool_input.location,
                    affiliated_hospital_id=tool_input.affiliated_hospital_id,
                    min_experience_years=tool_input.min_experience_years,
                    min_rating=tool_input.min_rating
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

    def _run(self, tool_input: MedicalDBSearchInput) -> MedicalDBSearchOutput:
        """
        Synchronous wrapper for async execution with robust event loop handling.
        """
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                nest_asyncio.apply()
                return loop.run_until_complete(self._arun(tool_input))
            else:
                return loop.run_until_complete(self._arun(tool_input))
        except ValidationError as e:
            raise e
        except Exception as e:
            logging.error("Error during synchronous run of MedicalDBSearchTool", exc_info=True)
            raise CustomException(sys, e)