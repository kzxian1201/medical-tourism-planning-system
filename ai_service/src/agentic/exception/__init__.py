import sys
from typing import Any, Optional # Add Optional import here

def error_message_detail(error_message_str: str, error_detail_sys: Any) -> str:
    # error_detail_sys is expected to be the sys module
    # Get the exception info tuple (type, value, traceback)
    _, exc_value, exc_tb = error_detail_sys.exc_info() # Now it should correctly receive sys

    file_name = "Unknown File" # Default values
    line_number = "Unknown Line"
    
    # ONLY try to access tb_frame if exc_tb is not None
    if exc_tb is not None:
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
    
    # Use the actual exception message if available, otherwise fallback to the provided string
    actual_error_msg = str(exc_value) if exc_value else error_message_str

    formatted_message = (
        f"Error occurred in python script name [{file_name}] "
        f"line number [{line_number}] error message: [{actual_error_msg}]"
    )
    return formatted_message

class CustomException(Exception):
    # Keep the reversed order for parameters as discussed in the previous turn
    def __init__(self, error_detail_sys: Any, error_message: str): # error_detail_sys is sys, error_message is string
        super().__init__(error_message) # super() expects the message first

        self.error_message = error_message_detail(
            error_message,      # Pass the string message as the first argument
            error_detail_sys    # Pass the sys module as the second argument
        )

    def __str__(self):
        return self.error_message