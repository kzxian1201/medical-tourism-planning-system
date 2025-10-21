# ai_service/src/agentic/agents/planning_agent_terminal.py
# ===================== Entrypoint =====================
from ai_service.src.agentic.utils.main_utils import setup_proto_warnings
setup_proto_warnings()

import os
import sys
import re
import logging
from typing import Optional, Any, List, Dict
import json
import asyncio
from datetime import datetime

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ai_service.src.agentic.utils.main_utils import LoadModel
from ai_service.src.agentic.tools.medical_planning_tool import MedicalPlanningTool
from ai_service.src.agentic.tools.travel_arrangement_tool import TravelArrangementTool
from ai_service.src.agentic.tools.travel_logistics_tool import TravelLogisticsTool
from ai_service.src.agentic.tools.update_session_state_tool import UpdateSessionStateTool
from ai_service.src.agentic.tools.calculate_budget_tool import CalculateBudgetTool

# ===================== Logging =====================
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ===================== Prompt Loader =====================
def load_prompt(prompt_path: Optional[str] = None) -> str:
    if prompt_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.normpath(os.path.join(base_dir, "../prompt/planning_agent_prompt.txt"))
    logger.info(f"Loading prompt template from: {prompt_path}")

    if not os.path.isfile(prompt_path):
        raise RuntimeError(f"Prompt file not found at {prompt_path}. Please ensure it exists.")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
    
# ===================== Date Utilities =====================
def parse_date(date_str: str) -> Optional[str]:
    """Normalize various date formats into ISO YYYY-MM-DD. Returns None if invalid."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
    return None

# ===================== Vague Input Handler =====================
VAGUE_ANSWERS = {"idk", "i don't know", "no idea", "not sure"}

def handle_vague_input(user_input: str, session_state: dict) -> Optional[dict]:
    if user_input.lower().strip() in VAGUE_ANSWERS:
        session_state["vague_count"] = session_state.get("vague_count", 0) + 1
        count = session_state["vague_count"]

        if count == 1:
            return {"message_type": "text", "content": {"prompt": "Could you specify a country or preference for your medical trip?"}}
        elif count == 2:
            return {"message_type": "text", "content": {"prompt": "Here are popular destinations: Malaysia, Thailand, Singapore, Korea. Would you like to choose one?"}}
        elif count >= 3:
            return {"message_type": "text", "content": {"prompt": "Without a destination or budget preference, I cannot proceed further. Please restart when ready."}}
    return None

# ===================== Departure City Consistency Check =====================
def check_departure_city_consistency(agent_output: dict, session_state: dict) -> Optional[dict]:
    """Ensure the departure city in agent_output matches session_state."""
    try:
        plan_params = session_state.get("plan_parameters", {})
        session_departure = plan_params.get("departure_city")
        output_departure = (
            agent_output.get("content", {})
            .get("travel_arrangement_response", {})
            .get("departure_city")
        )

        if session_departure and output_departure:
            if session_departure.lower().strip() != output_departure.lower().strip():
                return {
                    "message_type": "text",
                    "content": {
                        "prompt": (
                            f"⚠️ I noticed a mismatch: your profile says departure city is **{session_departure}**, "
                            f"but the plan suggests **{output_departure}**.\n"
                            "Which one should I use to continue planning?"
                        )
                    }
                }
    except Exception as e:
        logger.warning(f"Departure city consistency check failed: {e}")
    return None

# ===================== Agent Executor Factory =====================
async def get_planning_agent_executor(prompt_template_str: Optional[str] = None) -> AgentExecutor:
    if prompt_template_str is None:
        prompt_template_str = load_prompt()

    try:
        llm = LoadModel.load_llm_model()
    except Exception as e:
        logger.error(f"Failed to load LLM model: {e}", exc_info=True)
        sys.exit(1)

    tools = [
        MedicalPlanningTool(),
        TravelArrangementTool(),
        TravelLogisticsTool(),
        UpdateSessionStateTool(),
        CalculateBudgetTool(),
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=40)
    logger.info("Planning AgentExecutor created successfully.")
    return agent_executor

# ===================== Output Handlers =====================
def _handle_agent_output(agent_output: Any, session_state: Dict) -> Dict:
    def clean_json_string(s: str) -> str:
        clean_s = re.sub(r"```json\s*", "", s, flags=re.DOTALL)
        clean_s = re.sub(r"\s*```\s*$", "", clean_s, flags=re.DOTALL)
        return clean_s.strip()

    if isinstance(agent_output, str):
        cleaned_output = clean_json_string(agent_output)
        try:
            parsed_output = json.loads(cleaned_output)
            if isinstance(parsed_output, dict):
                city_check = check_departure_city_consistency(parsed_output, session_state)
                if city_check:
                    return city_check
                return parsed_output
        except json.JSONDecodeError:
            return {
                "message_type": "error",
                "content": {
                    "prompt": "Invalid output format",
                    "raw": str(agent_output),
                },
            }

    if isinstance(agent_output, dict):
        city_check = check_departure_city_consistency(agent_output, session_state)
        if city_check:
            return city_check
        return agent_output

    return {"message_type": "text", "content": {"prompt": str(agent_output)}}

# ===================== Terminal Interactive Mode =====================
async def run_interactive_session_async():
    agent_executor = await get_planning_agent_executor()
    print("Planning Agent is ready. Enter your questions below (type 'exit' or 'quit' to stop):")
    chat_history = []

    session_state = {"plan_parameters": {}}

    profile_data = {
        "destination_country": "Malaysia",
        "medical_purpose": "Heart Bypass Surgery",
        "patient_nationality": "Chinese",
        "estimated_budget_usd": 10000,
        "departure_city": "Beijing",
    }
    session_state["plan_parameters"].update(profile_data)
    chat_history.append(SystemMessage(content=f"User Profile: {json.dumps(profile_data)}"))

    # Smart Start greeting
    print(json.dumps({
        "message_type": "text",
        "content": {
            "prompt": f"Hello! I see you're interested in {profile_data['destination_country']} for {profile_data['medical_purpose']}. Is that correct?"
        }
    }, indent=2, ensure_ascii=False))

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting Planning Agent. Goodbye!")
                break

            # Handle vague inputs with fallback strategy
            fallback_response = handle_vague_input(user_input, session_state)
            if fallback_response:
                print(json.dumps(fallback_response, indent=2, ensure_ascii=False))
                continue

            chat_history.append(HumanMessage(content=user_input))
            response = await agent_executor.ainvoke({
                "input": user_input,
                "chat_history": chat_history[-10:],
                "session_state": json.dumps(session_state),
                "agent_scratchpad": "",
            })
            agent_output = response.get("output") or response.get("output_text")
            final_output = _handle_agent_output(agent_output, session_state)
            chat_history.append(AIMessage(content=json.dumps(final_output)))
            print(json.dumps(final_output, indent=2, ensure_ascii=False))

        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting.")
            break
        except Exception as e:
            logger.error(f"Error during session: {e}", exc_info=True)
            print(json.dumps({"message_type": "text", "content": {"prompt": "An unexpected error occurred. Please try again."}}, indent=2, ensure_ascii=False))

# ===================== Entrypoint =====================
if __name__ == "__main__":
    asyncio.run(run_interactive_session_async())

    
# ===================== Terminal Interactive Mode =====================
#def _format_medical_plan_output(data: dict) -> str:
#    response = data.get("content", {}).get("medical_planning_response", {})
#    message = response.get("message", "Here are the medical plan options I found:")
#     plans_text = f"**{message}**\n\n"
#     options = response.get("medical_plan_options", [])
#     if not options:
#         plans_text += "No suitable medical plan options were found."
#         return plans_text
#     for i, plan in enumerate(options, start=1):
#         plans_text += f"**Option {i}:**\n"
#         clinic_name = plan.get("clinic_name")
#         if clinic_name and isinstance(clinic_name, str) and clinic_name.upper() != "N/A":
#             plans_text += f" - **Hospital:** {clinic_name}\n"
#         cost = plan.get("estimated_cost_usd")
#         if cost:
#             plans_text += f" - **Estimated Cost:** {cost}\n"
#         plans_text += f" - **Plan Details:** {plan.get('brief_description', 'No summary available.')}\n\n"
#     visa_info = response.get("visa_information", {})
#     if visa_info:
#         plans_text += "\n---\n**Visa Requirements**\n"
#         plans_text += f"- **Visa Type:** {visa_info.get('visa_type', 'N/A')}\n"
#         required_docs = visa_info.get("required_documents", [])
#         if required_docs:
#             plans_text += "- **Required Documents:**\n"
#             for doc in required_docs:
#                 plans_text += f"  - {doc}\n"
#         plans_text += f"- **Notes:** {visa_info.get('notes', 'N/A')}\n"
#     return plans_text

# def _format_travel_plan_output(data: dict) -> str:
#     response = data.get("content", {}).get("travel_arrangement_response", {})
#     message = response.get("message", "Here are the travel arrangement options:")
#     plan_text = f"**{message}**\n\n"
#     plan_text += f"---**Flight Suggestions**---\n"
#     for i, flight in enumerate(response.get("flight_suggestions", []), start=1):
#         plan_text += f"**Option {i}:**\n"
#         plan_text += f" - **Airline:** {flight.get('airline', 'N/A')}\n"
#         plan_text += f" - **Price:** {flight.get('price_usd', 'N/A')}\n"
#         plan_text += f" - **Details:** {flight.get('description', 'No details available.')}\n\n"
#     plan_text += f"---**Accommodation Suggestions**---\n"
#     for i, hotel in enumerate(response.get("accommodation_suggestions", []), start=1):
#         plan_text += f"**Option {i}:**\n"
#         plan_text += f" - **Hotel:** {hotel.get('hotel_name', 'N/A')}\n"
#         plan_text += f" - **Price per night:** {hotel.get('price_per_night_usd', 'N/A')}\n"
#         plan_text += f" - **Details:** {hotel.get('brief_description', 'No details available.')}\n\n"
#     return plan_text

# def _format_local_logistics_output(data: dict) -> str:
#     response = data.get("content", {}).get("travel_logistics_response", {})
#     message = response.get("message", "Here is your local logistics plan:")
#     plan_text = f"**{message}**\n\n"
    
#     plan_text += "**Airport Pick-up:**\n"
#     plan_text += f" - {response.get('airport_pick_up_info', 'Not available.')}\n\n"
    
#     plan_text += "**Local Transportation:**\n"
#     plan_text += f" - {response.get('local_transport_info', 'Not available.')}\n\n"
    
#     plan_text += "**Additional Services:**\n"
#     for service in response.get("additional_local_services_info", []):
#         plan_text += f" - **{service.get('service_name')}:** {service.get('description', 'N/A')}\n"
#     plan_text += "\n"

#     plan_text += "**Dietary Recommendations:**\n"
#     for rec in response.get("dietary_recommendations_info", []):
#         plan_text += f" - **{rec.get('restaurant_name')}:** {rec.get('description', 'N/A')}\n"
#    plan_text += "\n"

#     plan_text += "**SIM Card Assistance:**\n"
#     plan_text += f" - {response.get('sim_card_assistance_info', 'Not available.')}\n\n"

#     plan_text += "**Leisure Activities:**\n"
#     for activity in response.get("leisure_activity_suggestions_info", []):
#         plan_text += f" - **{activity.get('activity_name')}:** {activity.get('description', 'N/A')}\n"
#     plan_text += "\n"
#     return plan_text

# def _format_final_plan_output(data: dict) -> str:
#     final_plan_content = data.get("content", {})
#     message = "Your complete medical tourism plan is ready!\n\n"
    
    # Medical Plan
#     medical_plan = final_plan_content.get("medical_plan", {})
#     message += "--- **Medical Plan** ---\n"
#     message += f"**Hospital:** {medical_plan.get('clinic_name', 'N/A')}\n"
#     message += f"**Treatment:** {medical_plan.get('treatment_name', 'N/A')}\n"
#     message += f"**Estimated Cost:** ${medical_plan.get('estimated_cost_usd', 'N/A')}\n\n"

    # Travel Arrangements
#     travel_arrangements = final_plan_content.get("travel_arrangement", {})
#     message += "--- **Travel Arrangements** ---\n"
#     message += f"**Flight:** {travel_arrangements.get('flight_suggestion', {}).get('description', 'N/A')}\n"
#     message += f"**Accommodation:** {travel_arrangements.get('accommodation_suggestion', {}).get('brief_description', 'N/A')}\n\n"

    # Local Logistics
#     local_logistics = final_plan_content.get("local_logistics", {})
#     message += "--- **Local Logistics** ---\n"
#     message += f"**Airport Pickup:** {local_logistics.get('airport_pick_up_info', 'N/A')}\n"
#     message += f"**Local Transport:** {local_logistics.get('local_transport_info', 'N/A')}\n"
#     message += f"**Leisure:** {local_logistics.get('leisure_activity_suggestions_info', [{'activity_name': 'N/A'}])[0].get('activity_name')}\n\n"

    # Total Budget
#     total_budget = final_plan_content.get("total_budget", {})
#     message += "--- **Budget Summary** ---\n"
#     message += f"**Total Estimated Budget:** ${total_budget.get('total_estimated_budget_usd', 'N/A')}\n"
#     breakdown = total_budget.get('breakdown', {})
#     message += f" - Medical: ${breakdown.get('medical_cost', 'N/A')}\n"
#     message += f" - Flight: ${breakdown.get('flight_cost', 'N/A')}\n"
#     message += f" - Accommodation: ${breakdown.get('accommodation_cost', 'N/A')}\n"
#     message += f" - Airport Pickup: ${breakdown.get('airport_pickup_cost', 'N/A')}\n"
    
#     return message
