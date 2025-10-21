# ai_service\src\agentic\tools\check_visa_requirements_tool.py
import sys
import json
import asyncio
import nest_asyncio
import os
from typing import Dict, Any, Optional, Type
from ..logger import logging
from ..exception import CustomException
from ..models import VisaRequirementsInput, VisaRequirementsOutput, VisaInfo
from langchain_core.tools import BaseTool
from pydantic import ValidationError

class VisaRequirementsCheckerTool(BaseTool):
    """
    A tool to check visa requirements specifically for medical travel.
    It loads visa rules from a JSON file and processes structured queries.
    """
    name: str = "check_visa_requirements"
    description: str = (
        """Useful for checking visa requirements for a specific nationality, destination country, and purpose (medical or tourism).
        Input MUST be a JSON object conforming to VisaRequirementsInput schema with the following REQUIRED keys: 'nationality', 'destination_country', 'purpose'.
        Example: {"nationality": "us", "destination_country": "malaysia", "purpose": "medical"}
        The tool returns a JSON object conforming to VisaRequirementsOutput schema with visa information."""
    )
    args_schema: Type[VisaRequirementsInput] = VisaRequirementsInput

    visa_rules_file: str = ""
    visa_rules: Dict[str, Any] = {}

    def __init__(self, visa_rules_file_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if visa_rules_file_path:
            self.visa_rules_file = visa_rules_file_path
        else:
            _current_script_dir = os.path.dirname(os.path.abspath(__file__))
            self.visa_rules_file = os.path.join(_current_script_dir, '..', '..', 'data', 'visa_rules.json')

        self.visa_rules = self._load_visa_rules()
        logging.info(f"VisaRequirementsCheckerTool initialized with rules from: {self.visa_rules_file}")

    def _load_visa_rules(self) -> Dict[str, Any]:
        """
        Loads visa rules from the specified JSON file.
        """
        if not os.path.exists(self.visa_rules_file):
            logging.error(f"Visa rules file not found at: {self.visa_rules_file}. Please ensure it exists.")
            raise FileNotFoundError(f"Visa rules file not found at: {self.visa_rules_file}")
        
        try:
            with open(self.visa_rules_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            logging.info("Visa rules loaded successfully.")
            return rules
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from visa rules file {self.visa_rules_file}: {e}")
            raise ValueError(f"Invalid JSON format in visa rules file: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading visa rules: {e}")
            raise CustomException(sys, e)

    async def _arun(self, tool_input: VisaRequirementsInput) -> VisaRequirementsOutput:
        """
        Asynchronously checks visa requirements based on a structured input object.
        """
        # Access fields directly from the tool_input object
        nationality = tool_input.nationality
        destination_country = tool_input.destination_country
        purpose = tool_input.purpose
        
        logging.info(f"Executing visa requirement check for nationality: '{nationality}', destination: '{destination_country}', purpose: '{purpose}'.")

        try:
            normalized_nationality = nationality.lower().replace(' citizen', '')
            normalized_destination = destination_country.lower()
            normalized_purpose = purpose.lower()

            lookup_key = f"{normalized_nationality}_{normalized_destination}_{normalized_purpose}"
            
            visa_info_dict = self.visa_rules.get(lookup_key)
            if not visa_info_dict:
                visa_info_dict = self.visa_rules.get("default", {
                    "visa_required": True,
                    "visa_type": "Unknown",
                    "stay_duration_notes": "N/A",
                    "processing_time_days": "N/A",
                    "required_documents": [],
                    "notes": "No rule matched and no default rule available"
                })
            
            visa_info = VisaInfo(**visa_info_dict)

            final_result = VisaRequirementsOutput(
                nationality=nationality,
                destination_country=destination_country,
                purpose=purpose,
                visa_info=visa_info,
                error=None
            )

            logging.info(f"Visa check completed. Result: {final_result.model_dump_json(indent=2)}")
            return final_result

        except ValidationError as ve:
            logging.error(f"VisaRequirementsCheckerTool: Pydantic validation failed for visa info: {ve}. Raw data: {visa_info_dict}", exc_info=True)
            return VisaRequirementsOutput(
                nationality=nationality,
                destination_country=destination_country,
                purpose=purpose,
                visa_info=VisaInfo(
                    visa_required=True,
                    visa_type="Unknown",
                    stay_duration_notes="N/A",
                    processing_time_days="N/A",
                    required_documents=[],
                    notes=f"Error validating visa info from rules: {ve}"
                ),
                error=f"Invalid visa rule data format: {ve}"
            )
        except Exception as e:
            logging.error(f"An error occurred during check_visa_requirements execution: {e}", exc_info=True)
            return VisaRequirementsOutput(
                nationality=nationality,
                destination_country=destination_country,
                purpose=purpose,
                visa_info=VisaInfo(
                    visa_required=True,
                    visa_type="Unknown",
                    stay_duration_notes="N/A",
                    processing_time_days="N/A",
                    required_documents=[],
                    notes=f"An internal error occurred: {e}"
                ),
                error=f"An internal error occurred: {str(e)}"
            )

    def _run(self, tool_input: Any) -> VisaRequirementsOutput:
            """
            Synchronous wrapper for asynchronous execution.
            Accepts dict, JSON string, or VisaRequirementsInput object.
            Ensures robust error handling and consistent return type.
            """
            try:
                # Normalize input
                if isinstance(tool_input, str):
                    try:
                        tool_input = json.loads(tool_input)
                    except json.JSONDecodeError as e:
                        logging.error(f"Invalid JSON input to _run: {e}")
                        return VisaRequirementsOutput(
                            nationality="unknown",
                            destination_country="unknown",
                            purpose="unknown",
                            visa_info=VisaInfo(visa_required=True, notes="Invalid JSON input"),
                            error=f"Invalid JSON input: {e}"
                        )

                if isinstance(tool_input, dict):
                    try:
                        tool_input = VisaRequirementsInput(**tool_input)
                    except ValidationError as ve:
                        logging.error(f"Schema validation failed in _run: {ve}")
                        return VisaRequirementsOutput(
                            nationality=tool_input.get("nationality", "unknown"),
                            destination_country=tool_input.get("destination_country", "unknown"),
                            purpose=tool_input.get("purpose", "unknown"),
                            visa_info=VisaInfo(visa_required=True, notes="Schema validation failed"),
                            error=f"Schema validation failed: {ve}"
                        )

                if not isinstance(tool_input, VisaRequirementsInput):
                    logging.error(f"Unexpected tool_input type: {type(tool_input)}")
                    return VisaRequirementsOutput(
                        nationality="unknown",
                        destination_country="unknown",
                        purpose="unknown",
                        visa_info=VisaInfo(visa_required=True, notes="Unexpected tool_input type"),
                        error=f"Unexpected tool_input type: {type(tool_input)}"
                    )

                # Ensure event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    nest_asyncio.apply()

                coroutine = self._arun(tool_input)
                return loop.run_until_complete(coroutine)

            except Exception as e:
                logging.error(f"VisaRequirementsCheckerTool._run encountered an error: {e}", exc_info=True)
                return VisaRequirementsOutput(
                    nationality="unknown",
                    destination_country="unknown",
                    purpose="unknown",
                    visa_info=VisaInfo(
                        visa_required=True,
                        visa_type="Unknown",
                        stay_duration_notes="N/A",
                        processing_time_days="N/A",
                        required_documents=[],
                        notes=f"Unexpected error: {e}"
                    ),
                    error=f"Unexpected error: {e}"
                )
