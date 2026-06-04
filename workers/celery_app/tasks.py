import asyncio
import httpx
from celery import Celery
from shared.config.settings import settings
from shared.db.session import get_db_context
from shared.db.models import PullRequest, PRStatus
from sqlalchemy import update
from shared.observability import logger

celery_app = Celery(
    "ai_pr_reviewer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


# Helper function to run async DB updates from sync Celery task
def _update_pr_status(pr_id: str, status: PRStatus):
    async def update_db():
        async with get_db_context() as session:
            stmt = (
                update(PullRequest).where(PullRequest.id == pr_id).values(status=status)
            )
            await session.execute(stmt)
            await session.commit()

    asyncio.run(update_db())


@celery_app.task(bind=True, max_retries=3)
def review_pr(
    self,
    pr_id: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    installation_id: int,
):
    logger.info("starting_review_pr_task", pr_id=pr_id)
    _update_pr_status(pr_id, PRStatus.reviewing)

    payload = {
        "pr_id": pr_id,
        "repo": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "installation_id": installation_id,
    }

    try:
        # We use sync httpx client since celery task is sync by default
        with httpx.Client(timeout=300.0) as client:  # LangGraph can take time
            response = client.post(
                f"{settings.ORCHESTRATOR_URL}/review/start", json=payload
            )
            response.raise_for_status()

        _update_pr_status(pr_id, PRStatus.completed)
        logger.info("completed_review_pr_task", pr_id=pr_id)

    except httpx.HTTPError as exc:
        logger.error("orchestrator_call_failed", pr_id=pr_id, error=str(exc))
        countdown = 60 * (2**self.request.retries)
        try:
            self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            _update_pr_status(pr_id, PRStatus.failed)
            raise
    except Exception as exc:
        logger.exception("unexpected_error_in_review_pr_task", pr_id=pr_id)
        _update_pr_status(pr_id, PRStatus.failed)
        raise exc


@celery_app.task(bind=True, max_retries=3)
def learn_pr(self, repo_full_name: str, pr_number: int, installation_id: int):
    logger.info("starting_learn_pr_task", repo=repo_full_name, pr_number=pr_number)

    payload = {
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "installation_id": installation_id,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.LEARNER_URL}/learn/merged-pr", json=payload
            )
            response.raise_for_status()
        logger.info("completed_learn_pr_task", repo=repo_full_name, pr_number=pr_number)
    except httpx.HTTPError as exc:
        countdown = 60 * (2**self.request.retries)
        self.retry(exc=exc, countdown=countdown)
