# ai_service/src/agentic/utils/main_utils.py
import os
import logging
import sys
import re
import warnings
from proto.marshal.rules import enums
from ..logger import logging
from ..exception import CustomException
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Validate required API keys
required_keys = ["GOOGLE_API_KEY"]

# Check for missing keys
missing_keys = [key for key in required_keys if not os.getenv(key)]
if missing_keys:
    print(f"DEBUG: Application is missing the following environment variables: {missing_keys}")
    raise CustomException(sys, "Missing required environment variables: " + ', '.join(missing_keys))

class LoadModel:
    @classmethod
    def load_llm_model(cls, model_name: str = "gemini-1.5-flash", temperature: float = 0.7):
        try:
            logging.info(f"Loading Google Gemini model: {model_name}")
            
            llm = ChatGoogleGenerativeAI(model=model_name,temperature=temperature,max_output_tokens=1024,)
            
            logging.info(f"Google Gemini model '{model_name}' loaded successfully.")
            return llm 

        except Exception as e:
            logging.error(f"DEBUG: Critical error in LoadModel.load_llm_model(): {e}", exc_info=True)
            print(f"\n--- DEBUG: Full Traceback from LoadModel.load_llm_model() ---")
            import traceback; traceback.print_exc(file=sys.stdout)
            print(f"DEBUG: Type of exception caught: {type(e)}")
            print(f"DEBUG: Message of exception caught: {e}")
            raise CustomException(sys, e)
    
def escape_braces_except_placeholders(s: str) -> str:
        """
        Escape braces except those used as variable placeholders in the format {variable}.
        """
        placeholder_pattern = re.compile(r"\{[a-zA-Z0-9_]+\}")
        result = []
        last_index = 0
        for match in placeholder_pattern.finditer(s):
            start, end = match.span()
            segment = s[last_index:start]
            segment_escaped = segment.replace("{", "{{").replace("}", "}}")
            result.append(segment_escaped)
            result.append(s[start:end])
            last_index = end
        tail_segment = s[last_index:]
        tail_escaped = tail_segment.replace("{", "{{").replace("}", "}}")
        result.append(tail_escaped)
        return "".join(result)

def setup_proto_warnings():
    """
    Suppresses the 'Unrecognized FinishReason' warning and
    provides a fallback for unrecognized enum values.
    """
    warnings.filterwarnings("ignore", message="Unrecognized FinishReason enum value")
    def safe_to_python(self, value, *, absent=None):
        try:
            return self._enum_cls(value)
        except Exception:
            warnings.warn(f"Unrecognized FinishReason enum value: {value}")
            class _EnumLike:
                def __init__(self, v):
                    self.value = v
                @property
                def name(self):
                    return f"UNKNOWN_FINISH_REASON_{self.value}"
                def __int__(self):
                    return int(self.value)
                def __repr__(self):
                    return f"<EnumLike name={self.name} value={self.value}>"
            return _EnumLike(value)
    enums.EnumRule.to_python = safe_to_python