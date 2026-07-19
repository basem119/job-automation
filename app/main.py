from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings
from config.preferences import Preferences
from config.profile import Profile
from core.exceptions import ApplicationError, ConfigurationError
from core.filtering.engine import FilteringEngine
from core.logging import configure_logging
from core.version import version
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository
from workflows.job_collection_workflow import JobCollectionWorkflow, build_collectors
from workflows.job_analysis_workflow import JobAnalysisWorkflow
from workflows.recruiter_discovery_workflow import RecruiterDiscoveryWorkflow
from workflows.application_draft_workflow import ApplicationDraftWorkflow


def main() -> int:
    try:
        settings = Settings.load()
        settings.validate_runtime_paths()
        logger = configure_logging(settings.log_level, settings.log_directory)

        logger.info("Application version: %s", version)
        logger.info("Configuration loaded")
        logger.info("Logging initialized")
        logger.info("Filesystem validated")

        database = SQLiteDatabase(settings.database_path)
        workflow = JobCollectionWorkflow(collectors=build_collectors(settings), database=database)
        summary = workflow.run()

        logger.info("Jobs downloaded: %s", summary["downloaded"])
        logger.info("Jobs inserted: %s", summary["inserted"])
        # logger.info("Jobs skipped (duplicates): %s", summary["duplicates"])

        # Run recommendation engine on newly inserted jobs
        preferences = Preferences.load(Path("config/preferences.yaml"))
        repository = JobRepository(database)
        filtering_engine = FilteringEngine(database=database, repository=repository, preferences=preferences)
        filter_summary = filtering_engine.run()

        logger.info("Jobs evaluated: %s", filter_summary["evaluated"])
        logger.info("Jobs recommended: %s", filter_summary["recommended"])
        logger.info("Jobs not recommended: %s", filter_summary["not_recommended"])
        logger.info("Jobs hard rejected: %s", filter_summary["hard_rejected"])
        logger.info("Average score: %.2f", filter_summary["average_score"])
        logger.info("Highest score: %s", filter_summary["highest_score"])
        logger.info("Lowest score: %s", filter_summary["lowest_score"])

        # Run job analysis on recommended jobs
        profile = Profile.load()
        analysis_workflow = JobAnalysisWorkflow(
            database=database,
            job_repository=repository,
            profile=profile,
        )
        analysis_summary = analysis_workflow.run()

        logger.info("Job analysis - Recommended jobs: %s", analysis_summary["recommended_jobs"])
        logger.info("Job analysis - Already analyzed: %s", analysis_summary["already_analyzed"])
        logger.info("Job analysis - New analyses: %s", analysis_summary["new_analyses"])
        logger.info("Job analysis - Execution time: %.2f seconds", analysis_summary["execution_time"])

        # Run recruiter discovery on recommended jobs
        recruiter_workflow = RecruiterDiscoveryWorkflow(
            database=database,
            job_repository=repository,
        )
        recruiter_summary = recruiter_workflow.run()

        logger.info("Recruiter discovery - Recommended jobs: %s", recruiter_summary["recommended_jobs"])
        logger.info("Recruiter discovery - Already discovered: %s", recruiter_summary["already_discovered"])
        logger.info("Recruiter discovery - Recruiters found: %s", recruiter_summary["recruiters_found"])
        logger.info("Recruiter discovery - Recruiters missing: %s", recruiter_summary["recruiters_missing"])
        logger.info("Recruiter discovery - Execution time: %.2f seconds", recruiter_summary["execution_time"])

        # Run application draft generation on recommended jobs
        draft_workflow = ApplicationDraftWorkflow(repository=repository, settings=settings)
        draft_summary = draft_workflow.run()

        logger.info("Application draft - Recommended jobs:       %s", draft_summary["recommended_jobs"])
        logger.info("Application draft - Recruiter found:         %s", draft_summary["recruiter_discovery_found"])
        logger.info("Application draft - Applications built:      %s", draft_summary["applications_built"])
        logger.info("Application draft - Drafts created:          %s", draft_summary["drafts_created"])
        logger.info("Application draft - Drafts with recipient:   %s", draft_summary["drafts_with_recipient"])
        logger.info("Application draft - Drafts without recipient:%s", draft_summary["drafts_without_recipient"])
        logger.info("Application draft - Validation failures:     %s", draft_summary["validation_failures"])
        logger.info("Application draft - Draft failures:          %s", draft_summary["draft_failures"])

        logger.info("Application initialized successfully")
        logger.info("Application finished")
        return 0
    except (ApplicationError, ConfigurationError, ValueError) as exc:
        logging.getLogger("job_automation").error("Application startup failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
