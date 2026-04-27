# ai_service/src/agentic/tools/calculate_budget_tool.py
import json
import logging
import re
from typing import Any
from langchain_core.tools import tool
from ..models import CalculateBudgetInput
from datetime import datetime
from ..config import AppConfig

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def _parse_cost(value: Any) -> float:
    """Robust cost parser."""
    if value is None: return 0.0
    if isinstance(value, (int, float)): return float(value)
        
    s = str(value).strip().lower().replace(',', '')
    if not s or s in ["n/a", "contact for price", "null", "pending"]: return 0.0

    matches = re.findall(r'\d+(?:\.\d+)?', s)
    if matches:
        nums = [float(m) for m in matches]
        return sum(nums) / len(nums)
    return 0.0

def _safe_dump(obj: Any) -> Any:
    """Helper: Converts Pydantic models to dicts safely to avoid 'has no attribute' errors."""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj

def _extract_val(obj: Any, key: str) -> float:
    """Helper to extract and parse cost from an object."""
    safe_obj = _safe_dump(obj)
    val = safe_obj.get(key) if isinstance(safe_obj, dict) else getattr(safe_obj, key, None)
    return _parse_cost(val)

def _calc_accom_cost(accom: Any, days: int) -> float:
    """Calculate the total cost for accommodation based on the number of days."""
    safe_accom = _safe_dump(accom)
    if not safe_accom: return 0.0
    r1 = _extract_val(safe_accom, "min_cost_per_night_usd")
    r2 = _extract_val(safe_accom, "max_cost_per_night_usd")
    avg_rate = (r1 + r2) / 2 if (r1 > 0 and r2 > 0) else (r1 or r2)
    return avg_rate * days

def _calc_logistics_cost(logistics: Any, local_daily: float, days: int) -> float:
    """Calculate total logistics cost, including local transport."""
    safe_logistics = _safe_dump(logistics)
    if not safe_logistics: return 0.0
    
    pickup = safe_logistics.get("airport_pick_up_details") if isinstance(safe_logistics, dict) else getattr(safe_logistics, "airport_pick_up_details", None)
    safe_pickup = _safe_dump(pickup)
    
    transfer_rate = _extract_val(safe_pickup, "estimated_cost_per_transfer_usd")
    return (transfer_rate * 2) + (local_daily * days)

def _build_notes(med_cost: float, flight_cost: float, log_cost: float, days: int) -> str:
    """Build human-readable notes based on the cost breakdown."""
    notes = [f"Includes {days} days stay."]
    if med_cost == 0: notes.append("Medical cost pending quote.")
    if flight_cost == 0: notes.append("Flight cost pending booking.")
    if log_cost > 0: notes.append("Includes daily local transport estimate.")
    return " ".join(notes)

def _get_trip_days(session_state: dict, default_days: int) -> int:
    """Extracts and calculates the number of days for the trip based on user profile dates."""
    user_profile = _safe_dump(session_state.get("user_profile", {}))
        
    current_trip = user_profile.get("current_trip") or {}
    departure_str = current_trip.get("departure_date")
    return_str = current_trip.get("return_date")

    if departure_str and return_str:
        try:
            dep_date = datetime.strptime(departure_str, "%Y-%m-%d")
            ret_date = datetime.strptime(return_str, "%Y-%m-%d")
            calc_days = (ret_date - dep_date).days
            if calc_days > 0:
                logger.info(f"📅 Trip duration calculated: {calc_days} days")
                return calc_days
        except ValueError:
            logger.warning(f"⚠️ Date parsing failed for {departure_str} - {return_str}. Fallback to {default_days} days.")
    
    return default_days

def _get_insurance_cost(logistics: Any) -> float:
    """Extract hidden insurance premium from logistics plan."""
    safe_logistics = _safe_dump(logistics)
    if not safe_logistics: return 0.0
    
    services = safe_logistics.get("additional_local_services_suggestions") if isinstance(safe_logistics, dict) else getattr(safe_logistics, "additional_local_services_suggestions", None)
    if not services:
        return 0.0

    services_str = str(services).lower()
    
    ins_match = re.search(r'premium.*?\$(\d+(?:\.\d+)?)', services_str)
    if not ins_match:
        ins_match = re.search(r'insurance.*?\$(\d+(?:\.\d+)?)', services_str)
        
    if ins_match:
        return float(ins_match.group(1))
    return 0.0

def create_calculate_budget_tool(config: AppConfig):
    """[Factory] Creates the Calculate Budget Tool."""
    @tool("calculate_budget_tool", args_schema=CalculateBudgetInput)
    async def calculate_budget(session_state: dict) -> str:
        """Use this tool to calculate the total estimated budget."""
        try:
            logger.info("🧮 Calculating Budget...")
            
            med = session_state.get("final_selected_medical_plan")
            flight = session_state.get("final_selected_flight")
            accom = session_state.get("final_selected_accommodation")
            logistics = session_state.get("logistics_plan")
            
            days = _get_trip_days(session_state, config.domain.default_recovery_days)

            med_cost = _extract_val(med, "estimated_cost_usd")
            flt_cost = _extract_val(flight, "total_cost")
            acc_cost = _calc_accom_cost(accom, days)
            log_cost = _calc_logistics_cost(logistics, config.domain.local_transport_daily_cost_usd, days)

            insurance_cost = _get_insurance_cost(logistics)

            total = med_cost + flt_cost + acc_cost + log_cost + insurance_cost

            result = {
                "currency": "USD",
                "total_estimated_budget_usd": round(total, 2),
                "breakdown": {
                    "medical_cost": med_cost,
                    "flight_cost": flt_cost,
                    "accommodation_cost": acc_cost,
                    "logistics_cost": log_cost,
                    "insurance_cost": insurance_cost
                },
                "notes": _build_notes(med_cost, flt_cost, log_cost, days),
                "_metadata": {
                    "source": "Deterministic Calculation Engine",
                    "timestamp": datetime.now().isoformat()
                }
            }
            logger.info(f"💰 Calculation Complete: ${total}")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Budget Tool Error: {e}", exc_info=True)
            return json.dumps({"error": str(e), "total_estimated_budget_usd": 0})
            
    return calculate_budget