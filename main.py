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
    ] + [(f"{SITE_URL}/dividend-tax/{a}","0.5","monthly") for a in DIVIDEND_AMOUNTS]
    r = make_response(render_template("sitemap.xml", url_entries=entries, now=now))
    r.content_type = "application/xml"
    return r

@app.route("/")
def landing():
    calc = calculate_dividend_tax(salary_income=40000, dividend_income=10000)
    faq = [
        {"q":"What is the dividend allowance for 2026/27?","a":"The dividend allowance is £500 for 2026/27. Dividends within this amount are free from dividend tax, regardless of which tax band you are in. This £500 sits on top of your Personal Allowance."},
        {"q":"What are the dividend tax rates for 2026/27?","a":"The dividend tax rates for 2026/27 are 10.75% in the basic-rate band (income up to £50,270), 35.75% in the higher-rate band (£50,271–£125,140), and 39.35% in the additional-rate band (above £125,140). These rates have applied since April 2023."},
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
        meta_description="Learn how dividend tax works for higher-rate taxpayers in 2026/27, including the £500 dividend allowance and 35.75% rate.",
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
