"""Recruiter discovery strategies."""
from __future__ import annotations

from app.recruiter.strategies.company_careers_page import CompanyCareersPageStrategy
from app.recruiter.strategies.company_contact_page import CompanyContactPageStrategy
from app.recruiter.strategies.common_address import CommonAddressStrategy
from app.recruiter.strategies.greenhouse import GreenhouseStrategy

__all__ = [
    "GreenhouseStrategy",
    "CompanyCareersPageStrategy",
    "CompanyContactPageStrategy",
    "CommonAddressStrategy",
]
