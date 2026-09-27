from celery import Celery

from app.config import settings

celery_app = Celery(
    "eve_healthcare",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    # thread pool for cross-platform compatibility
    worker_pool="threads",
    worker_concurrency=4,
    result_expires=3600,
    task_default_retry_delay=30,
    task_max_retries=3,
    # short socket timeout so broker downtime does not block api requests
    broker_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": False,
    },
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
    task_default_queue="eve_default",
    task_queues={
        "eve_default": {},
        "eve_notifications": {},
        "eve_webhooks": {},
    },
    task_routes={
        "app.worker.tasks.notify_booking_created": {"queue": "eve_notifications"},
        "app.worker.tasks.notify_payment_result": {"queue": "eve_notifications"},
        "app.worker.tasks.retry_webhook_processing": {"queue": "eve_webhooks"},
    },
)
