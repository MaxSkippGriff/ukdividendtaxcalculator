"""UKDividendTaxCalculator.co.uk Flask application."""
from __future__ import annotations
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, abort, make_response, redirect, render_template, request, send_from_directory
from flask_limiter import Limiter
from calculator import active_tax_year, TAX_YEAR, calculate_dividend_tax, PERSONAL_ALLOWANCE, BASIC_RATE_LIMIT, DIVIDEND_ALLOWANCE, DIVIDEND_BASIC_RATE, DIVIDEND_HIGHER_RATE, DIVIDEND_ADDITIONAL_RATE
from scraper_guard import init_guard

load_dotenv()

_PUBLIC_PATHS = (
    "/sitemap.xml", "/robots.txt", "/ads.txt", "/favicon.ico",
    "/favicon-16x16.png", "/favicon-32x32.png", "/apple-touch-icon.png",
    "/site.webmanifest", "/health",
)
_HONEYPOT_BLOCKED: set = set()

app = Flask(__name__)

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "ukdividendtaxcalculator.co.uk").replace("https://","").replace("http://","")
CANONICAL_HOST = CANONICAL_HOST[4:] if CANONICAL_HOST.startswith("www.") else CANONICAL_HOST
SITE_URL = f"https://{CANONICAL_HOST}"
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "G-8W2Z5MD7Y0").strip()
ADSENSE_CLIENT = os.getenv("ADSENSE_CLIENT", "ca-pub-3932111812673824").strip()

limiter = Limiter(
    app=app,
    key_func=lambda: (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or ""),
    default_limits=["300 per minute"],
    storage_uri="memory://",
    strategy="fixed-window",
)

init_guard(app, _PUBLIC_PATHS, "/trap", _HONEYPOT_BLOCKED)


@app.before_request
def enforce_canonical():
    host = (request.host or "").split(":")[0].lower()
    if host == f"www.{CANONICAL_HOST}":
        t = f"{SITE_URL}{request.full_path if request.query_string else request.path}"
        return redirect(t.rstrip("?"), code=301)
    return None


@app.after_request
def cache_headers(r):
    p = request.path or ""
    if p.startswith("/static/"):
        r.headers["Cache-Control"] = "public, max-age=300"
    elif p in ("/favicon.ico","/site.webmanifest","/apple-touch-icon.png","/favicon-32x32.png","/favicon-16x16.png"):
        r.headers["Cache-Control"] = "public, max-age=86400"
    elif p == "/robots.txt":
        r.headers["Cache-Control"] = "public, max-age=60"
    elif r.mimetype == "text/html":
        r.headers["Cache-Control"] = "private, no-store, max-age=0, must-revalidate"
    r.headers.setdefault("X-Content-Type-Options","nosniff")
    r.headers.setdefault("X-Frame-Options","SAMEORIGIN")
    r.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
    r.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
    return r


def _ctx(**kw):
    return dict(site_url=SITE_URL, tax_year=active_tax_year(), now=datetime.utcnow(),
                ga_measurement_id=GA_MEASUREMENT_ID, adsense_client=ADSENSE_CLIENT, **kw)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/favicon-32x32.png")
def favicon_32():
    return send_from_directory(app.static_folder, "favicon-32x32.png", mimetype="image/png")

@app.route("/favicon-16x16.png")
def favicon_16():
    return send_from_directory(app.static_folder, "favicon-16x16.png", mimetype="image/png")

@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory(app.static_folder, "apple-touch-icon.png", mimetype="image/png")

@app.route("/site.webmanifest")
def webmanifest():
    return send_from_directory(app.static_folder, "site.webmanifest", mimetype="application/manifest+json")

@app.route("/trap")
def trap():
    xff = request.headers.get("X-Forwarded-For", "")
    _HONEYPOT_BLOCKED.add(xff.split(",")[0].strip() if xff else (request.remote_addr or ""))
    abort(403)

@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/robots.txt")
def robots():
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /trap",
        "Disallow: /api/",
        "Disallow: /admin/",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
    ])
    r = make_response(body)
    r.content_type = "text/plain"
    return r


@app.route("/ads.txt")
def ads_txt():
    pub_id = ADSENSE_CLIENT.replace("ca-pub-", "").strip()
    body = f"google.com, pub-{pub_id}, DIRECT, f08c47fec0942fa0\n" if pub_id else ""
    resp = make_response(body)
    resp.mimetype = "text/plain"
    return resp


@app.route("/sitemap.xml")
def sitemap():
    now = datetime.utcnow().strftime("%Y-%m-%d")
    entries = [
        (f"{SITE_URL}/","1.0","weekly"),
        (f"{SITE_URL}/calculator","0.9","weekly"),
        (f"{SITE_URL}/methodology","0.7","monthly"),
        (f"{SITE_URL}/about","0.5","monthly"),
        (f"{SITE_URL}/privacy","0.3","yearly"),
        (f"{SITE_URL}/contact","0.3","yearly"),
        (f"{SITE_URL}/disclaimer","0.3","yearly"),
        (f"{SITE_URL}/dividend-tax-for-contractors","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-for-investors","0.6","monthly"),
        (f"{SITE_URL}/dividends-and-self-assessment","0.6","monthly"),
        (f"{SITE_URL}/dividends-inside-isa","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-higher-rate-taxpayer","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-basic-rate-taxpayer","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-additional-rate-taxpayer","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-and-isa","0.6","monthly"),
        (f"{SITE_URL}/dividend-personal-allowance","0.6","monthly"),
        (f"{SITE_URL}/dividend-tax-for-retirees","0.6","monthly"),
        (f"{SITE_URL}/additional-rate-dividend-tax","0.6","monthly"),
        (f"{SITE_URL}/guides","0.6","monthly"),
        (f"{SITE_URL}/calculators","0.6","monthly"),
        (f"{SITE_URL}/director-dividend-calculator","0.7","monthly"),
        (f"{SITE_URL}/dividend-after-salary-calculator","0.7","monthly"),
        (f"{SITE_URL}/investment-dividend-tax-calculator","0.7","monthly"),
        (f"{SITE_URL}/dividend-allowance-calculator","0.7","monthly"),
        (f"{SITE_URL}/blog","0.7","weekly"),
    ] + [(f"{SITE_URL}/blog/{p['slug']}","0.6","monthly") for p in BLOG_POSTS] + [
        (f"{SITE_URL}/dividend-tax/{a}","0.5","monthly") for a in DIVIDEND_AMOUNTS
    ]
    r = make_response(render_template("sitemap.xml", url_entries=entries, now=now))
    r.content_type = "application/xml"
    return r

@app.route("/")
def landing():
    calc = calculate_dividend_tax(salary_income=40000, dividend_income=10000)
    faq = [
        {"q":"What is the dividend allowance for 2026/27?","a":"The dividend allowance is £500 for 2026/27. Dividends within this amount are free from dividend tax, regardless of which tax band you are in. This £500 sits on top of your Personal Allowance."},
        {"q":"What are the dividend tax rates for 2026/27?","a":"The dividend tax rates for 2026/27 are 8.75% in the basic-rate band (income up to £50,270), 33.75% in the higher-rate band (£50,271–£125,140), and 39.35% in the additional-rate band (above £125,140)."},
        {"q":"Are dividends from ISAs taxed?","a":"No. Dividends received within a Stocks and Shares ISA are completely free from UK income tax and dividend tax. Only dividends paid outside an ISA count towards your dividend allowance and are subject to dividend tax."},
        {"q":"Why does my salary affect my dividend tax rate?","a":"Dividends are treated as the top slice of your income. Your salary and other non-dividend income fill the Personal Allowance and the basic-rate band first. Dividends then sit on top, so a higher salary pushes more dividends into higher tax bands. This is why the calculator asks for your salary."},
        {"q":"Do I need to complete a Self Assessment for dividend income?","a":"You must register for Self Assessment if your dividend income exceeds £1,000 in a tax year (or £500 if you are already required to file). HMRC cannot automatically collect dividend tax through PAYE, so you must declare it yourself."},
        {"q":"Is corporation tax separate from dividend tax?","a":"Yes. Corporation tax is paid by the company on its profits before any dividends are paid. When a dividend is then paid to a shareholder, dividend tax is calculated on the shareholder's personal income. This calculator covers only the personal dividend tax — not corporation tax on profits."},
    ]
    return render_template("landing.html", **_ctx(
        title="Dividend Tax Calculator UK 2026/27 | Estimate Tax on Dividend Income",
        meta_description="Calculate UK dividend tax for 2026/27 based on dividend income, salary and other taxable income. Estimate how much tax you may owe.",
        canonical_url=SITE_URL+"/",
        calc=calc,
        faq_items=faq,
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"}],
    ))

@app.route("/calculator")
def calculator_page():
    return render_template("calculator.html", **_ctx(
        title="Dividend Tax Calculator 2026/27 | UK Dividend Tax Breakdown",
        meta_description="Free UK dividend tax calculator for 2026/27. Enter salary and dividend income to get a full breakdown of dividend tax by band.",
        canonical_url=SITE_URL+"/calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Calculator","url":SITE_URL+"/calculator"}],
    ))

@app.route("/methodology")
def methodology():
    return render_template("methodology.html", **_ctx(
        title="Methodology — How We Calculate UK Dividend Tax 2026/27",
        meta_description="How UKDividendTaxCalculator.co.uk calculates dividend tax: 2026/27 rates, £500 allowance, band ordering and what we don't model.",
        canonical_url=SITE_URL+"/methodology",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Methodology","url":SITE_URL+"/methodology"}],
    ))

@app.route("/about")
def about():
    return render_template("about.html", **_ctx(
        title="About UK Dividend Tax Calculator — Free Dividend Tax Tool",
        meta_description="About UKDividendTaxCalculator.co.uk — a free, independent tool to estimate UK dividend tax for 2026/27.",
        canonical_url=SITE_URL+"/about",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"About","url":SITE_URL+"/about"}],
    ))

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", **_ctx(
        title="Privacy Policy — UKDividendTaxCalculator.co.uk",
        meta_description="Privacy policy for UKDividendTaxCalculator.co.uk. We don't store your financial data.",
        canonical_url=SITE_URL+"/privacy",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Privacy","url":SITE_URL+"/privacy"}],
    ))

@app.route("/contact")
def contact():
    return render_template("contact.html", **_ctx(
        title="Contact — UKDividendTaxCalculator.co.uk",
        meta_description="Get in touch with UKDividendTaxCalculator.co.uk.",
        canonical_url=SITE_URL+"/contact",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Contact","url":SITE_URL+"/contact"}],
    ))

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html", **_ctx(
        title="Disclaimer — UKDividendTaxCalculator.co.uk",
        meta_description="Disclaimer for UKDividendTaxCalculator.co.uk. Results are estimates only.",
        canonical_url=SITE_URL+"/disclaimer",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Disclaimer","url":SITE_URL+"/disclaimer"}],
    ))

@app.route("/dividend-tax-for-contractors")
def guide_contractors():
    return render_template("dividend-tax-for-contractors.html", **_ctx(
        title="Dividend Tax for Contractors 2026/27 | UK Guide",
        meta_description="A practical guide to UK dividend tax for contractors and company owners, including salary, dividends and 2026/27 dividend rates.",
        canonical_url=SITE_URL+"/dividend-tax-for-contractors",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Contractors","url":SITE_URL+"/dividend-tax-for-contractors"}],
    ))

@app.route("/dividend-tax-for-investors")
def guide_investors():
    return render_template("dividend-tax-for-investors.html", **_ctx(
        title="Dividend Tax for Investors 2026/27 | UK Guide",
        meta_description="Understand how dividend tax applies to investors holding shares or funds outside ISAs and pensions, with 2026/27 rates and examples.",
        canonical_url=SITE_URL+"/dividend-tax-for-investors",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Investors","url":SITE_URL+"/dividend-tax-for-investors"}],
    ))

@app.route("/dividends-and-self-assessment")
def guide_self_assessment():
    return render_template("dividends-and-self-assessment.html", **_ctx(
        title="Dividends and Self Assessment 2026/27 | UK Guide",
        meta_description="Learn when dividend income may need to be reported through Self Assessment and how dividend tax is estimated.",
        canonical_url=SITE_URL+"/dividends-and-self-assessment",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividends and Self Assessment","url":SITE_URL+"/dividends-and-self-assessment"}],
    ))

@app.route("/dividends-inside-isa")
def guide_isa():
    return render_template("dividends-inside-isa.html", **_ctx(
        title="Are Dividends Inside an ISA Taxed? | UK Guide 2026/27",
        meta_description="Dividends inside ISAs are not taxed. Learn how ISA dividends differ from taxable dividends outside an ISA.",
        canonical_url=SITE_URL+"/dividends-inside-isa",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividends Inside an ISA","url":SITE_URL+"/dividends-inside-isa"}],
    ))

@app.route("/dividend-tax-higher-rate-taxpayer")
def guide_higher_rate():
    return render_template("dividend-tax-higher-rate-taxpayer.html", **_ctx(
        title="Dividend Tax for Higher-Rate Taxpayers 2026/27",
        meta_description="Learn how dividend tax works for higher-rate taxpayers in 2026/27, including the £500 dividend allowance and 33.75% rate.",
        canonical_url=SITE_URL+"/dividend-tax-higher-rate-taxpayer",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Higher-Rate Taxpayers","url":SITE_URL+"/dividend-tax-higher-rate-taxpayer"}],
    ))

@app.route("/dividend-tax-basic-rate-taxpayer")
def guide_basic_rate():
    return render_template("dividend-tax-basic-rate-taxpayer.html", **_ctx(
        title="Dividend Tax for Basic-Rate Taxpayers 2026/27 | UK Guide",
        meta_description="Basic-rate taxpayers pay 8.75% on dividends above the £500 allowance. Learn how the Personal Allowance and dividend allowance interact in 2026/27.",
        canonical_url=SITE_URL+"/dividend-tax-basic-rate-taxpayer",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Basic-Rate Taxpayers","url":SITE_URL+"/dividend-tax-basic-rate-taxpayer"}],
    ))

@app.route("/dividend-tax-additional-rate-taxpayer")
def guide_additional_rate():
    return render_template("dividend-tax-additional-rate-taxpayer.html", **_ctx(
        title="Dividend Tax for Additional-Rate Taxpayers 2026/27 | UK Guide",
        meta_description="Additional-rate taxpayers pay 39.35% on dividends above £500. Learn the £125,140 threshold, worked examples and 2026/27 rates.",
        canonical_url=SITE_URL+"/dividend-tax-additional-rate-taxpayer",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Additional-Rate Taxpayers","url":SITE_URL+"/dividend-tax-additional-rate-taxpayer"}],
    ))

@app.route("/dividend-tax-and-isa")
def guide_isa_tax():
    return render_template("dividend-tax-and-isa.html", **_ctx(
        title="Dividends Inside an ISA: No Tax 2026/27 | UK Guide",
        meta_description="Dividends inside a Stocks and Shares ISA are completely exempt from UK income tax. Learn how ISA dividends work and the £20,000 allowance for 2026/27.",
        canonical_url=SITE_URL+"/dividend-tax-and-isa",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax and ISA","url":SITE_URL+"/dividend-tax-and-isa"}],
    ))

@app.route("/dividend-personal-allowance")
def guide_personal_allowance():
    return render_template("dividend-personal-allowance.html", **_ctx(
        title="Dividends and the Personal Allowance 2026/27 | UK Guide",
        meta_description="The Personal Allowance (£12,570) can shelter dividend income if your salary doesn't use it all. Learn how dividends and the Personal Allowance interact in 2026/27.",
        canonical_url=SITE_URL+"/dividend-personal-allowance",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividends and the Personal Allowance","url":SITE_URL+"/dividend-personal-allowance"}],
    ))

@app.route("/dividend-tax-for-retirees")
def guide_retirees():
    return render_template("dividend-tax-for-retirees.html", **_ctx(
        title="Dividend Tax for Retirees 2026/27 | UK Guide",
        meta_description="Retirees can have very tax-efficient dividend income. Learn how the state pension, Personal Allowance and dividend allowance combine in 2026/27.",
        canonical_url=SITE_URL+"/dividend-tax-for-retirees",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax for Retirees","url":SITE_URL+"/dividend-tax-for-retirees"}],
    ))

@app.route("/additional-rate-dividend-tax")
def guide_additional_rate_new():
    return render_template("additional-rate-dividend-tax.html", **_ctx(
        title="Additional-Rate Dividend Tax 2026/27 | UK Guide",
        meta_description="For 2026/27, dividends in the additional-rate band are taxed at 39.35% after the £500 dividend allowance. Guide with worked example for income above £125,140.",
        canonical_url=SITE_URL+"/additional-rate-dividend-tax",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Additional-Rate Dividend Tax","url":SITE_URL+"/additional-rate-dividend-tax"}],
    ))

@app.route("/guides")
def guides_index():
    return render_template("guides.html", **_ctx(
        title="Dividend Tax Guides 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="In-depth UK dividend tax guides for contractors, investors, directors and retirees.",
        canonical_url=SITE_URL + "/guides",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Guides","url":SITE_URL+"/guides"}],
    ))

@app.route("/calculators")
def calculators_index():
    return render_template("calculators.html", **_ctx(
        title="Dividend Tax Calculators 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="Free UK dividend tax calculators for directors, investors and basic/higher rate taxpayers.",
        canonical_url=SITE_URL + "/calculators",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Calculators","url":SITE_URL+"/calculators"}],
    ))

@app.route("/director-dividend-calculator")
def director_dividend_calculator():
    return render_template("director-dividend-calculator.html", **_ctx(
        title="Director Dividend Calculator 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="Estimate personal dividend tax for a company director taking salary and dividends in 2026/27.",
        canonical_url=SITE_URL + "/director-dividend-calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Director Dividend Calculator","url":SITE_URL+"/director-dividend-calculator"}],
    ))

@app.route("/dividend-after-salary-calculator")
def dividend_after_salary_calculator():
    return render_template("dividend-after-salary-calculator.html", **_ctx(
        title="Dividend Tax After Salary Calculator 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="See how your salary uses tax bands before dividends are assessed for 2026/27.",
        canonical_url=SITE_URL + "/dividend-after-salary-calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend After Salary Calculator","url":SITE_URL+"/dividend-after-salary-calculator"}],
    ))

@app.route("/investment-dividend-tax-calculator")
def investment_dividend_tax_calculator():
    return render_template("investment-dividend-tax-calculator.html", **_ctx(
        title="Investment Dividend Tax Calculator 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="Estimate tax on investment dividends outside ISAs and pensions for 2026/27.",
        canonical_url=SITE_URL + "/investment-dividend-tax-calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Investment Dividend Tax Calculator","url":SITE_URL+"/investment-dividend-tax-calculator"}],
    ))

@app.route("/dividend-allowance-calculator")
def dividend_allowance_calculator():
    return render_template("dividend-allowance-calculator.html", **_ctx(
        title="Dividend Allowance Calculator 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="See how the £500 dividend allowance applies after your salary and other income in 2026/27.",
        canonical_url=SITE_URL + "/dividend-allowance-calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Allowance Calculator","url":SITE_URL+"/dividend-allowance-calculator"}],
    ))

DIVIDEND_AMOUNTS = [1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000]

@app.route("/dividend-tax/<int:amount>")
def dividend_amount_page(amount: int):
    if amount not in DIVIDEND_AMOUNTS:
        abort(404)
    # Basic-rate scenario: £30,000 salary
    calc_basic = calculate_dividend_tax(salary_income=30000, dividend_income=amount)
    # Higher-rate scenario: £55,000 salary
    calc_higher = calculate_dividend_tax(salary_income=55000, dividend_income=amount)
    all_amounts = DIVIDEND_AMOUNTS
    return render_template("dividend_amount_page.html", **_ctx(
        title=f"Dividend Tax on £{amount:,} Dividends 2026/27 | UK Calculator",
        meta_description=f"How much dividend tax on £{amount:,} dividends in 2026/27? After the £500 allowance, a basic-rate taxpayer (£30k salary) pays £{calc_basic.total_dividend_tax:,.0f} and a higher-rate taxpayer (£55k salary) pays £{calc_higher.total_dividend_tax:,.0f}.",
        canonical_url=SITE_URL+f"/dividend-tax/{amount}",
        amount=amount,
        calc_basic=calc_basic,
        calc_higher=calc_higher,
        all_amounts=all_amounts,
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":f"Dividend tax on £{amount:,}","url":SITE_URL+f"/dividend-tax/{amount}"}],
    ))


BLOG_POSTS = [
    {
        "slug": "dividend-tax-in-scotland",
        "title": "Dividend Tax in Scotland 2026/27: How Scottish Income Tax Affects Your Bill",
        "description": "Scottish taxpayers pay different income tax rates on salary, but dividend tax rates are set by Westminster. Here is how the interaction works in practice.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "Scotland Sets Its Own Income Tax Rates — But Not Dividend Tax Rates",
                "paragraphs": [
                    "Scotland has had the power to set its own income tax rates and bands since 2017. For 2026/27, Scottish taxpayers face five main bands: starter (19%), basic (20%), intermediate (21%), higher (42%) and top (48%). The Personal Allowance of £12,570 still applies across the UK. This means a Scottish salary earner pays more income tax than an equivalent earner in England, Wales or Northern Ireland at many income levels.",
                    "What Scotland cannot change is dividend tax. The rates of 8.75%, 33.75% and 39.35% are reserved UK-wide taxes set by the UK Parliament. This creates an unusual split: your salary is taxed under Scottish rates while your dividends are taxed under rUK rates. Calculating the combined position requires understanding both systems.",
                ],
            },
            {
                "heading": "How Bands Interact: Salary Fills Scottish Bands, Dividends Fill UK Bands",
                "paragraphs": [
                    "For the purpose of working out which dividend tax rate applies, HMRC uses the UK-wide band thresholds, not the Scottish ones. The basic-rate limit for UK dividend purposes is £50,270. Your salary and other non-dividend income are assessed against Scottish thresholds for income tax, but the residual basic-rate band available for dividends is calculated against the UK threshold of £50,270.",
                    "Consider a Scottish director with a £43,000 salary and £10,000 dividends. Their salary falls within the Scottish higher-rate band (above £43,662 in 2026/27). For income tax on salary, they pay Scottish higher rate (42%) on the top slice of salary. However, for dividend tax purposes, their salary of £43,000 leaves £7,270 of the UK basic-rate band (£50,270 − £43,000) still available. Dividends up to £500 are covered by the dividend allowance, then the next £6,770 is taxed at 8.75%, and anything above that at 33.75%.",
                    "This interaction means a Scottish higher-rate taxpayer may still pay basic-rate dividend tax (8.75%) on a portion of dividends, because the relevant threshold for dividends is the UK-wide £50,270, not the lower Scottish higher-rate threshold of £43,662. This is genuinely different from the income tax position and catches many Scottish directors by surprise.",
                ],
            },
            {
                "heading": "The Dividend Allowance: Same for All UK Taxpayers",
                "paragraphs": [
                    "The £500 dividend allowance applies identically to Scottish taxpayers as to everyone else in the UK. The first £500 of dividend income each year is free from dividend tax, regardless of which income tax band the taxpayer falls into. This allowance has been at £500 since April 2024, reduced from £1,000 the year before and from £2,000 before that.",
                    "Scottish taxpayers should also note that the Personal Allowance (£12,570) behaves the same way as elsewhere. Dividend income can benefit from the Personal Allowance if salary income has not fully used it. A Scottish retiree with a small pension and dividend income may pay no dividend tax at all if total income stays below £12,570.",
                ],
            },
            {
                "heading": "Planning Implications for Scottish Directors",
                "paragraphs": [
                    "Because Scottish income tax rates on salary are higher, the optimal salary level for a Scottish director is often lower than for a director elsewhere in the UK. The point at which paying additional salary becomes more expensive than dividends is reached sooner. For 2026/27, many Scottish directors use a salary around the National Insurance secondary threshold (approximately £5,000) or up to the primary threshold level, then draw dividends for the remainder.",
                    "Scottish taxpayers who are higher-rate payers on salary should model the full picture: Scottish income tax on salary at 42%, employer NI potentially saving corporation tax, and then dividend tax at the relevant UK rate. The calculator on this site allows you to enter any salary and dividend combination to see the personal tax result using the correct rUK dividend tax rates.",
                ],
            },
        ],
        "faqs": [
            {"q": "Do Scottish taxpayers pay higher dividend tax?", "a": "No. Dividend tax rates are set by the UK Parliament and apply identically across England, Scotland, Wales and Northern Ireland. The rates for 2026/27 are 8.75%, 33.75% and 39.35%."},
            {"q": "Which band threshold applies for dividend tax in Scotland?", "a": "The UK-wide basic-rate limit of £50,270 applies for dividend tax purposes, not the Scottish higher-rate threshold. So Scottish taxpayers can still have dividends taxed at 8.75% even if their salary is already in the Scottish higher-rate band."},
            {"q": "Does the dividend allowance apply in Scotland?", "a": "Yes. The £500 dividend allowance applies to all UK taxpayers including Scottish taxpayers."},
        ],
    },
    {
        "slug": "dividend-tax-wales-2026",
        "title": "Dividend Tax in Wales 2026/27: What Welsh Taxpayers Need to Know",
        "description": "Wales uses the same income tax rates as England and Northern Ireland for 2026/27. This guide explains how dividend tax works for Welsh taxpayers and what the Welsh Rate of Income Tax means in practice.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "5 min read",
        "sections": [
            {
                "heading": "The Welsh Rate of Income Tax",
                "paragraphs": [
                    "Since April 2019, Welsh taxpayers have been subject to the Welsh Rate of Income Tax (WRIT). The UK Government reduced the basic, higher and additional rates each by 10 pence and the Welsh Government then set its own Welsh rates. For every year since 2019, the Welsh Government has set its rates to match the rUK (England and Northern Ireland) rates exactly. For 2026/27, this means Welsh taxpayers pay 20%, 40% and 45% — the same as in England and Northern Ireland.",
                    "In practice, Welsh taxpayers' income tax bills are identical to those of English taxpayers at the same income level. The Welsh rate mechanism means that, unlike Scotland, there is no divergence in take-home pay for salary earners in Wales compared to England. This makes tax planning for Welsh directors and investors straightforward: the same rules and examples that apply in England apply equally in Wales.",
                ],
            },
            {
                "heading": "Dividend Tax for Welsh Taxpayers",
                "paragraphs": [
                    "Because Wales uses the same income tax rates as rUK, dividend tax works identically for Welsh taxpayers. The £500 dividend allowance, the 8.75% basic-rate tax on dividends, the 33.75% higher-rate tax and the 39.35% additional-rate tax all apply exactly as they do in England. The band thresholds are the same: basic rate up to £50,270, higher rate up to £125,140, and additional rate above that.",
                    "Welsh company directors taking salary and dividends should use exactly the same planning frameworks as English directors. The optimal salary and dividend split, the interaction with the Personal Allowance (£12,570) and the dividend allowance (£500) work identically. Tools on this site give accurate results for Welsh taxpayers without any adjustments.",
                ],
            },
            {
                "heading": "ISAs and Other Tax-Efficient Wrappers in Wales",
                "paragraphs": [
                    "ISA rules are UK-wide and apply equally in Wales. The annual ISA allowance for 2026/27 is £20,000. Dividends received inside a Stocks and Shares ISA are completely exempt from dividend tax. Welsh investors can use ISAs in exactly the same way as investors elsewhere in the UK.",
                    "Pension contributions also work identically. A Welsh taxpayer making a pension contribution gets basic-rate tax relief at source (20%) and can claim higher-rate relief through Self Assessment in the same way as an English taxpayer. Welsh investors looking to shelter dividend income should prioritise filling their ISA allowance and consider pension contributions as a way of bringing income below the higher-rate threshold.",
                ],
            },
            {
                "heading": "Self Assessment for Welsh Dividend Income",
                "paragraphs": [
                    "Welsh taxpayers with dividend income above £1,000 in a tax year must register for Self Assessment. This threshold is the same as for England. HMRC cannot collect dividend tax through PAYE, so Welsh employees and directors who receive dividends above the allowance must file a return and pay any tax due by 31 January following the end of the tax year.",
                    "Welsh taxpayers filing Self Assessment will see their tax code and tax calculation reflect the Welsh income tax rates. However, since those rates currently match England, the practical result is the same. HMRC's systems identify Welsh taxpayers by postcode and apply the correct rates automatically.",
                ],
            },
        ],
        "faqs": [
            {"q": "Do Welsh taxpayers pay different dividend tax?", "a": "No. Dividend tax rates are set by the UK Parliament and are identical across all four nations. Welsh income tax rates on salary also match England for 2026/27."},
            {"q": "Can Welsh taxpayers use the same dividend tax calculator?", "a": "Yes. Because Wales uses the same income tax rates as England, our dividend tax calculator gives accurate results for Welsh taxpayers without any adjustment."},
            {"q": "What is the Welsh Rate of Income Tax?", "a": "The Welsh Rate of Income Tax is a mechanism allowing the Welsh Government to vary income tax rates in Wales. Since 2019 it has been set to match England and Northern Ireland, so Welsh taxpayers pay the same rates."},
        ],
    },
    {
        "slug": "how-much-dividend-tax-on-50000",
        "title": "How Much Dividend Tax on £50,000 Dividends? (2026/27 Worked Examples)",
        "description": "A detailed worked example showing dividend tax on £50,000 of dividends with no other income versus £30,000 salary, using 2026/27 rates.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "The Key Variable: Your Other Income",
                "paragraphs": [
                    "The amount of dividend tax you pay on £50,000 of dividends depends almost entirely on how much other income you have in the same tax year. Dividends are always treated as the top slice of income. Your salary, pension income and other non-dividend income fill the Personal Allowance and the basic-rate band first. Only then are dividends assessed, and the rate applied depends on which band they land in.",
                    "For 2026/27, the key thresholds are: Personal Allowance £12,570, basic-rate limit £50,270 and higher-rate limit £125,140. The dividend allowance is £500. The dividend tax rates are 8.75% (basic), 33.75% (higher) and 39.35% (additional).",
                ],
            },
            {
                "heading": "Scenario 1: £50,000 Dividends, No Salary",
                "paragraphs": [
                    "If your only income is £50,000 of dividends and you have no salary or other taxable income, the calculation works as follows. The Personal Allowance of £12,570 shelters the first £12,570 of dividends from all tax. The next £500 is covered by the dividend allowance (free). That leaves £36,930 of dividends to be taxed.",
                    "The basic-rate band runs from £12,570 to £50,270, a range of £37,700. After the Personal Allowance and dividend allowance have been used (£12,570 + £500 = £13,070), the remaining basic-rate band available is £50,270 − £13,070 = £37,200. All £36,930 of remaining dividends falls within this band. Dividend tax at 8.75% on £36,930 = £3,231. Total dividend tax bill: approximately £3,231.",
                    "This is a relatively modest tax bill on £50,000 of income. The combination of the Personal Allowance and the 8.75% basic rate makes dividend income highly tax-efficient for investors with no other income, such as retirees drawing from a share portfolio.",
                ],
            },
            {
                "heading": "Scenario 2: £50,000 Dividends on Top of £30,000 Salary",
                "paragraphs": [
                    "Now suppose you also have a £30,000 salary. Your salary uses the Personal Allowance first. After the Personal Allowance of £12,570, the salary leaves £17,430 of taxable salary. Income tax on salary: 20% on £17,430 = £3,486 (plus National Insurance, not shown here as this is a dividend tax calculation).",
                    "For dividend tax, the salary (£30,000) has already filled the basic-rate band up to £30,000. The remaining basic-rate band for dividends is £50,270 − £30,000 = £20,270. The first £500 of dividends is covered by the allowance. That leaves £49,500 of taxable dividends. The first £20,270 is charged at 8.75% = £1,774. The remaining £29,230 falls into the higher-rate band and is charged at 33.75% = £9,865. Total dividend tax: approximately £11,639.",
                    "The difference is stark: no salary gives £3,231 of dividend tax, while £30,000 of salary alongside the same dividends generates £11,639. This illustrates why salary level is so important in dividend tax planning, and why directors typically try to keep total income below £50,270 where possible.",
                ],
            },
            {
                "heading": "How to Reduce the Bill",
                "paragraphs": [
                    "For the higher-salary scenario, strategies include: maximising ISA contributions (up to £20,000 per year, sheltering those dividends entirely), making pension contributions to reduce taxable income, and transferring dividend-producing assets to a spouse or civil partner who has lower income or unused allowances.",
                    "For retirees in Scenario 1, the position is already quite efficient. Those with income above £100,000 face a different challenge: the Personal Allowance is gradually withdrawn above £100,000, and a director with £50,000 of dividends on top of £100,000+ income will face additional-rate taxes of 39.35% on the top portion.",
                ],
            },
        ],
        "faqs": [
            {"q": "How much dividend tax on £50,000 with no other income?", "a": "For 2026/27, approximately £3,231. The Personal Allowance (£12,570) and dividend allowance (£500) shelter the first £13,070. The remaining £36,930 is taxed at 8.75% basic rate."},
            {"q": "How much dividend tax on £50,000 dividends with a £30,000 salary?", "a": "For 2026/27, approximately £11,639. The salary uses up basic-rate band, pushing much of the dividends into the 33.75% higher-rate band."},
            {"q": "Can I reduce my dividend tax by using an ISA?", "a": "Yes. Dividends inside a Stocks and Shares ISA are completely exempt from dividend tax. The annual ISA allowance is £20,000 per person for 2026/27."},
        ],
    },
    {
        "slug": "dividend-tax-planning-2026",
        "title": "Dividend Tax Planning for 2026/27: Strategies to Reduce Your Bill",
        "description": "Practical strategies to reduce UK dividend tax in 2026/27, including ISA use, pension contributions, the dividend allowance and basic-rate band management.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "8 min read",
        "sections": [
            {
                "heading": "Why Dividend Tax Planning Matters",
                "paragraphs": [
                    "The combination of a reduced dividend allowance (now just £500), rates of up to 39.35% and the interaction with income tax bands means dividend tax can be a significant cost for company directors and investors. Unlike PAYE, dividend tax is not withheld automatically — it must be declared through Self Assessment and paid by 31 January. This gives taxpayers an opportunity to plan ahead and use available reliefs before the tax year ends on 5 April.",
                    "The most effective planning actions are structural: changing where assets are held, how income is split between family members, and how the basic-rate band is used. One-off actions like topping up ISAs before the year-end deadline can also make a meaningful difference.",
                ],
            },
            {
                "heading": "Strategy 1: Fill Your ISA Allowance First",
                "paragraphs": [
                    "Dividends received inside a Stocks and Shares ISA are entirely exempt from dividend tax, and the gains are also free from capital gains tax. The annual ISA allowance is £20,000 per person for 2026/27. For a higher-rate taxpayer, sheltering £20,000 of dividend-producing investments inside an ISA saves up to £6,750 per year in dividend tax (33.75% on £20,000) compared to holding the same investment outside an ISA.",
                    "The ISA allowance is use-it-or-lose-it: any unused allowance at 5 April disappears permanently. If you are a director with significant personal investments, the priority should be to move dividend-producing holdings into an ISA as quickly as your allowance permits. Transfers from unwrapped accounts to ISAs may trigger capital gains on exit, so model the full picture before acting.",
                ],
            },
            {
                "heading": "Strategy 2: Use Pension Contributions to Reduce Income",
                "paragraphs": [
                    "Pension contributions reduce your adjusted net income. If you are close to the basic-rate/higher-rate boundary of £50,270, a pension contribution can bring your total income back below the threshold, turning higher-rate dividend tax (33.75%) into basic-rate dividend tax (8.75%). The saving is 25 percentage points on every pound of dividends that moves from higher rate to basic rate.",
                    "For company directors, employer pension contributions paid by the company reduce corporation tax and do not count as personal income, making them even more efficient. A director whose salary plus dividends totals £55,000 might make a £5,000 employer pension contribution, bringing their effective total income to £50,000 and ensuring all dividends fall within the basic-rate band. Always check the annual allowance (£60,000 for 2026/27) and tapered annual allowance rules before making large contributions.",
                ],
            },
            {
                "heading": "Strategy 3: Maximise the Dividend Allowance for Each Family Member",
                "paragraphs": [
                    "Every UK individual has a £500 dividend allowance. Spouses, civil partners and adult children who own shares independently each have their own allowance. A couple can therefore receive up to £1,000 of dividends free from dividend tax each year. If one spouse is a basic-rate taxpayer and the other a non-taxpayer, transferring dividend-producing shares can shift the tax rate on those dividends from 33.75% to 0% or 8.75%.",
                    "Gifts of assets between spouses are made at no-gain/no-loss for capital gains tax purposes, so there is usually no CGT cost in transferring shares between spouses. The shares then generate dividends in the lower-earning spouse's name and are taxed at their marginal rate. This strategy is well-established and wholly legal, but the transfer must be a genuine gift — HMRC will scrutinise arrangements that appear artificial.",
                ],
            },
            {
                "heading": "Strategy 4: Manage the Basic-Rate Band Carefully",
                "paragraphs": [
                    "For directors, the salary/dividend split is the most powerful lever. Keeping salary low means more of the basic-rate band is available for dividends to be taxed at 8.75% rather than 33.75%. For 2026/27, a common approach is a salary at the National Insurance secondary threshold (around £5,000) which still qualifies as an expense for the company and triggers no employer or employee NI. Dividends can then fill the basic-rate band up to £50,270 total income at 8.75%.",
                    "A director with a £5,000 salary can pay out approximately £45,270 in dividends (after the £500 allowance) before any dividend tax is due at 33.75%. Basic-rate dividend tax of 8.75% applies on dividends above the allowance within the band. Total personal tax is significantly lower than if the same amount had been paid as salary through PAYE.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the most effective way to reduce dividend tax?", "a": "Using a Stocks and Shares ISA is usually the most impactful, as dividends inside an ISA are completely exempt. After that, pension contributions to stay below the higher-rate threshold and asset-sharing between spouses are highly effective."},
            {"q": "Can I carry forward unused dividend allowance?", "a": "No. The £500 dividend allowance cannot be carried forward to future tax years. It must be used in the current tax year or it is lost."},
            {"q": "What is the optimal salary for a company director in 2026/27?", "a": "The most common approach is a salary at approximately £5,000 (near the employer NI secondary threshold), with remaining income taken as dividends. This minimises NI costs while still qualifying as a deductible expense for the company."},
        ],
    },
    {
        "slug": "dividend-allowance-history",
        "title": "The History of the UK Dividend Allowance: From £5,000 to £500",
        "description": "How the UK dividend allowance has changed from £5,000 in 2016/17 to £500 in 2024/25 onwards, and what each cut meant for investors and directors.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "Introduction of the Dividend Allowance in 2016",
                "paragraphs": [
                    "The dividend allowance was introduced by the then Chancellor George Osborne in the April 2016 tax reform. Before this, dividends came with a notional 10% tax credit, meaning basic-rate taxpayers paid no additional tax and higher-rate taxpayers paid less than the headline rate. The 2016 reform scrapped the tax credit and replaced it with a new £5,000 tax-free dividend allowance. Basic-rate dividend tax was set at 7.5%, higher rate at 32.5% and additional rate at 38.1%.",
                    "For many small investors and directors with modest dividend income, the £5,000 allowance meant no dividend tax was payable at all. A director taking £5,000 in dividends from their company paid zero dividend tax, making the allowance highly valuable for the self-employed company owner community.",
                ],
            },
            {
                "heading": "Cut to £2,000 in April 2018",
                "paragraphs": [
                    "The first reduction came in April 2018 when the allowance was cut from £5,000 to £2,000. This change affected a large number of investors and small business owners who had previously relied on the full £5,000 to stay below the tax threshold. For a higher-rate taxpayer, the cut from £5,000 to £2,000 added approximately £975 to their annual dividend tax bill (32.5% on the £3,000 reduction). For additional-rate taxpayers, the hit was around £1,143 (38.1% on £3,000).",
                    "The government framed the cut as addressing a perceived unfairness between employed and self-employed individuals and between salary and dividend income. The argument was that the £5,000 allowance had been too generous relative to the employer NI advantage directors already enjoyed. The reduction to £2,000 was a first step in narrowing those structural advantages.",
                ],
            },
            {
                "heading": "Cut to £1,000 in April 2023",
                "paragraphs": [
                    "The April 2023 reduction to £1,000 was announced by Chancellor Jeremy Hunt as part of the Autumn Statement 2022. At the same time, the dividend tax rates themselves were increased by 1.25 percentage points in April 2022 (a temporary Health and Social Care Levy surcharge), taking basic-rate dividend tax to 8.75%, higher rate to 33.75% and additional rate to 39.35%. Although the 1.25% surcharge was reversed for income tax and NI in November 2022, the higher dividend tax rates were retained permanently.",
                    "The combined effect of higher rates and a lower allowance was significant. A higher-rate taxpayer who had previously paid no dividend tax on £2,000 of dividends now paid 33.75% on £1,000 above the new £1,000 allowance: an annual cost of £337.50. Meanwhile, the 1.25% rate increase added to bills across all dividend income above the allowance.",
                ],
            },
            {
                "heading": "Cut to £500 in April 2024",
                "paragraphs": [
                    "The most recent reduction, to £500, took effect from 6 April 2024. This was also announced by Jeremy Hunt and completed a sequence of four cuts over eight years. The £500 allowance represents a 90% reduction from the original £5,000 in 2016. For a higher-rate taxpayer with £5,000 of dividends, the annual dividend tax bill has risen from approximately £0 in 2016 to approximately £1,519 in 2026/27 (33.75% on £4,500 above the allowance).",
                    "The current £500 allowance is expected to remain at this level for the foreseeable future, though it can of course be changed by future governments. There is no indexing to inflation, so in real terms the allowance will erode further over time unless explicitly increased. Directors and investors should plan on the basis of the current £500 figure.",
                ],
            },
            {
                "heading": "What the Cuts Mean for Planning Today",
                "paragraphs": [
                    "With only £500 of dividend income tax-free, the case for using ISAs and pensions to shelter dividend income has never been stronger. The ISA allowance of £20,000 per year, if fully used in a Stocks and Shares ISA, protects all dividends from the small-company share portfolio of most individual investors. Directors who relied on the generous early allowances need to reassess their salary/dividend mix and consider whether other structures (such as pension contributions) can restore some of the lost efficiency.",
                    "The trajectory of the allowance also serves as a reminder that tax reliefs can be reduced or removed. Long-term planning should not rely heavily on a single allowance remaining at its current level — diversifying across ISAs, pensions and other wrappers gives resilience against future changes.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the dividend allowance for 2026/27?", "a": "The dividend allowance is £500 for 2026/27. It has been at this level since April 2024."},
            {"q": "When was the dividend allowance £5,000?", "a": "The dividend allowance was £5,000 from April 2016 (when it was introduced) until April 2018, when it was cut to £2,000."},
            {"q": "Has the dividend allowance been reduced?", "a": "Yes. The allowance has been cut four times: introduced at £5,000 in 2016, cut to £2,000 in 2018, cut to £1,000 in 2023, and cut to £500 in 2024."},
        ],
    },
    {
        "slug": "director-salary-dividend-mix-2026",
        "title": "Optimal Director Salary and Dividend Mix for 2026/27",
        "description": "How company directors can minimise combined corporation tax and personal tax in 2026/27 by choosing the right salary and dividend split.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "9 min read",
        "sections": [
            {
                "heading": "Why the Salary/Dividend Mix Matters",
                "paragraphs": [
                    "Company directors who are also shareholders have flexibility in how they extract income from their company: salary, dividends, or a combination. Each method has a different tax treatment. Salary is subject to income tax under PAYE and National Insurance contributions (both employee and employer). Dividends are paid from post-corporation-tax profits and are subject to dividend tax at lower rates. Choosing the right mix can make a material difference to total tax paid.",
                    "There is no universally optimal split — the answer depends on the company's profit level, whether the director is a sole shareholder or shares ownership, whether there are other directors, the company's corporation tax rate and the director's other personal income. However, the principles are consistent and the key thresholds for 2026/27 are well-established.",
                ],
            },
            {
                "heading": "The Corporation Tax Angle",
                "paragraphs": [
                    "Corporation tax for 2026/27 is 25% on profits above £250,000 and 19% on profits up to £50,000, with marginal relief between. Salary is deductible as a business expense, reducing the profit on which corporation tax is charged. A £1 of salary saves 25p of corporation tax (at the main rate). Dividends are paid from post-tax profits and therefore have no corporation tax deduction.",
                    "This means salary is not purely a cost — it reduces the company's corporation tax bill. A £10,000 salary paid to a director (with no employer NI if kept below the secondary threshold of around £5,000, or with employer NI above) saves the company £2,500 in corporation tax at the main rate. The net cost to the company is £10,000 minus £2,500 = £7,500. The director then pays income tax and NI on the salary personally. For very low salary levels, the personal tax is also very low or zero.",
                ],
            },
            {
                "heading": "Common Salary Strategies for 2026/27",
                "paragraphs": [
                    "Three salary levels are commonly discussed for 2026/27. First, £5,000 approximately (the employer NI secondary threshold). At this level, the company pays no employer NI and the director pays no employee NI and no income tax (salary is well below the Personal Allowance of £12,570). The salary is still deductible for corporation tax. This level makes sense for directors who are not concerned about State Pension credit accrual.",
                    "Second, £12,570 (the Personal Allowance). Paying salary up to the Personal Allowance means no income tax for the director. However, employer NI is payable on salary above the secondary threshold (around £5,000), typically at 13.8%. The employer NI is itself deductible for corporation tax. Whether this level beats the £5,000 strategy depends on the corporation tax rate and whether the employer NI cost is worthwhile for the State Pension credit.",
                    "Third, the primary NI threshold for employees (also approximately £12,570 for 2026/27). Above this level, the director starts paying employee NI at 8%. Taking salary above the primary threshold is rarely efficient unless the director values State Pension credits or needs evidence of PAYE income for a mortgage. Most single-director limited companies opt for a salary of £12,570 or just above if the employer NI cost is acceptable.",
                ],
            },
            {
                "heading": "The Dividend Top-Up",
                "paragraphs": [
                    "After setting salary, the remaining income requirement is met with dividends from post-tax company profits. The director pays dividend tax at 8.75% on dividends within the basic-rate band (up to total income of £50,270), 33.75% in the higher-rate band (£50,271 to £125,140) and 39.35% in the additional-rate band (above £125,140). The first £500 of dividends each year is free from dividend tax.",
                    "For a director with a £12,570 salary and total income needs of £50,000, approximately £37,430 of dividends are needed. After the £500 allowance, dividend tax of 8.75% applies to £36,930 = approximately £3,231. Combined with zero income tax on salary (covered by the Personal Allowance) and any NI, this represents the personal tax on £50,000 of total income for this director. The company has also paid corporation tax on the profits before distribution, so the full picture includes company-level tax too.",
                ],
            },
            {
                "heading": "A Worked Comparison: £50,000 Profit",
                "paragraphs": [
                    "Consider a single-director company with £50,000 of pre-tax profit. The director needs £40,000 of personal income. Option A: take all as salary. Salary of £40,000, employer NI on the element above £5,000, income tax and employee NI for the director. No corporation tax on the £40,000 deductible salary. Option B: salary of £12,570 (primary threshold) plus dividends. The company deducts the salary, pays corporation tax on remaining profits, then pays a dividend.",
                    "For Option B: £12,570 salary means the company has corporation tax on approximately £37,430 of profit (£50,000 minus £12,570 salary). Corporation tax at the small company rate of 19% = approximately £7,111. Post-tax profit: £30,319. Dividend of £27,430 declared (£40,000 total income minus £12,570 salary). Dividend tax: £500 allowance free, then 8.75% on £26,930 = £2,356. Total tax for director (income tax: nil, NI: approximately £65 employee NI on salary above primary threshold, dividend tax: £2,356) plus £7,111 corporation tax = approximately £9,532 combined. Option A would typically produce a higher combined bill once employer NI, employee NI and income tax at 20%/40% are all accounted for.",
                ],
            },
        ],
        "faqs": [
            {"q": "What salary should a company director take in 2026/27?", "a": "Most directors take a salary at or around £12,570 (the Personal Allowance) to avoid income tax, with employer NI being a consideration. Some prefer £5,000 (below the employer NI threshold) to eliminate NI entirely at the cost of a smaller salary deduction for corporation tax."},
            {"q": "Are dividends more tax-efficient than salary for a director?", "a": "Often yes, but it depends on the company's tax position and the director's income level. Dividends avoid NI entirely but are paid from post-corporation-tax profits. The optimal mix depends on modelling the full picture including both personal and company-level taxes."},
            {"q": "Can a director take all their income as dividends?", "a": "Legally yes, but a salary of at least £6,396 per year is needed to qualify for the State Pension credit for that year. A very low or zero salary also means the director may not have an employment record that satisfies mortgage lenders."},
        ],
    },
]

@app.route("/blog")
def blog_index():
    return render_template("blog_index.html", **_ctx(
        title="UK Dividend Tax Guides 2026/27 | UKDividendTaxCalculator.co.uk",
        meta_description="In-depth guides on UK dividend tax for contractors, directors, investors and retirees. Covering 2026/27 rates, allowances and planning.",
        canonical_url=SITE_URL + "/blog",
        posts=BLOG_POSTS,
    ))

BLOG_BY_SLUG = {p["slug"]: p for p in BLOG_POSTS}

@app.route("/blog/<slug>")
def blog_post(slug):
    post = BLOG_BY_SLUG.get(slug)
    if not post:
        abort(404)
    return render_template("blog_post.html", **_ctx(
        title=post["title"],
        meta_description=post["description"],
        canonical_url=SITE_URL + f"/blog/{slug}",
        post=post,
        examples=[],
        article_faqs=post.get("faqs", []),
        reference_facts=None,
        sources=[
            {"url": "https://www.gov.uk/tax-on-dividends", "label": "HMRC: Tax on dividends"},
            {"url": "https://www.gov.uk/income-tax-rates", "label": "HMRC: Income Tax rates and Personal Allowances"},
            {"url": "https://www.gov.uk/guidance/rates-and-allowances-income-tax", "label": "HMRC: Rates and allowances — Income Tax"},
        ],
    ))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
