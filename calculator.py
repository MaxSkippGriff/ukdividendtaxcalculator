"""UK Dividend Tax Calculator — 2026/27 tax year constants and logic."""

from __future__ import annotations
import datetime
from dataclasses import dataclass


def active_tax_year() -> str:
    today = datetime.date.today()
    return "2026/27" if today >= datetime.date(2026, 4, 6) else "2025/26"


TAX_YEAR = "2026/27"

# Income tax thresholds 2026/27
PERSONAL_ALLOWANCE = 12_570
BASIC_RATE_LIMIT = 50_270
HIGHER_RATE_LIMIT = 125_140
BASIC_RATE_BAND = BASIC_RATE_LIMIT - PERSONAL_ALLOWANCE  # £37,700

# Dividend allowance (£500 from April 2024)
DIVIDEND_ALLOWANCE = 500

# Dividend tax rates 2026/27
# Source: https://www.gov.uk/tax-on-dividends
DIVIDEND_BASIC_RATE = 0.0875    # 8.75% — 2026/27 basic-rate dividend tax
DIVIDEND_HIGHER_RATE = 0.3375   # 33.75% — 2026/27 higher-rate dividend tax
DIVIDEND_ADDITIONAL_RATE = 0.3935  # 39.35% — 2026/27 additional-rate dividend tax


@dataclass(frozen=True)
class DividendTaxResult:
    total_gross_income: float
    personal_allowance_used: float
    dividend_allowance_used: float
    taxable_dividends: float
    dividends_at_basic: float
    dividends_at_higher: float
    dividends_at_additional: float
    tax_at_basic: float
    tax_at_higher: float
    tax_at_additional: float
    total_dividend_tax: float
    net_dividend_income: float
    total_dividend_income: float
    effective_dividend_rate: float


def _r(v: float) -> float:
    return round(float(v), 2)


def calculate_dividend_tax(
    salary_income: float = 0.0,
    dividend_income: float = 0.0,
    other_income: float = 0.0,
    pension_contributions: float = 0.0,
) -> DividendTaxResult:
    """
    Calculate UK dividend tax for 2026/27.
    Salary and other non-dividend income fill the band first.
    Dividends sit on top. Pension contributions reduce non-dividend taxable income.
    """
    salary = max(0.0, float(salary_income))
    divs = max(0.0, float(dividend_income))
    other = max(0.0, float(other_income))
    pension = max(0.0, float(pension_contributions))

    gross = salary + divs + other
    non_div = salary + other

    # Personal allowance tapers above £100k total income (£2 removed per £1 over)
    pa = PERSONAL_ALLOWANCE
    if gross > 100_000:
        pa = max(0.0, PERSONAL_ALLOWANCE - (gross - 100_000) / 2.0)

    # Pension reduces non-dividend taxable income
    non_div_after_pension = max(0.0, non_div - pension)

    # PA covers non-dividend income first
    pa_used_by_non_div = min(pa, non_div_after_pension)
    pa_remaining = max(0.0, pa - pa_used_by_non_div)
    taxable_non_div = max(0.0, non_div_after_pension - pa_used_by_non_div)

    # Remaining PA covers dividends
    divs_covered_by_pa = min(pa_remaining, divs)
    divs_after_pa = divs - divs_covered_by_pa

    # Dividend allowance (£500)
    div_allowance_used = min(DIVIDEND_ALLOWANCE, divs_after_pa)
    taxable_divs = max(0.0, divs_after_pa - div_allowance_used)

    # How much of basic-rate band remains after non-dividend income
    basic_used_by_non_div = min(taxable_non_div, BASIC_RATE_BAND)
    basic_remaining = max(0.0, BASIC_RATE_BAND - basic_used_by_non_div)

    # Higher rate band: £74,870 (125140 - 50270)
    higher_band = HIGHER_RATE_LIMIT - BASIC_RATE_LIMIT
    higher_used_by_non_div = max(0.0, taxable_non_div - BASIC_RATE_BAND)
    higher_remaining = max(0.0, higher_band - higher_used_by_non_div)

    # Allocate taxable dividends across bands
    divs_basic = min(taxable_divs, basic_remaining)
    divs_higher = min(max(0.0, taxable_divs - divs_basic), higher_remaining)
    divs_additional = max(0.0, taxable_divs - divs_basic - divs_higher)

    tax_basic = divs_basic * DIVIDEND_BASIC_RATE
    tax_higher = divs_higher * DIVIDEND_HIGHER_RATE
    tax_additional = divs_additional * DIVIDEND_ADDITIONAL_RATE
    total_div_tax = tax_basic + tax_higher + tax_additional

    net_div = divs - total_div_tax
    eff_rate = (total_div_tax / divs * 100.0) if divs > 0 else 0.0

    return DividendTaxResult(
        total_gross_income=_r(gross),
        personal_allowance_used=_r(pa_used_by_non_div + divs_covered_by_pa),
        dividend_allowance_used=_r(div_allowance_used),
        taxable_dividends=_r(taxable_divs),
        dividends_at_basic=_r(divs_basic),
        dividends_at_higher=_r(divs_higher),
        dividends_at_additional=_r(divs_additional),
        tax_at_basic=_r(tax_basic),
        tax_at_higher=_r(tax_higher),
        tax_at_additional=_r(tax_additional),
        total_dividend_tax=_r(total_div_tax),
        net_dividend_income=_r(net_div),
        total_dividend_income=_r(divs),
        effective_dividend_rate=_r(eff_rate),
    )
