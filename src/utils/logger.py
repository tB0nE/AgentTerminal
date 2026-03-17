import logging
import os

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Create a logger for the entire application
logger = logging.getLogger("writer_agent")
logger.setLevel(logging.DEBUG)

# Create a file handler for detailed debug logs
file_handler = logging.FileHandler("logs/writer_agent.log")
file_handler.setLevel(logging.DEBUG)

# Create a clear format for logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(file_handler)

def log_debug(msg):
    logger.debug(msg)

def log_info(msg):
    logger.info(msg)

def log_error(msg):
    logger.error(msg)
