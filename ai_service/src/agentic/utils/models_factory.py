# ai_service/src/agentic/utils/models_factory.py
import os
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from ..logger import logging

@lru_cache(maxsize=1)
def get_gemini_planner():
    """
    Singleton: Returns the main Gemini instance for Planning.
    Initialized once per process.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.error("❌ GOOGLE_API_KEY not found!")
        return None
        
    logging.info("🔌 Establishing connection to Google Gemini...")

    return ChatGoogleGenerativeAI(
        model="models/gemini-3-flash-preview",
        temperature=0.3,
        google_api_key=api_key
    )

@lru_cache(maxsize=1)
def get_auditor_model():
    """
    Singleton: Returns the Llama 3.3 instance for Auditing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logging.warning("⚠️ GROQ_API_KEY not found. Auditor disabled.")
        return None

    logging.info("🔌 Establishing connection to Groq Llama 3.3...")

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        groq_api_key=api_key
    )