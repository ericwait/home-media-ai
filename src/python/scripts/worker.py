"""
HomeMedia AI Worker Script.
Listens for jobs from Redis and performs AI inference.

Usage:
    python src/python/scripts/worker.py
"""
import json
import logging
import time
from pathlib import Path

from home_media.config import load_config, get_redis_config
from home_media.utils import translate_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker")

def process_job(job_data, mapping):
    """Placeholder for job processing logic."""
    original_path = job_data.get("image_path")
    if not original_path:
        logger.error("Job missing image_path")
        return

    # Translate path from Mac (Server) to Windows (Worker)
    local_path = translate_path(original_path, mapping)
    logger.info(f"Processing image: {original_path} -> {local_path}")
    
    # Verify file existence
    if not Path(local_path).exists():
        logger.error(f"File not found: {local_path}")
        return

    # TODO: Load model and run inference
    logger.info("Inference logic goes here...")
    time.sleep(1) # Simulate work

def main():
    try:
        config = load_config()
        redis_config = get_redis_config(config, use_defaults=True, logger=logger)
        path_mapping = config.get("path_mapping", {})
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    try:
        import redis
        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config.get('password'),
            db=redis_config.get('db', 0),
            decode_responses=True
        )
        # Verify connectivity before entering processing loop
        r.ping()
        logger.info(f"Connected to Redis at {redis_config['host']}:{redis_config['port']}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return

    queue_name = "home_media_jobs"
    logger.info(f"Waiting for jobs on queue: {queue_name}")

    while True:
        try:
            if job := r.blpop(queue_name, timeout=5):
                _, data_str = job
                logger.info(f"Received job: {data_str}")
                try:
                    job_data = json.loads(data_str)
                    process_job(job_data, path_mapping)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode JSON from queue '{queue_name}': {e}. "
                        f"Raw payload: {data_str!r}"
                    )
                    # Skip this malformed payload and continue to next job
                    continue
        except KeyboardInterrupt:
            logger.info("Worker stopping...")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
