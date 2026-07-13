from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from config.preferences import Preferences
from core.filtering.rules import ExperienceRule, HardRejectRule, LocationRule, TechnologyRule, TitleRule
from infrastructure.sqlite.database import SQLiteDatabase
from infrastructure.sqlite.job_repository import JobRepository

logger = logging.getLogger("job_automation")


class RecommendationEngine:
    """Evaluate all jobs with recommendation rules and assign scores."""

    def __init__(
        self,
        database: SQLiteDatabase | None = None,
        repository: JobRepository | None = None,
        preferences: Preferences | None = None,
    ) -> None:
        self.database = database or SQLiteDatabase()
        self.repository = repository or JobRepository(self.database)
        self.preferences = preferences or Preferences.load(Path("config/preferences.yaml"))
        self.hard_reject_rule = HardRejectRule(self.preferences)
        self.scoring_rules = [
            LocationRule(self.preferences),
            TitleRule(self.preferences),
            TechnologyRule(self.preferences),
            ExperienceRule(self.preferences),
        ]

    def run(self) -> dict:
        """Evaluate all NEW jobs, assign recommendation scores, update status."""
        started_at = time.perf_counter()
        jobs = self.repository.load_new_jobs()
        evaluated = len(jobs)
        recommended = 0
        not_recommended = 0
        hard_rejected = 0
        scores: list[int] = []

        for job in jobs:
            # First, check hard reject conditions
            hard_reject_result = self.hard_reject_rule.evaluate(job)
            if not hard_reject_result.passed:
                # Hard rejected
                self.repository.update_recommendation(
                    job.id,
                    status="HARD_REJECTED",
                    score=0,
                    summary=hard_reject_result.summary,
                    details=hard_reject_result.details,
                )
                hard_rejected += 1
                continue

            # Evaluate all scoring rules
            all_results = [rule.evaluate(job) for rule in self.scoring_rules]
            
            # Calculate total score
            total_score = sum(r.score for r in all_results)
            
            # Collect all details
            all_details = []
            for result in all_results:
                all_details.extend(result.details)

            # Generate summary
            summary = self._generate_summary(job, all_results, all_details, total_score)

            # Classify based on threshold
            threshold = self.preferences.recommendation.minimum_score
            if total_score >= threshold:
                status = "RECOMMENDED"
                recommended += 1
            else:
                status = "NOT_RECOMMENDED"
                not_recommended += 1

            scores.append(total_score)

            # Update job with recommendation
            self.repository.update_recommendation(
                job.id,
                status=status,
                score=total_score,
                summary=summary,
                details=all_details,
            )

        elapsed = time.perf_counter() - started_at

        # Calculate statistics
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0

        logger.info("Jobs evaluated: %s", evaluated)
        logger.info("Jobs recommended: %s", recommended)
        logger.info("Jobs not recommended: %s", not_recommended)
        logger.info("Jobs hard rejected: %s", hard_rejected)
        logger.info("Average score: %.2f", avg_score)
        logger.info("Highest score: %s", max_score)
        logger.info("Lowest score: %s", min_score)
        logger.info("Execution time: %.2f seconds", elapsed)

        return {
            "evaluated": evaluated,
            "recommended": recommended,
            "not_recommended": not_recommended,
            "hard_rejected": hard_rejected,
            "average_score": avg_score,
            "highest_score": max_score,
            "lowest_score": min_score,
            "execution_time": elapsed,
        }

    def _generate_summary(self, job, results, details, total_score) -> str:
        """Generate a concise human-readable recommendation summary."""
        # Get titles and techs
        title = job.title or "Unknown"
        technologies = job.technologies or []
        
        # Count detail contributions
        title_details = [d for d in details if d.rule == "Title"]
        tech_details = [d for d in details if d.rule == "Technology"]
        exp_details = [d for d in details if d.rule == "Experience"]
        loc_details = [d for d in details if d.rule == "Location"]
        
        summary_parts = []
        
        # Title summary
        if title_details:
            summary_parts.append(title_details[0].reason)
        
        # Technology summary
        if tech_details:
            for td in tech_details:
                if td.score > 0:
                    summary_parts.append(td.reason)
        
        # Experience summary
        if exp_details and any(e.score > 0 for e in exp_details):
            summary_parts.append(exp_details[0].reason)
        
        # Location summary
        if loc_details:
            if loc_details[0].score > 0:
                summary_parts.append(f"Position is {loc_details[0].reason.lower()}")
            elif loc_details[0].score < 0:
                summary_parts.append(loc_details[0].reason)
        
        summary = ". ".join(summary_parts)
        if summary:
            summary = summary.rstrip(". ") + f" (Score: {total_score})"
        else:
            summary = f"Recommendation score: {total_score}"
        
        return summary


# For backward compatibility
FilteringEngine = RecommendationEngine
