"""Run the arq worker responsible for audit LLM evaluations."""

from app.core.jobs import WorkerConfig
from app.modules.audit.judge import evaluation_worker


class EvaluationWorkerSettings:
    functions = [evaluation_worker]
    redis_settings = WorkerConfig(functions=[]).redis_settings
    max_jobs = 4
    job_timeout = 600
