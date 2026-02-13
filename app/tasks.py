from app.worker import celery_app
import time


@celery_app.task(bind=True, max_retries=3)
def test_task(self):
    """Simple test task to verify Celery is working"""
    try:
        print("Test task started")
        time.sleep(2)  # Simulate work
        print("Test task completed")
        return {"status": "success", "message": "Test task executed successfully"}
    except Exception as exc:
        print(f"Test task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
