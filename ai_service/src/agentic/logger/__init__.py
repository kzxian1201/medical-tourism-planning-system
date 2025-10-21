# src/agentic/logger/__init__.py
import logging
import os
from datetime import datetime
from from_root import from_root
import sys

LOG_DIR_PATH = os.path.join(from_root(), 'log')

os.makedirs(LOG_DIR_PATH, exist_ok=True)

LOG_FILE_NAME = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"

LOG_FILE_FULL_PATH = os.path.join(LOG_DIR_PATH, LOG_FILE_NAME)

logging.basicConfig(
    format="[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,         
    handlers=[
        logging.FileHandler(LOG_FILE_FULL_PATH), 
        logging.StreamHandler(sys.stdout)     
    ]
)

logging.info(f"Logging configured. Log file: {LOG_FILE_FULL_PATH}")