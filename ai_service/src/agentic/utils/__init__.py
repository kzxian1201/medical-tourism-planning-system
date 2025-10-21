import sys
from ..logger import logging

def error_message_detail(error, error_detail:sys):
    _, _, exc_tb = sys.exc_info() 
    
    if exc_tb:
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
        error_message = "Error occurred in python script name [{0}] line number [{1}] error message [{2}]".format(
            file_name, line_number, str(error))
    else:
        error_message = "Error occurred: [{0}]".format(str(error))
        
    logging.error(error_message)
    return error_message

class CustomException(Exception):
    def __init__(self, sys_module, error_object: Exception): # 
        super().__init__(str(error_object)) 
        self.error_message = error_message_detail(error_object, sys_module) 
    
    def __str__(self):
        return self.error_message