from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "viralforge_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,  # One task at a time (important for long tasks)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (memory cleanup)
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'collect-trends-periodic': {
        'task': 'app.tasks.collect_trends_task',
        'schedule': settings.trend_scrape_interval_hours * 3600,  # Convert hours to seconds
    },
    'analyze-trends-periodic': {
        'task': 'app.tasks.analyze_trends_task',
        'schedule': settings.trend_scrape_interval_hours * 3600,  # Same interval
        # Analysis runs at same interval but relies on collected data from last 24h
    },
}

# Ensure pipeline tasks are registered
import app.pipeline  # noqa: F401

# Auto-discover tasks from app.tasks module
celery_app.autodiscover_tasks(['app'])
