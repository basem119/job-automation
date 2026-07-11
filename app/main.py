from pathlib import Path
import logging

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
level=logging.INFO,
format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

def main() -> None:
    logger.info("Job Automation application started.")
logger.info("Environment loaded successfully.")
logger.info("Application finished successfully.")

if __name__ == "__main__":
    main()
