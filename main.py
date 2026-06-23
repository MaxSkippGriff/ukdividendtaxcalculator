"""UKDividendTaxCalculator.co.uk Flask application."""
from __future__ import annotations
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, abort, make_response, redirect, render_template, request, send_from_directory
from flask_limiter import Limiter
from calculator import active_tax_year, TAX_YEAR, calculate_dividend_tax, PERSONAL_ALLOWANCE, BASIC_RATE_LIMIT, DIVIDEND_ALLOWANCE, DIVIDEND_BASIC_RATE, DIVIDEND_HIGHER_RATE, DIVIDEND_ADDITIONAL_RATE
from scraper_guard import init_guard
import firestore_client as _fs

load_dotenv()

_PUBLIC_PATHS = (
    "/sitemap.xml", "/robots.txt", "/ads.txt", "/favicon.ico",
    "/favicon-16x16.png", "/favicon-32x32.png", "/apple-touch-icon.png",
    "/site.webmanifest", "/health",
)
_HONEYPOT_BLOCKED: set = set()

app = Flask(__name__)

CANONICAL_HOST = os.getenv("CANONICAL_HOST", "ukdividendtaxcalculator.co.uk").replace("https://","").replace("http://","")
# Named amount pages for SEO
NAMED_AMOUNTS = [5000, 10000, 20000, 50000, 100000]
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
        (f"{SITE_URL}/editorial-standards","0.4","yearly"),
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
        (f"{SITE_URL}/dividend-tax-calculator-director","0.7","monthly"),
        (f"{SITE_URL}/dividend-allowance-2026-27","0.7","monthly"),
        (f"{SITE_URL}/dividend-tax-vs-salary-calculator","0.7","monthly"),
        (f"{SITE_URL}/dividend-tax-scotland","0.7","monthly"),
        (f"{SITE_URL}/how-to-pay-less-dividend-tax","0.7","monthly"),
        (f"{SITE_URL}/dividend-tax-self-assessment","0.7","monthly"),
        (f"{SITE_URL}/dividend-tax-foreign-investors","0.7","monthly"),
        (f"{SITE_URL}/dividend-tax-rates-2026-27","0.8","monthly"),
    ] + [(f"{SITE_URL}/blog/{p['slug']}","0.6","monthly") for p in BLOG_POSTS] + [
        (f"{SITE_URL}/dividend-tax/{a}","0.5","monthly") for a in DIVIDEND_AMOUNTS
    ] + [(f"{SITE_URL}/dividend-tax-on-{a}","0.6","monthly") for a in NAMED_AMOUNTS]
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
        {"q":"Is corporation tax separate from dividend tax?","a":"Yes. Corporation tax is paid by the company on its profits before any dividends are paid. When a dividend is then paid to a shareholder, dividend tax is calculated on the shareholder's personal income. This calculator covers only the personal dividend tax, not corporation tax on profits."},
    ]
    return render_template("landing.html", **_ctx(
        title="Dividend Tax Calculator UK 2026/27 | Free Estimator",
        meta_description="Dividend tax calculator 2026/27: £500 allowance, 8.75% basic rate, 33.75% higher rate, 39.35% additional rate. Works for salary + dividends. Includes Scotland.",
        canonical_url=SITE_URL+"/",
        calc=calc,
        faq_items=faq,
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"}],
    ))

@app.route("/calculator")
def calculator_page():
    return render_template("calculator.html", **_ctx(
        title="Dividend Tax Calculator 2026/27 | UK Dividend Tax Breakdown",
        meta_description="Free UK dividend tax calculator for 2026/27. Enter salary and dividend income to get a full breakdown by band: 8.75% basic, 33.75% higher, 39.35% additional.",
        canonical_url=SITE_URL+"/calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Calculator","url":SITE_URL+"/calculator"}],
    ))

@app.route("/methodology")
def methodology():
    return render_template("methodology.html", **_ctx(
        title="Methodology, How We Calculate UK Dividend Tax 2026/27",
        meta_description="How UKDividendTaxCalculator.co.uk calculates dividend tax: 2026/27 rates, £500 allowance, band ordering and what we don't model.",
        canonical_url=SITE_URL+"/methodology",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Methodology","url":SITE_URL+"/methodology"}],
    ))

@app.route("/about")
def about():
    return render_template("about.html", **_ctx(
        title="About UK Dividend Tax Calculator, Free Dividend Tax Tool",
        meta_description="About UKDividendTaxCalculator.co.uk, a free, independent tool to estimate UK dividend tax for 2026/27.",
        canonical_url=SITE_URL+"/about",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"About","url":SITE_URL+"/about"}],
    ))

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", **_ctx(
        title="Privacy Policy, UKDividendTaxCalculator.co.uk",
        meta_description="Privacy policy for UKDividendTaxCalculator.co.uk. We don't store your financial data.",
        canonical_url=SITE_URL+"/privacy",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Privacy","url":SITE_URL+"/privacy"}],
    ))

@app.route("/editorial-standards")
def editorial_standards():
    return render_template("editorial_standards.html", **_ctx(
        title="Editorial Standards, UKDividendTaxCalculator.co.uk",
        meta_description="How UKDividendTaxCalculator.co.uk writes, reviews and maintains its calculator content and guides on UK dividend tax.",
        canonical_url=SITE_URL+"/editorial-standards",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Editorial Standards","url":SITE_URL+"/editorial-standards"}],
    ))

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        try:
            db = _fs.get_db()
            if db is not None:
                db.collection("contact_messages").add({
                    "name": name,
                    "email": email,
                    "message": message,
                    "site": SITE_URL,
                    "created_at": _fs.server_timestamp(),
                    "read": False,
                })
        except Exception:
            pass
        return redirect("/contact?sent=1")
    sent = request.args.get("sent") == "1"
    return render_template("contact.html", **_ctx(
        title="Contact, UKDividendTaxCalculator.co.uk",
        meta_description="Get in touch with UKDividendTaxCalculator.co.uk.",
        canonical_url=SITE_URL+"/contact",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Contact","url":SITE_URL+"/contact"}],
        sent=sent,
    ))

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html", **_ctx(
        title="Disclaimer, UKDividendTaxCalculator.co.uk",
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

# SEO redirect routes, common alternative URLs pointing to canonical pages
@app.route("/dividend-calculator")
def redirect_dividend_calculator():
    return redirect(SITE_URL + "/", code=301)

@app.route("/dividend-tax-uk")
def redirect_dividend_tax_uk():
    return redirect(SITE_URL + "/", code=301)

@app.route("/tax-on-dividends-calculator")
def redirect_tax_on_dividends_calculator():
    return redirect(SITE_URL + "/", code=301)

@app.route("/foreign-dividend-tax")
def redirect_foreign_dividend_tax():
    return redirect(SITE_URL + "/blog/foreign-dividend-tax-uk", code=301)

@app.route("/salary-vs-dividends")
def redirect_salary_vs_dividends():
    return redirect(SITE_URL + "/blog/salary-vs-dividends-director-2026", code=301)

@app.route("/salary-vs-dividends-calculator")
def redirect_salary_vs_dividends_calculator():
    return redirect(SITE_URL + "/blog/salary-vs-dividends-director-2026", code=301)

@app.route("/dividend-income-tax-calculator")
def redirect_dividend_income_tax_calculator():
    return redirect(SITE_URL + "/", code=301)

@app.route("/limited-company-dividend-tax-calculator")
def redirect_limited_company_dividend_tax_calculator():
    return redirect(SITE_URL + "/director-dividend-calculator", code=301)

# Additional SEO redirect aliases
@app.route("/calculate-dividend-tax")
def redirect_calculate_dividend_tax():
    return redirect(SITE_URL + "/calculator", code=301)

@app.route("/tax-on-dividends")
def redirect_tax_on_dividends():
    return redirect(SITE_URL + "/", code=301)

@app.route("/dividend-tax-rate")
def redirect_dividend_tax_rate():
    return redirect(SITE_URL + "/dividend-tax-rates-2026-27", code=301)

@app.route("/dividend-tax-2026-27")
def redirect_dividend_tax_2026_27():
    return redirect(SITE_URL + "/dividend-tax-rates-2026-27", code=301)

@app.route("/paye-and-dividend-calculator")
def redirect_paye_dividend():
    return redirect(SITE_URL + "/calculator", code=301)

@app.route("/director-dividend-tax-calculator")
def redirect_director_dividend_tax():
    return redirect(SITE_URL + "/dividend-tax-calculator-director", code=301)

@app.route("/ltd-company-dividend-calculator")
def redirect_ltd_dividend():
    return redirect(SITE_URL + "/dividend-tax-calculator-director", code=301)

@app.route("/dividend-vs-salary")
def redirect_dividend_vs_salary():
    return redirect(SITE_URL + "/dividend-tax-vs-salary-calculator", code=301)

@app.route("/pay-less-dividend-tax")
def redirect_pay_less():
    return redirect(SITE_URL + "/how-to-pay-less-dividend-tax", code=301)

@app.route("/dividend-tax-scotland-calculator")
def redirect_scotland_calc():
    return redirect(SITE_URL + "/dividend-tax-scotland", code=301)

@app.route("/foreign-dividend-calculator")
def redirect_foreign_dividend():
    return redirect(SITE_URL + "/dividend-tax-foreign-investors", code=301)

# New informational pages
@app.route("/dividend-tax-calculator-director")
def dividend_tax_calculator_director():
    return render_template("dividend-tax-calculator-director.html", **_ctx(
        title="Dividend Tax Calculator for Directors 2026/27 | UK Guide",
        meta_description="How directors calculate dividend tax in 2026/27: £9,100 or £12,570 salary, 8.75% basic rate, worked example showing effective rate on salary plus dividends.",
        canonical_url=SITE_URL + "/dividend-tax-calculator-director",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Calculator for Directors","url":SITE_URL+"/dividend-tax-calculator-director"}],
    ))

@app.route("/dividend-allowance-2026-27")
def dividend_allowance_2026_27():
    return render_template("dividend-allowance-2026-27.html", **_ctx(
        title="Dividend Allowance 2026/27: £500 Explained | UK Guide",
        meta_description="The dividend allowance is £500 for 2026/27. Every UK taxpayer gets this free dividend tax allowance. Worked examples, history and how it interacts with the Personal Allowance.",
        canonical_url=SITE_URL + "/dividend-allowance-2026-27",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Allowance 2026/27","url":SITE_URL+"/dividend-allowance-2026-27"}],
    ))

@app.route("/dividend-tax-vs-salary-calculator")
def dividend_vs_salary_calc():
    return render_template("dividend-tax-vs-salary-calculator.html", **_ctx(
        title="Dividend vs Salary Tax Comparison 2026/27 | UK Guide",
        meta_description="Compare dividend tax vs salary tax in 2026/27. Dividend tax is 8.75% basic vs 20% income tax + 8% NI for salary. Worked examples at multiple income levels.",
        canonical_url=SITE_URL + "/dividend-tax-vs-salary-calculator",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend vs Salary Calculator","url":SITE_URL+"/dividend-tax-vs-salary-calculator"}],
    ))

@app.route("/dividend-tax-scotland")
def dividend_tax_scotland():
    return render_template("dividend-tax-scotland.html", **_ctx(
        title="Dividend Tax in Scotland 2026/27 | UK Rates Apply",
        meta_description="Dividend tax in Scotland uses UK rates: 8.75%, 33.75%, 39.35%. Scottish income tax bands differ but do not affect dividend tax rates. Worked example for Scottish directors.",
        canonical_url=SITE_URL + "/dividend-tax-scotland",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Scotland","url":SITE_URL+"/dividend-tax-scotland"}],
    ))

@app.route("/how-to-pay-less-dividend-tax")
def how_to_pay_less_dividend_tax():
    return render_template("how-to-pay-less-dividend-tax.html", **_ctx(
        title="How to Pay Less Dividend Tax 2026/27 | 5 Strategies",
        meta_description="Five legal strategies to reduce dividend tax in 2026/27: ISA, pension contributions, spouse transfers, accumulation funds and salary optimisation. Worked examples throughout.",
        canonical_url=SITE_URL + "/how-to-pay-less-dividend-tax",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"How to Pay Less Dividend Tax","url":SITE_URL+"/how-to-pay-less-dividend-tax"}],
    ))

@app.route("/dividend-tax-self-assessment")
def dividend_tax_self_assessment():
    return render_template("dividend-tax-self-assessment.html", **_ctx(
        title="Self Assessment for Dividend Income 2026/27 | UK Guide",
        meta_description="When to file Self Assessment for dividends in 2026/27: £500 threshold, 31 Jan 2028 deadline, what to include, foreign dividends, and penalties for late filing.",
        canonical_url=SITE_URL + "/dividend-tax-self-assessment",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Self Assessment","url":SITE_URL+"/dividend-tax-self-assessment"}],
    ))

@app.route("/dividend-tax-foreign-investors")
def dividend_tax_foreign_investors():
    return render_template("dividend-tax-foreign-investors.html", **_ctx(
        title="Foreign Dividend Tax UK 2026/27 | Withholding Tax Guide",
        meta_description="UK residents pay dividend tax on foreign dividends at 8.75%/33.75%/39.35%. Withholding tax credits offset UK liability. How to declare on Self Assessment.",
        canonical_url=SITE_URL + "/dividend-tax-foreign-investors",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Foreign Dividend Tax Calculator","url":SITE_URL+"/dividend-tax-foreign-investors"}],
    ))

@app.route("/dividend-tax-rates-2026-27")
def dividend_tax_rates_2026_27():
    return render_template("dividend-tax-rates-2026-27.html", **_ctx(
        title="UK Dividend Tax Rates 2026/27: 8.75%, 33.75%, 39.35%",
        meta_description="Complete 2026/27 dividend tax rates: 8.75% basic, 33.75% higher, 39.35% additional. £500 allowance. Comparison with previous years and worked examples.",
        canonical_url=SITE_URL + "/dividend-tax-rates-2026-27",
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":"Dividend Tax Rates 2026/27","url":SITE_URL+"/dividend-tax-rates-2026-27"}],
    ))

@app.route("/dividend-tax-calculator-2026")
@app.route("/uk-dividend-tax-calculator-2026")
def redirect_dividend_calc_2026():
    return redirect(SITE_URL + "/", code=301)

@app.route("/dividend-tax-2026")
def redirect_dividend_tax_2026():
    return redirect(SITE_URL + "/dividend-tax-rates-2026-27", code=301)

@app.route("/how-are-dividends-taxed-uk")
@app.route("/is-dividend-income-taxable")
def redirect_how_dividends_taxed():
    return redirect(SITE_URL + "/dividend-tax-uk", code=301)

@app.route("/dividend-tax-exempt")
def redirect_dividend_tax_exempt():
    return redirect(SITE_URL + "/dividends-inside-isa", code=301)

@app.route("/director-take-home-salary-dividend")
def redirect_director_take_home():
    return redirect(SITE_URL + "/director-dividend-calculator", code=301)

@app.route("/dividend-tax-self-employed")
def redirect_dividend_self_employed():
    return redirect(SITE_URL + "/dividend-tax-for-contractors", code=301)

@app.route("/best-way-to-take-dividends")
def redirect_best_way_dividends():
    return redirect(SITE_URL + "/how-to-pay-less-dividend-tax", code=301)

@app.route("/dividend-tax-basic-rate")
def redirect_dividend_basic_rate():
    return redirect(SITE_URL + "/dividend-tax-basic-rate-taxpayer", code=301)

@app.route("/dividend-tax-higher-rate")
def redirect_dividend_higher_rate():
    return redirect(SITE_URL + "/dividend-tax-higher-rate-taxpayer", code=301)

DIVIDEND_AMOUNTS = [1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000, 100000]

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


# Named amount pages, SEO-friendly slug versions (e.g. /dividend-tax-on-10000)
@app.route("/dividend-tax-on-<int:amount>")
def dividend_tax_on_amount(amount: int):
    if amount not in NAMED_AMOUNTS:
        abort(404)
    calc_basic = calculate_dividend_tax(salary_income=30000, dividend_income=amount)
    calc_higher = calculate_dividend_tax(salary_income=55000, dividend_income=amount)
    return render_template("dividend-tax-on-amount.html", **_ctx(
        title=f"Dividend Tax on £{amount:,} 2026/27 | UK Worked Examples",
        meta_description=f"How much tax on £{amount:,} of dividends in 2026/27? Basic-rate taxpayer (£30k salary): £{calc_basic.total_dividend_tax:,.0f}. Higher-rate taxpayer (£55k salary): £{calc_higher.total_dividend_tax:,.0f}. Includes worked calculation.",
        canonical_url=SITE_URL+f"/dividend-tax-on-{amount}",
        amount=amount,
        calc_basic=calc_basic,
        calc_higher=calc_higher,
        all_amounts=NAMED_AMOUNTS,
        breadcrumbs=[{"name":"Home","url":SITE_URL+"/"},{"name":f"Dividend Tax on £{amount:,}","url":SITE_URL+f"/dividend-tax-on-{amount}"}],
    ))


BLOG_POSTS = [
    {
        "slug": "dividend-tax-rates-2026-27",
        "title": "Dividend Tax Rates 2026/27, All Three Bands Explained",
        "description": "UK dividend tax rates for 2026/27: 8.75% basic rate, 33.75% higher rate, 39.35% additional rate. £500 dividend allowance. Why your salary determines which rate applies, and when Self Assessment is required.",
        "date_iso": "2026-05-26",
        "date": "May 2026",
        "reading_time": "7 min read",
        "sections": [
            {
                "heading": "The Three Dividend Tax Rates",
                "paragraphs": [
                    "Dividend income is taxed at rates that are distinct from income tax rates on salary. For 2026/27 the rates are: 8.75% on dividends within the basic-rate band (total income up to £50,270), 33.75% on dividends in the higher-rate band (£50,271 to £125,140), and 39.35% on dividends in the additional-rate band (above £125,140). These rates have applied since April 2022 when the 1.25 percentage point increase was made permanent following the reversal of the Health and Social Care Levy for other taxes.",
                    "These are not the same as income tax rates. You do not pay 20% basic rate on dividends, you pay 8.75%. You do not pay 40% higher rate, you pay 33.75%. The lower rates exist because dividends are paid from company profits that have already been subject to corporation tax. The government regards this as partial economic double taxation, hence the preferential rates. But 33.75% and 39.35% are still meaningful rates, particularly for those whose dividend income falls in the higher or additional-rate bands.",
                ],
            },
            {
                "heading": "The £500 Dividend Allowance",
                "paragraphs": [
                    "Every UK taxpayer receives a dividend allowance of £500 for 2026/27. The first £500 of dividend income each year is free from dividend tax. This applies regardless of which income tax band you are in, a basic-rate taxpayer and an additional-rate taxpayer both receive the same £500 allowance. The allowance was reduced to £500 from April 2024, down from £1,000 the previous year and £2,000 before that.",
                    "The allowance cannot be carried forward to the next tax year and cannot be shared with a spouse. It occupies a slot within your income bands rather than being a deduction, this means it uses up some of your basic-rate or higher-rate band, which affects how much of your other income falls into each band. For most investors this distinction is not material, but it matters for complex income structures.",
                ],
            },
            {
                "heading": "How Dividends Sit on Top of Other Income, The Stacking Rule",
                "paragraphs": [
                    "Dividends are always treated as the top slice of your total income. Your salary, pension and other non-dividend income fills the personal allowance (£12,570) and then the basic-rate band first. Dividends are then assessed on whatever band they fall into after all that other income has been allocated. This is sometimes called the stacking rule.",
                    "The practical consequence is that the dividend tax rate you pay depends heavily on how much salary and other income you have. A person with no other income and £30,000 of dividends pays only 8.75% on most of it (after the personal allowance and the £500 allowance). A person with a £45,000 salary and £10,000 of dividends finds that most of those dividends land in the higher-rate band at 33.75%, because the salary has used up most of the basic-rate band. Same dividends, very different tax bill. This is why the calculator asks for your salary or other income before calculating dividend tax.",
                ],
            },
            {
                "heading": "Self Assessment Requirement",
                "paragraphs": [
                    "Dividend tax cannot be collected through PAYE. If your dividend income exceeds £500 in a tax year, you must report it through Self Assessment. This means registering for Self Assessment with HMRC (if you are not already registered), filing a tax return by 31 January following the end of the tax year, and paying any tax due by the same deadline. Tax returns for 2026/27 must be filed and paid by 31 January 2028.",
                    "The £500 threshold means even small investors who receive just over £500 in dividends from a general investment account need to file a return. Dividends inside ISAs are completely exempt and do not count towards the £500 threshold, they need not be declared at all. If you already file a Self Assessment return for another reason (self-employment, rental income, salary above £100,000), you simply add your dividend income to the existing return.",
                ],
            },
        ],
        "faqs": [
            {"q": "What are the dividend tax rates for 2026/27?", "a": "8.75% basic rate, 33.75% higher rate, 39.35% additional rate. These apply after the £500 dividend allowance."},
            {"q": "Do I pay dividend tax if my dividends are under £500?", "a": "No. The £500 dividend allowance means the first £500 of dividends each year is free from dividend tax. You still need to file Self Assessment if your dividends exceed £500."},
            {"q": "Why does my salary affect my dividend tax rate?", "a": "Dividends sit on top of other income. Your salary fills the basic-rate band first, so the more salary you have, the higher up the bands your dividends land, and the higher the dividend tax rate."},
        ],
    },
    {
        "slug": "dividend-tax-directors-guide",
        "title": "Dividend Tax for Company Directors, Salary Plus Dividends",
        "description": "How limited company directors structure salary and dividends in 2026/27: £9,100 vs £12,570 salary, NI savings, 8.75%/33.75% dividend tax rates and worked example showing the effective rate on combined income.",
        "date_iso": "2026-05-26",
        "date": "May 2026",
        "reading_time": "8 min read",
        "sections": [
            {
                "heading": "The Typical Director Structure",
                "paragraphs": [
                    "Most sole-director limited company owners take a low salary, typically around £5,000 to £12,570, and draw the remainder of their income as dividends from post-corporation-tax profits. This structure exists for two reasons: first, dividends are not subject to National Insurance (either employee or employer), whereas salary attracts employee NI at 8% (up to £50,270) and employer NI at 15%; second, dividend tax rates are lower than income tax rates on salary at the same income level.",
                    "A salary of £9,100 (just above the NI lower earnings limit, qualifying for a State Pension credit year) means the company pays no employer NI and the director pays no employee NI on the salary. A salary of £12,570 (the personal allowance) eliminates income tax on the salary but does attract employer NI on the portion above the secondary threshold of approximately £5,000. Whether £9,100 or £12,570 is optimal depends on the corporation tax rate and whether the employer NI cost is worthwhile for the additional personal allowance saving.",
                ],
            },
            {
                "heading": "Calculating the Effective Rate, Worked Example",
                "paragraphs": [
                    "Consider a director with a £9,100 salary and £50,000 in dividends, total income £59,100. Income tax on salary: the £9,100 salary is entirely within the personal allowance (£12,570), so nil income tax on salary. Employee NI on salary: nil (below the primary threshold). Employer NI: nil (below the secondary threshold of approximately £5,000, actually £9,100 is slightly above £5,000, so employer NI applies on the excess of approximately £4,100 at 15% = £615 paid by the company).",
                    "On the £50,000 of dividends: personal allowance is £12,570, of which £9,100 is used by salary, leaving £3,470 of personal allowance available for dividends. The first £3,470 of dividends is sheltered by the remaining personal allowance (nil tax). The next £500 is the dividend allowance (nil tax). Dividends now assessed: £50,000 − £3,470 − £500 = £46,030. The remaining basic-rate band is £50,270 − £9,100 = £41,170. Of the £46,030 taxable dividends, £41,170 falls in the basic-rate band at 8.75% = £3,602; the remaining £4,860 falls into the higher-rate band at 33.75% = £1,640. Total dividend tax: approximately £5,242. The director's effective personal tax rate on £59,100 total income is approximately 8.9%.",
                ],
            },
            {
                "heading": "The Dividend Allowance Within the Structure",
                "paragraphs": [
                    "The £500 dividend allowance is factored into the calculation above, it sits within the basic-rate band after the personal allowance is used by salary. For a director with a low salary, the personal allowance shelters considerably more income than the dividend allowance, making the dividend allowance a relatively minor component of the overall saving. Its main value is for directors whose salary already uses the full personal allowance, where the £500 allowance provides a small additional exempt amount at the bottom of the dividend assessment.",
                ],
            },
            {
                "heading": "When the Structure Stops Being Tax-Efficient",
                "paragraphs": [
                    "Above total income of £50,270, dividends start attracting 33.75%, the higher-rate dividend tax. For a director taking a £9,100 salary, dividends are taxed at 8.75% up to total income of approximately £50,270, and at 33.75% above that. The structure remains more tax-efficient than equivalent salary income above £50,270 (where salary would attract 40% income tax and 2% NI), but the advantage narrows significantly.",
                    "Above £125,140, dividends are taxed at the additional rate of 39.35%. At this point, directors with very high incomes may benefit from reviewing the corporation tax position more carefully, particularly if profits are being retained in the company rather than extracted, which can trigger complex rules around close companies. Taking large employer pension contributions directly from the company is often more efficient than dividends above the higher-rate threshold.",
                ],
            },
        ],
        "faqs": [
            {"q": "What salary should a director take in 2026/27?", "a": "Most directors take a salary around £9,100 (no NI for either party) or £12,570 (uses full personal allowance, some employer NI). The optimal level depends on the company's corporation tax position."},
            {"q": "Is dividend income always more tax-efficient than salary for a director?", "a": "Yes for most income levels, because dividends avoid NI entirely. However above £50,270 the advantage reduces, and above £125,140 the comparison is closer. Always model the combined personal and company tax position."},
            {"q": "At what income does the higher-rate dividend tax kick in?", "a": "When total income (salary plus dividends) exceeds £50,270. For a director with a £9,100 salary, the higher 33.75% rate begins to apply when dividends take total income above £50,270."},
        ],
    },
    {
        "slug": "dividend-vs-cgt-comparison",
        "title": "Dividend Tax vs Capital Gains Tax, Which Is Lower?",
        "description": "Dividend income and capital gains are taxed differently. At basic rate the difference is small; at higher rate, CGT at 10% or 20% beats dividend tax at 33.75% by a significant margin. Here is the arithmetic.",
        "date_iso": "2026-05-26",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "The Fundamental Difference",
                "paragraphs": [
                    "Dividend income and capital gains are fundamentally different in how they arise. Dividends are income paid by a company out of profits, they are declared by the board and paid to shareholders. Capital gains arise when you sell an asset for more than you paid for it. You do not usually get to choose which type of return you receive, a company either pays dividends or it does not, and the gain on a sale is whatever the market determines.",
                    "The distinction matters for tax because HMRC treats them entirely differently. Dividend income is subject to dividend tax rates (8.75%, 33.75%, 39.35%). Capital gains are subject to CGT rates (10%/20% for most assets, 18%/24% for residential property). In most cases, capital gains are taxed more lightly than equivalent dividend income, particularly at higher income levels.",
                ],
            },
            {
                "heading": "Where You Can Choose",
                "paragraphs": [
                    "There are situations where investors can influence whether their return comes as income or capital. Accumulation funds reinvest dividends internally rather than distributing them, so the investor's return accrues as capital growth rather than income. This is sometimes called 'rolling up' income, it can convert what would have been taxable dividend income into a future capital gain instead. Whether this is advantageous depends on your income level and the tax year in which you ultimately sell.",
                    "Company directors have a genuine choice between salary and dividends (income) or retaining profits in the company for future capital growth (potentially a capital gain on sale). Pension contributions made by the company create a different outcome again. The optimal route requires modelling across multiple tax types simultaneously.",
                ],
            },
            {
                "heading": "The Arithmetic at Different Income Levels",
                "paragraphs": [
                    "For a basic-rate taxpayer: dividend tax is 8.75% and CGT on most assets is 10%. The difference is only 1.25 percentage points, broadly similar, and the choice between holding income-generating versus growth assets is not primarily driven by this differential. Residential property CGT is 18%, noticeably higher than dividend tax at 8.75%.",
                    "For a higher-rate taxpayer: dividend tax is 33.75% and CGT on shares is 20%. The gap is 13.75 percentage points, a very significant difference. A £10,000 return from dividends costs £3,375 in tax; the same £10,000 from a capital gain on shares costs £2,000. This is why higher-rate taxpayers with a choice between accumulation and income funds, or between retained company profits and dividends, often prefer the capital gains route. For residential property at 24%, CGT is still below the 33.75% higher-rate dividend rate.",
                ],
            },
            {
                "heading": "ISAs and the Answer to Which Is Lower",
                "paragraphs": [
                    "Inside an ISA, the answer is zero for both. Dividends received from shares held in a Stocks and Shares ISA are completely free from dividend tax. Capital gains on ISA holdings are completely free from CGT. The annual ISA subscription limit for 2026/27 is £20,000 per person. For any investor with holdings inside an ISA, the comparison between dividend tax and CGT is irrelevant, both rates are zero.",
                    "This is why long-term investors prioritise sheltering high-return investments inside ISAs. Whether those investments generate returns as dividends or capital gains, the tax treatment is identical, and identically attractive. The comparison between dividend tax and CGT only becomes relevant for the portion of a portfolio held outside an ISA.",
                ],
            },
        ],
        "faqs": [
            {"q": "Is dividend income taxed more than capital gains?", "a": "At higher rate: yes, significantly. Dividend tax is 33.75%, CGT on shares is 20%. At basic rate: dividend tax is 8.75%, CGT is 10%, very similar. For residential property, CGT is 18%/24%, which is higher than basic-rate dividend tax."},
            {"q": "Can I convert dividend income into capital gains?", "a": "In some cases yes, accumulation funds reinvest dividends as growth rather than paying them out, converting future income into a potential capital gain. Directors can also retain profits in the company rather than paying dividends."},
            {"q": "Are there any UK investments where both dividend tax and CGT are zero?", "a": "Yes, investments held inside a Stocks and Shares ISA. Both dividends and capital gains are completely exempt from tax within the ISA wrapper."},
        ],
    },
    {
        "slug": "self-assessment-dividends",
        "title": "Self Assessment for Dividend Income 2026/27",
        "description": "When to file Self Assessment for dividends in 2026/27: the £500 threshold, how to report UK and foreign dividends, withholding tax credits, and penalties for missing the 31 January deadline.",
        "date_iso": "2026-05-26",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "When You Must File",
                "paragraphs": [
                    "You must file a Self Assessment tax return if your dividend income exceeds £500 in a tax year. This threshold has applied from the 2024/25 tax year onwards, it reduced from £1,000 in 2023/24 following the cut in the dividend allowance. If your total dividends are £500 or less, no return is required for dividend income alone (though you may need to file for other reasons).",
                    "If you are already required to file a Self Assessment return for another reason, self-employment income, rental income, salary above £100,000, a director's tax affairs, you simply add your dividend income to the existing return. You do not file separately for dividends. The requirement to file applies to each tax year independently: if your dividends exceeded £500 in 2024/25 but not in 2025/26, you file for 2024/25 but may not need to for 2025/26 (unless another trigger applies).",
                ],
            },
            {
                "heading": "What to Include on the Return",
                "paragraphs": [
                    "Dividend income is reported in the 'UK dividends' section of the Self Assessment return (SA100 and, if needed, SA101 supplementary pages). You enter the gross dividend amount received in the tax year. For UK dividends, the gross amount is the cash amount you received, there is no withholding tax on UK dividends, so the figure from your broker statement or dividend voucher is the gross amount.",
                    "Older dividend vouchers (pre-April 2016) included a notional 10% tax credit, but this was abolished in April 2016. If you receive dividends from UK companies via a broker, your end-of-year statement will show the total dividends received. Investment platforms typically provide a consolidated tax certificate each April showing dividends paid during the year, this is the figure to use. Enter the total UK dividend income and HMRC will calculate the tax using the allowance and applicable rate.",
                ],
            },
            {
                "heading": "Dividend Income from Foreign Companies",
                "paragraphs": [
                    "Foreign dividends are more complex. Most overseas companies are subject to withholding tax in their home country before the dividend reaches you. The withholding tax rate varies: 15% is common from the USA under the UK-US tax treaty, though the standard US rate is 30%. France typically withholds at 12.8% under the UK-France treaty.",
                    "On your Self Assessment return, you declare the gross dividend (before withholding) and claim credit for the withholding tax already paid overseas. The credit is limited to the UK dividend tax that would otherwise be due, you cannot get a repayment if the withholding tax exceeds your UK liability. For many basic-rate taxpayers whose dividend tax rate is only 8.75%, a 15% US withholding tax already exceeds the UK tax due, meaning there is no additional UK dividend tax but also no repayment of the excess withholding. You should report foreign dividends in the 'Foreign income' section of the return (SA106 supplementary pages).",
                ],
            },
            {
                "heading": "Penalties for Not Filing",
                "paragraphs": [
                    "If you are required to file a Self Assessment return and fail to do so, HMRC charges a £100 fixed penalty immediately after the 31 January filing deadline (even if no tax is owed). Daily penalties of £10 per day accrue after 3 months, up to a maximum of £900. After 6 months, a further penalty of 5% of the tax due (or £300 if greater) is charged. After 12 months, another 5% penalty applies.",
                    "For investors who are unaware of the filing requirement, perhaps because their dividends only recently crept above the £500 threshold, HMRC can impose all of these penalties retrospectively. If you have missed a filing deadline, the best approach is to register for Self Assessment and file as soon as possible. HMRC may waive penalties in cases of genuine ignorance, but this is not guaranteed. The interest charge on late payment is separate from the penalties and accrues from the 31 January payment deadline.",
                ],
            },
        ],
        "faqs": [
            {"q": "Do I need to file Self Assessment if my dividends are exactly £500?", "a": "No. The requirement to file applies if dividends exceed £500. Exactly £500 or less does not trigger the obligation (unless you must file for another reason)."},
            {"q": "My broker doesn't send me a dividend voucher, what do I use?", "a": "Your broker's annual tax certificate or consolidated dividend statement, usually sent in April, shows the total dividends paid during the tax year. This is the figure to enter on the Self Assessment return."},
            {"q": "What is the penalty for missing the Self Assessment filing deadline?", "a": "A £100 fixed penalty immediately, then £10 per day after 3 months (up to £900), then 5% of tax due (or £300) at 6 months and again at 12 months."},
        ],
    },
    {
        "slug": "dividend-isa-vs-non-isa",
        "title": "Dividend Tax on ISA vs Non-ISA Investments",
        "description": "Dividends inside a Stocks and Shares ISA are completely free from UK income tax. Outside an ISA, dividend tax at 8.75%–39.35% applies above the £500 allowance. Here is the full comparison.",
        "date_iso": "2026-05-26",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "ISA Dividends",
                "paragraphs": [
                    "Dividends received from shares, funds or ETFs held inside a Stocks and Shares ISA are completely free from UK income tax and dividend tax. There is no limit on how much dividend income can accumulate inside an ISA, even if your ISA generates £50,000 of dividends in a year, none of it is taxable. No reporting is required; ISA income does not appear on a Self Assessment return. ISA dividends also do not count as income for any other purpose, they do not affect your personal allowance, your adjusted net income, the High Income Child Benefit Charge calculation or student loan repayments.",
                    "The current annual ISA subscription limit is £20,000 per person for 2026/27. Once funds are inside the ISA wrapper, all future dividends and capital gains are permanently tax-free, there is no time limit on holding, no CGT on growth, and no exit charge. The ISA is arguably the most straightforward and powerful tax-efficient vehicle for ordinary investors.",
                ],
            },
            {
                "heading": "Non-ISA Dividends",
                "paragraphs": [
                    "Dividends from shares held in a general investment account (GIA) or directly held shares (not in an ISA or pension) are subject to dividend tax above the £500 annual allowance. The rates are 8.75% basic, 33.75% higher and 39.35% additional, applied after the dividend allowance and after your other income has been allocated to the relevant bands. Dividend income in a GIA counts as income for all purposes: it can affect your personal allowance taper (if total income exceeds £100,000), trigger the High Income Child Benefit Charge, and for plan 2 or plan 5 student loans, it counts towards the income used for repayment calculations.",
                    "Non-ISA dividends must be reported through Self Assessment once total dividends exceed £500 in a tax year. The reporting obligation exists even if the resulting tax bill is small, HMRC cannot collect dividend tax through PAYE, so the onus is on the investor to declare.",
                ],
            },
            {
                "heading": "Moving Investments into an ISA",
                "paragraphs": [
                    "You cannot transfer shares directly from a GIA into an ISA. The only route is the bed and ISA strategy: sell the shares in the GIA, then use the cash proceeds to subscribe to the ISA and repurchase the shares (or an equivalent investment) inside the ISA wrapper. The sale in the GIA is a disposal for CGT purposes, any gain is subject to CGT in the normal way, reduced by the annual exempt amount (£3,000 for 2026/27).",
                    "During the tax year in which the transfer occurs, dividends paid on the old GIA holding count as taxable dividends up to the sale date, and dividends paid inside the new ISA holding after that date are tax-free. If the sale and repurchase happen in the same tax year and the holding pays dividends quarterly, you will typically have some taxable and some tax-free dividends from the same underlying fund in the same tax year.",
                ],
            },
            {
                "heading": "The £20,000 ISA Allowance, Prioritisation Strategy",
                "paragraphs": [
                    "With a fixed annual subscription limit of £20,000, investors with both dividend-paying and growth-oriented holdings face a choice about which to prioritise for the ISA wrapper. The answer depends on tax rates and holding periods. For higher-rate taxpayers, the dividend tax saving from sheltering dividend-paying investments is 33.75% annually, which is likely to exceed the capital gains saving from sheltering growth assets, which is only realised on disposal. This suggests prioritising dividend-paying income investments inside the ISA first.",
                    "However, the compounding effect of tax-free growth over decades is substantial. A growth investment that doubles over 10 years outside an ISA faces a 20% CGT charge on half the gain. Inside an ISA, there is no charge at all. For very long holding periods, the ISA shelter for high-growth assets can be more valuable. Most financial planners suggest holding the investment type with the highest annual tax drag inside the ISA first, which for most higher-rate taxpayers means high-dividend stocks and income funds.",
                ],
            },
        ],
        "faqs": [
            {"q": "Do I pay any tax on dividends inside an ISA?", "a": "No. Dividends inside a Stocks and Shares ISA are completely exempt from UK income tax and do not need to be reported. There is no limit on how much ISA dividend income you can receive tax-free."},
            {"q": "Do ISA dividends count towards the £500 dividend allowance?", "a": "No. ISA dividends are exempt and do not count towards the allowance or any filing threshold."},
            {"q": "Can I move my shares directly into an ISA?", "a": "No. You must sell the shares outside the ISA (crystallising any CGT liability) and use the proceeds to subscribe to the ISA, then repurchase inside the ISA. This is the bed and ISA strategy."},
        ],
    },
    {
        "slug": "dividend-tax-in-scotland",
        "title": "Dividend Tax in Scotland 2026/27: Scottish Income Tax Bands + UK Dividend Rates",
        "description": "Scottish income tax bands are different from rUK, but dividend tax rates (8.75%/33.75%/39.35%) are set by Westminster and apply to all UK taxpayers. This guide shows exactly how the two systems interact for Scottish directors and investors in 2026/27.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "6 min read",
        "sections": [
            {
                "heading": "Scotland Sets Its Own Income Tax Rates, But Not Dividend Tax Rates",
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
                    "Since April 2019, Welsh taxpayers have been subject to the Welsh Rate of Income Tax (WRIT). The UK Government reduced the basic, higher and additional rates each by 10 pence and the Welsh Government then set its own Welsh rates. For every year since 2019, the Welsh Government has set its rates to match the rUK (England and Northern Ireland) rates exactly. For 2026/27, this means Welsh taxpayers pay 20%, 40% and 45%, the same as in England and Northern Ireland.",
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
                    "The combination of a reduced dividend allowance (now just £500), rates of up to 39.35% and the interaction with income tax bands means dividend tax can be a significant cost for company directors and investors. Unlike PAYE, dividend tax is not withheld automatically, it must be declared through Self Assessment and paid by 31 January. This gives taxpayers an opportunity to plan ahead and use available reliefs before the tax year ends on 5 April.",
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
                    "Gifts of assets between spouses are made at no-gain/no-loss for capital gains tax purposes, so there is usually no CGT cost in transferring shares between spouses. The shares then generate dividends in the lower-earning spouse's name and are taxed at their marginal rate. This strategy is well-established and wholly legal, but the transfer must be a genuine gift, HMRC will scrutinise arrangements that appear artificial.",
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
                    "The trajectory of the allowance also serves as a reminder that tax reliefs can be reduced or removed. Long-term planning should not rely heavily on a single allowance remaining at its current level, diversifying across ISAs, pensions and other wrappers gives resilience against future changes.",
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
        "description": "Optimal salary and dividend split for limited company directors in 2026/27: £5,000 vs £12,570 salary, corporation tax at 19%/25%, 8.75% dividend tax, NI costs and full worked example on £50,000 profit.",
        "date_iso": "2026-05-01",
        "date": "May 2026",
        "reading_time": "9 min read",
        "sections": [
            {
                "heading": "Why the Salary/Dividend Mix Matters",
                "paragraphs": [
                    "Company directors who are also shareholders have flexibility in how they extract income from their company: salary, dividends, or a combination. Each method has a different tax treatment. Salary is subject to income tax under PAYE and National Insurance contributions (both employee and employer). Dividends are paid from post-corporation-tax profits and are subject to dividend tax at lower rates. Choosing the right mix can make a material difference to total tax paid.",
                    "There is no universally optimal split, the answer depends on the company's profit level, whether the director is a sole shareholder or shares ownership, whether there are other directors, the company's corporation tax rate and the director's other personal income. However, the principles are consistent and the key thresholds for 2026/27 are well-established.",
                ],
            },
            {
                "heading": "The Corporation Tax Angle",
                "paragraphs": [
                    "Corporation tax for 2026/27 is 25% on profits above £250,000 and 19% on profits up to £50,000, with marginal relief between. Salary is deductible as a business expense, reducing the profit on which corporation tax is charged. A £1 of salary saves 25p of corporation tax (at the main rate). Dividends are paid from post-tax profits and therefore have no corporation tax deduction.",
                    "This means salary is not purely a cost, it reduces the company's corporation tax bill. A £10,000 salary paid to a director (with no employer NI if kept below the secondary threshold of around £5,000, or with employer NI above) saves the company £2,500 in corporation tax at the main rate. The net cost to the company is £10,000 minus £2,500 = £7,500. The director then pays income tax and NI on the salary personally. For very low salary levels, the personal tax is also very low or zero.",
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
    {
        "slug": "foreign-dividend-tax-uk",
        "title": "Foreign Dividend Tax UK 2026/27, Double Taxation, Withholding Tax and How to Declare",
        "description": "Foreign dividends are taxed at the same UK rates as domestic dividends: 8.75%/33.75%/39.35% above the £500 allowance. But withholding tax paid abroad can be offset against your UK bill. This guide covers double taxation relief, country examples (US, EU) and how to declare foreign dividends on Self Assessment.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "8 min read",
        "sections": [
            {
                "heading": "UK Tax on Foreign Dividends, Same Rates as UK Dividends",
                "paragraphs": [
                    "If you hold shares in overseas companies, whether directly, via an investment platform, or through a fund, any dividends you receive are subject to UK income tax in exactly the same way as dividends from UK companies. For 2026/27 the rates are: 8.75% on dividends within the basic-rate band (total income up to £50,270), 33.75% in the higher-rate band (£50,271 to £125,140), and 39.35% in the additional-rate band (above £125,140). The £500 dividend allowance applies to your total dividends, UK and foreign combined, not separately to each type.",
                    "This means a UK investor receiving £300 in UK dividends and £400 in US dividends has £700 of total dividend income. After the £500 allowance, £200 is taxable at the applicable rate. HMRC does not distinguish between UK-sourced and foreign-sourced dividends in setting the rate, they all sit in the same pot.",
                ],
            },
            {
                "heading": "Withholding Tax, What It Is and Why It Matters",
                "paragraphs": [
                    "Most countries deduct a withholding tax from dividends before paying them to overseas investors. This means you receive less than the gross dividend. The withholding rate depends on the country and whether a double taxation agreement (DTA) exists between that country and the UK. Without a DTA, the withholding rate can be 25–35%. With a DTA, it is usually lower.",
                    "Common withholding rates for UK investors in 2026/27: United States, 15% under the UK-US tax treaty (standard rate is 30%, but the treaty reduces this to 15% for most UK investors); Germany, 15% under treaty; France, 12.8% under treaty; Ireland, 0% (no withholding on dividends to UK investors under the UK-Ireland treaty); Netherlands, 15% under treaty. Note that some countries have higher effective rates for certain investor types or fund structures. Always check your broker statement for the actual amount withheld.",
                ],
            },
            {
                "heading": "Double Taxation Relief, Offsetting Withholding Tax Against UK Tax",
                "paragraphs": [
                    "The UK has double taxation agreements with more than 130 countries. These agreements allow you to offset the withholding tax you have already paid abroad against the UK dividend tax you would otherwise owe. This prevents the same income from being taxed twice in full.",
                    "The relief works as follows: you declare the gross foreign dividend (before withholding) on your Self Assessment return and calculate the UK dividend tax due at the applicable UK rate. You then claim credit for the withholding tax paid, reducing the UK tax bill accordingly. The credit is capped at the UK tax that would otherwise be due, you cannot receive a repayment if the withholding tax exceeds your UK liability.",
                    "Example: You receive a US dividend with a gross amount of £1,000. The broker withholds 15% = £150, so you receive £850. Your UK dividend tax on £1,000 at the basic rate (8.75%) = £87.50. The foreign tax credit is capped at £87.50, so you have no additional UK tax to pay, but the excess £62.50 of US withholding is not refunded. For a higher-rate taxpayer, the picture is different: UK tax at 33.75% on £1,000 = £337.50; withholding credit of £150; additional UK tax due = £187.50.",
                ],
            },
            {
                "heading": "How to Declare Foreign Dividends on Self Assessment",
                "paragraphs": [
                    "Foreign dividends are reported in the 'Foreign income' section of the Self Assessment return, using the SA106 supplementary pages (not the UK dividend section). You must enter the gross dividend amount received in each country, the amount of withholding tax deducted, and claim the foreign tax credit. HMRC requires you to convert foreign currency amounts to pounds sterling using the exchange rate at the date of receipt (or an average rate for the year, which HMRC publishes).",
                    "Your broker or investment platform should provide a consolidated tax certificate or annual summary showing: the gross dividends paid from each country, the withholding tax deducted, and the net amount received. This is the source document for your Self Assessment return. If your platform does not break down dividends by country, you may need to obtain this information from individual dividend vouchers or the company's investor relations page.",
                    "The filing deadline is 31 January following the end of the tax year. For 2026/27 (ending 5 April 2027), the deadline is 31 January 2028. You must pay any UK tax due by the same date. Interest accrues on late payments from that date.",
                ],
            },
            {
                "heading": "Foreign Dividends Inside an ISA or SIPP",
                "paragraphs": [
                    "If you hold overseas shares or international funds inside a Stocks and Shares ISA or a pension (SIPP), UK dividend tax is not charged, the ISA and SIPP wrappers exempt you from UK tax regardless of the dividend source. However, withholding tax at source is a different matter: the foreign country still withholds tax before the dividend reaches your account, and in most cases this withholding cannot be reclaimed inside an ISA or SIPP wrapper (because there is no UK tax liability against which to claim the credit).",
                    "This is an important but often overlooked point. A UK investor holding US shares inside an ISA pays no UK dividend tax, but will typically still suffer the 15% US withholding tax and cannot claim it back. For US equities specifically, some platforms offer W-8BEN form filing which reduces the US withholding to 15% (from 30%) but cannot eliminate it entirely for ISA holders. This makes US dividend stocks slightly less tax-efficient inside an ISA than domestic income stocks, where no withholding applies.",
                ],
            },
        ],
        "faqs": [
            {"q": "Are foreign dividends taxed differently from UK dividends?", "a": "No. UK residents are taxed on foreign dividends at the same rates as UK dividends: 8.75% basic rate, 33.75% higher rate, 39.35% additional rate. The £500 dividend allowance covers all dividends combined."},
            {"q": "What is withholding tax and can I reclaim it?", "a": "Withholding tax is deducted by the foreign country before paying the dividend. You can offset it against your UK dividend tax liability (Double Taxation Relief). The credit is capped at your UK tax due, excess withholding is not refunded."},
            {"q": "How do I declare foreign dividends on my tax return?", "a": "Use the SA106 Foreign income supplementary pages. Enter the gross dividend (before withholding), the tax withheld, and claim the foreign tax credit. Convert foreign currency amounts to sterling at the exchange rate on the date of receipt."},
            {"q": "Do foreign dividends inside an ISA attract withholding tax?", "a": "Yes. The ISA wrapper removes UK dividend tax but does not prevent the foreign country from withholding tax at source. For US shares, the standard withholding is 30%, reduced to 15% under the UK-US treaty for those who have filed a W-8BEN form. This withholding cannot be reclaimed inside an ISA."},
        ],
    },
    {
        "slug": "how-much-dividend-tax-calculator",
        "title": "How Much Dividend Tax Will I Pay? 2026/27 Worked Examples",
        "description": "How much dividend tax will you pay in 2026/27? The answer depends on your salary. This guide works through five common scenarios, from a basic-rate investor to an additional-rate director, with full calculations at 8.75%, 33.75% and 39.35%.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "8 min read",
        "sections": [
            {
                "heading": "The Three Variables That Determine Your Bill",
                "paragraphs": [
                    "Three things determine how much dividend tax you pay: the amount of your dividend income, your salary and other non-dividend income, and whether those dividends are held inside or outside an ISA or pension. The interaction of salary and dividends is what makes the question non-trivial. Dividends are always treated as the top slice of income, your salary fills the Personal Allowance (£12,570) and the basic-rate band (up to £50,270) first, and dividends land on whatever remains.",
                    "The dividend allowance of £500 applies to everyone: the first £500 of dividends each year is free from dividend tax regardless of your income level. Above £500, the rate applied, 8.75%, 33.75% or 39.35%, depends on which band your dividends fall into after salary has filled the lower bands.",
                ],
            },
            {
                "heading": "Scenario 1: Basic-Rate Investor (£25,000 Salary, £3,000 Dividends)",
                "paragraphs": [
                    "A salaried employee earns £25,000 and receives £3,000 of dividends from a general investment account. Total income: £28,000, within the basic-rate band. Salary uses the Personal Allowance (£12,570) first, leaving taxable salary of £12,430. Dividends sit on top of the total income of £28,000.",
                    "Dividend allowance: £500 free. Taxable dividends: £2,500. All £2,500 fall within the remaining basic-rate band (£50,270 − £25,000 = £25,270 available). Dividend tax at 8.75% on £2,500 = £218.75. Total dividend tax bill: approximately £219. The Self Assessment return for this investor is straightforward, a single figure of £3,000 of UK dividends, and HMRC calculates the tax.",
                ],
            },
            {
                "heading": "Scenario 2: Higher-Rate Employee (£60,000 Salary, £8,000 Dividends)",
                "paragraphs": [
                    "An employee with a £60,000 salary receives £8,000 of dividends outside an ISA. Total income: £68,000, firmly in the higher-rate band. The salary of £60,000 exceeds the basic-rate limit of £50,270 by £9,730, so all of the basic-rate band is used by salary. Dividends of £8,000 land entirely in the higher-rate band.",
                    "Dividend allowance: £500 free. Taxable dividends: £7,500 at 33.75% = £2,531. Total dividend tax: £2,531. If this employee could move all £8,000 of dividends into a Stocks and Shares ISA, the saving would be the full £2,531, which illustrates why ISA prioritisation matters significantly for higher-rate taxpayers.",
                ],
            },
            {
                "heading": "Scenario 3: Director (£12,570 Salary, £45,000 Dividends)",
                "paragraphs": [
                    "A limited company director takes a salary of £12,570 and dividends of £45,000. Total income: £57,570. Salary of £12,570 uses the full Personal Allowance, no income tax on salary. For dividend tax, the salary has filled the basic-rate band up to £12,570. Remaining basic-rate band for dividends: £50,270 − £12,570 = £37,700.",
                    "Dividend allowance: £500 free. Taxable dividends: £44,500. Of these, £37,700 fall in the basic-rate band at 8.75% = £3,299. The remaining £6,800 fall in the higher-rate band at 33.75% = £2,295. Total dividend tax: £5,594. At total income of £57,570, this gives an effective dividend tax rate of approximately 12.4% on the dividend income. The director's total personal tax is essentially just this £5,594 plus modest employee NI on salary.",
                ],
            },
            {
                "heading": "Scenario 4: Retiree (No Salary, £15,000 Dividends)",
                "paragraphs": [
                    "A retiree with no employment income receives £15,000 of dividends from a share portfolio. No salary, no pension income (for simplicity). Total income: £15,000. The Personal Allowance of £12,570 shelters the first £12,570 of dividends (treating dividends as income). After that, the dividend allowance applies to the next £500: free.",
                    "Taxable dividends: £15,000 − £12,570 (PA) − £500 (allowance) = £1,930. All £1,930 falls within the basic-rate band. Dividend tax at 8.75% = £169. Total dividend tax: £169 on £15,000 of income. An extremely low effective rate, which is why dividend income is often described as very tax-efficient for retirees with no other income. This retiree must still file Self Assessment as dividends exceed £500.",
                ],
            },
            {
                "heading": "Scenario 5: Additional-Rate Taxpayer (£130,000 Salary, £20,000 Dividends)",
                "paragraphs": [
                    "A high earner with a £130,000 salary and £20,000 of dividends. Total income: £150,000. Salary of £130,000 exceeds £125,140, so all dividends land in the additional-rate band. The Personal Allowance is also fully tapered away at this income level (taper begins at £100,000, removed by £1 for every £2 above that; at £125,140 the PA is zero).",
                    "Dividend allowance: £500 free. Taxable dividends: £19,500 at 39.35% = £7,673. Total dividend tax: £7,673. This is a very high effective rate on the dividend income, and demonstrates why additional-rate taxpayers with significant dividend income outside an ISA face a substantial tax bill. Pension contributions to bring income below £125,140 would convert some additional-rate dividend tax into lower-rate savings.",
                ],
            },
            {
                "heading": "The Simple Rule: Use the Calculator for Your Exact Position",
                "paragraphs": [
                    "The five scenarios above illustrate the range of outcomes, but your actual bill depends on your precise salary, the source and amount of your dividend income, any pension contributions (which reduce adjusted net income), and whether any dividends are sheltered by an ISA or SIPP. The dividend tax calculator on this site handles all of these variables: enter your salary, any pension contributions, and your dividend income to get the exact breakdown by band.",
                    "If your dividends will exceed £500 in 2026/27, remember that a Self Assessment return is required. HMRC cannot collect dividend tax through PAYE. The deadline for 2026/27 is 31 January 2028.",
                ],
            },
        ],
        "faqs": [
            {"q": "How much dividend tax do I pay on £5,000 of dividends?", "a": "It depends on your salary. With a £30,000 salary (basic-rate taxpayer), dividend tax on £5,000 is approximately £394 (8.75% on £4,500 above the allowance). With a £55,000 salary (higher-rate taxpayer), it is approximately £1,519 (33.75% on £4,500)."},
            {"q": "Do I pay dividend tax if my dividends are under £500?", "a": "No. The £500 dividend allowance means the first £500 of dividends each year is free from dividend tax. You also do not need to file Self Assessment if total dividends are £500 or less (absent other reasons)."},
            {"q": "Why does my salary affect how much dividend tax I pay?", "a": "Dividends sit on top of other income. Salary fills the basic-rate band first. The more salary you have, the less of the basic-rate band remains for dividends, pushing more dividends into the higher-rate band at 33.75%."},
        ],
    },
    {
        "slug": "dividend-tax-limited-company-director",
        "title": "Dividend Tax for Limited Company Directors 2026/27: Complete Guide",
        "description": "A complete guide for limited company directors on dividend tax in 2026/27: optimal salary, dividend tax rates, NI savings, corporation tax interaction, and a full worked example showing the combined company-plus-personal tax position.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "12 min read",
        "sections": [
            {
                "heading": "Why Directors Extract Income as Dividends",
                "paragraphs": [
                    "The defining tax advantage of a limited company structure is the ability to pay dividends. Dividends are paid from company profits after corporation tax has been paid, and they carry no National Insurance, neither employer NI (at 15% from April 2026) nor employee NI (at 8% up to £50,270). For a director-shareholder, this makes dividends significantly cheaper to extract than equivalent salary at most income levels.",
                    "The trade-off is corporation tax. Salary is deductible as a business expense, reducing the profit on which corporation tax is charged. Dividends are not, they are paid from post-tax profits. At the small company rate of 19% or the main rate of 25%, this is a meaningful cost that must be factored into any comparison between salary and dividends. The optimal structure minimises total tax across both company and personal levels, not just one or the other.",
                ],
            },
            {
                "heading": "Corporation Tax in 2026/27",
                "paragraphs": [
                    "Corporation tax for 2026/27 is 19% on profits up to £50,000, 25% on profits above £250,000, and subject to marginal relief between £50,000 and £250,000. The effective marginal rate within the marginal relief band is approximately 26.5%. For a sole director company, the 19% small company rate typically applies if the combined extraction plus retained profits remain below £50,000. Above that, the marginal and main rates bite.",
                    "This means a director with a company earning £80,000 profit effectively faces a blended corporation tax rate somewhere between 19% and 25% on those profits. Before any dividend can be distributed, this tax must be paid. A £100,000 profit generates approximately £75,000 of post-tax profit available for dividends (at the 25% main rate), not £100,000.",
                ],
            },
            {
                "heading": "The Optimal Salary: £9,100 or £12,570?",
                "paragraphs": [
                    "For 2026/27, most directors choose a salary at one of two levels. The first is approximately £9,100, close to the National Insurance lower earnings limit. At this level, neither the director nor the company pays any NI. No income tax is payable on the salary (it is within the Personal Allowance of £12,570). The salary is still deductible for corporation tax. The director also accrues a qualifying year for State Pension purposes. This level suits directors who want maximum simplicity and minimum NI.",
                    "The second level is £12,570, the full Personal Allowance. No income tax is payable on the salary. However, employer NI at 15% applies on salary above the secondary threshold of approximately £5,000, so the company pays approximately £1,136 in employer NI (15% × £7,570). This employer NI is deductible for corporation tax. At the main 25% corporation tax rate, the net cost of the employer NI to the company is approximately £852. In exchange, the director has a higher salary deduction reducing taxable profits, usually worth it at the 25% rate but closer at 19%.",
                    "A salary above £12,570 becomes progressively less efficient: employee NI at 8% starts to accrue, and the combined NI burden increases for every additional pound of salary. Above the National Insurance upper earnings limit (£50,270), both income tax and NI rates are highest. Very few directors take salary above £12,570.",
                ],
            },
            {
                "heading": "Dividend Tax Rates and Thresholds",
                "paragraphs": [
                    "Once the salary level is set, remaining income needs are met by dividends. For 2026/27, dividend tax rates are: 8.75% on dividends within the basic-rate band (total income up to £50,270), 33.75% on dividends in the higher-rate band (£50,271 to £125,140), and 39.35% in the additional-rate band (above £125,140). The £500 dividend allowance shelters the first £500 of dividends each year.",
                    "For a director with a £12,570 salary, the basic-rate band available for dividends is £50,270 − £12,570 = £37,700. After the £500 allowance, approximately £37,200 of dividends can be taken at 8.75% before the 33.75% rate applies. This is the key planning target for directors who want to stay in the basic-rate band, keeping total income below £50,270.",
                ],
            },
            {
                "heading": "Full Worked Example: £70,000 Company Profit, £50,000 Extraction",
                "paragraphs": [
                    "A sole director's company earns £70,000 of profit before remuneration. The director wants to extract £50,000 of personal income in 2026/27. Strategy: salary of £12,570 plus dividends.",
                    "Step 1, Company position. Salary of £12,570 is deducted. Employer NI on £7,570 at 15% = £1,136 (deductible). Company taxable profit: £70,000 − £12,570 − £1,136 = £56,294. Corporation tax at the marginal/main rate (effective rate approximately 22% on £56,294 after marginal relief) = approximately £12,385. Post-tax profit available for dividends: £56,294 − £12,385 = £43,909.",
                    "Step 2, Director's personal income. Salary of £12,570: no income tax (fully covered by Personal Allowance), no employee NI (at primary threshold). Dividends required: £50,000 − £12,570 = £37,430. Check: £37,430 ≤ £43,909 post-tax profit, dividends are affordable. Dividend tax: £500 allowance free. Taxable dividends: £36,930. Remaining basic-rate band: £50,270 − £12,570 = £37,700. All £36,930 falls in the basic-rate band. Dividend tax at 8.75% = £3,231.",
                    "Total personal tax: £3,231 (no income tax on salary, no employee NI, dividend tax only). Total company tax: £12,385 corporation tax + £1,136 employer NI = £13,521. Combined total tax burden on £70,000 profit to extract £50,000: approximately £16,752. Effective combined tax rate on the £70,000 profit: approximately 24%. This compares very favourably with extracting the same income purely as salary, which would attract income tax at 20%/40% and full NI charges.",
                ],
            },
            {
                "heading": "When Higher-Rate Dividend Tax Becomes Relevant",
                "paragraphs": [
                    "Directors who need to extract more than approximately £50,270 in total income (salary plus dividends) will encounter the 33.75% higher-rate dividend tax on the excess. This does not mean the structure becomes inefficient, 33.75% dividend tax is still significantly lower than 42% (40% income tax + 2% NI) that would apply to equivalent salary income. However, the margin narrows.",
                    "For directors with total income between £50,270 and £125,140, the optimal question is often about the balance between extracting more dividends (at 33.75%) versus retaining profits in the company (deferring tax, potentially in a lower bracket in a later year, or creating a capital gain on eventual sale which might be taxed at 20% CGT). Employer pension contributions paid by the company are particularly efficient at this level, they reduce corporation tax, create no personal income, and build retirement savings.",
                ],
            },
            {
                "heading": "Self Assessment and Record-Keeping for Directors",
                "paragraphs": [
                    "All directors who receive dividends must file a Self Assessment tax return each year. The dividend income is declared in the UK dividends section of the SA100. The company must formally declare the dividend and issue a dividend voucher, an informal payment of profits without a properly minuted dividend declaration is legally a salary, not a dividend, and will attract NI accordingly.",
                    "The company must also prepare company accounts and file a corporation tax return (CT600) with HMRC. Corporation tax is due nine months and one day after the end of the company's accounting period. The director's personal Self Assessment return is due 31 January following the end of the tax year, 31 January 2028 for 2026/27 income. Keeping these deadlines aligned and ensuring sufficient post-tax profit exists before dividends are declared is essential record-keeping for any director-shareholder.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the optimal director salary for 2026/27?", "a": "Most directors take a salary of £9,100 (no NI for either party, qualifies for State Pension) or £12,570 (uses full Personal Allowance, employer NI of ~£1,136 payable). The optimal level depends on the company's corporation tax rate."},
            {"q": "At what income does the 33.75% dividend rate apply for a director?", "a": "When total income (salary plus dividends) exceeds £50,270. For a director with a £12,570 salary, dividends above £37,700 push income above this threshold and attract 33.75%."},
            {"q": "Is a salary or dividend more tax-efficient for a director?", "a": "A combination of a low salary plus dividends is almost always more efficient than salary alone, because dividends carry no NI. However, the company must pay corporation tax on profits before paying dividends. The full picture requires modelling both company and personal taxes together."},
            {"q": "Does a director need to produce a dividend voucher?", "a": "Yes. Each dividend payment must be accompanied by a dividend voucher showing the company, date, amount per share and tax year. Without proper documentation, HMRC may treat the payment as salary subject to PAYE and NI."},
        ],
    },
    {
        "slug": "dividend-tax-investment-portfolio-2026",
        "title": "Dividend Tax on an Investment Portfolio 2026/27",
        "description": "How dividend tax applies to investors holding shares and funds in a general investment account, and strategies to reduce it using ISAs, pensions and asset location. With 2026/27 rates and worked examples for basic-rate and higher-rate investors.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "9 min read",
        "sections": [
            {
                "heading": "Which Dividends Are Taxable?",
                "paragraphs": [
                    "Dividends from shares or funds held in a general investment account (GIA) outside an ISA or pension are subject to UK dividend tax. This includes dividends from UK-listed shares, international shares held via a UK brokerage, funds and ETFs that distribute income, and REITs (real estate investment trusts) that pay dividends. Dividends inside a Stocks and Shares ISA are completely exempt. Dividends inside a pension (SIPP) are not taxed at the personal level, though the pension fund may suffer irrecoverable withholding tax on foreign holdings.",
                    "The taxable total is the sum of all dividends received from non-ISA, non-pension holdings during the tax year, whether UK or foreign. This gross total is what you report on Self Assessment. The £500 dividend allowance then applies, and the remainder is taxed at 8.75%, 33.75% or 39.35% depending on which band the dividends fall into after your salary and other income has been allocated.",
                ],
            },
            {
                "heading": "Worked Example: Basic-Rate Investor with Mixed Portfolio",
                "paragraphs": [
                    "An investor has a salary of £28,000 and receives the following dividends in 2026/27: £600 from UK equity income ETF held in a GIA, £400 from US S&P 500 fund held in a GIA (after 15% withholding, gross was £471), and £1,200 from a UK equity ISA. Total taxable dividends: £600 + £471 = £1,071 (ISA dividends are excluded). Withholding on the US fund: £71 (15% of £471).",
                    "Dividend allowance: £500 free. Taxable dividends: £571. Both the UK and US dividends fall within the basic-rate band (total income is well below £50,270 at £28,000 + £1,071 = £29,071). Dividend tax at 8.75% on £571 = £49.96. Foreign tax credit for the US withholding (£71): capped at UK tax due of £49.96, so no additional UK tax. Total UK dividend tax on the GIA investments: £0 (withholding exceeds UK liability). The ISA dividend of £1,200: zero tax.",
                    "This investor has a small UK dividend tax bill that is entirely offset by US withholding. They must still file Self Assessment as total dividends from GIA holdings exceed £500. The form SA106 is needed for the foreign dividends.",
                ],
            },
            {
                "heading": "Worked Example: Higher-Rate Investor, Larger Portfolio",
                "paragraphs": [
                    "An investor has a salary of £70,000 and holds £200,000 of dividend-yielding shares in a GIA, yielding 4% = £8,000 in dividends. Salary of £70,000 already exceeds the basic-rate limit, so all dividends fall in the higher-rate band.",
                    "Dividend allowance: £500 free. Taxable dividends: £7,500 at 33.75% = £2,531. The investor also holds £100,000 in a Stocks and Shares ISA yielding 4% = £4,000 in tax-free ISA dividends. If the entire £300,000 was in the GIA, dividend tax would be on £11,500 at 33.75% = £3,881. The ISA shelters £1,350 of annual dividend tax (33.75% × £4,000).",
                    "Over a 20-year investment period, the ISA dividends reinvested without tax compound significantly more than the same dividends taxed at 33.75% each year. Reinvesting £4,000 at 4% over 20 years with no tax versus reinvesting £2,650 (after 33.75% tax) over the same period produces a meaningful difference in terminal wealth, demonstrating why asset location (which assets go inside the ISA) matters for long-term portfolio returns.",
                ],
            },
            {
                "heading": "Which Assets Belong in the ISA?",
                "paragraphs": [
                    "The ISA allowance is £20,000 per year per person. With a fixed annual limit, prioritisation matters. The general principle is to hold the highest-tax-drag investments inside the ISA first. For investors paying dividend tax at 33.75%, high-yield income investments (equity income funds, REITs, bond funds) create the largest annual tax drag and benefit most from ISA shelter. Growth investments with low dividend yields create less annual drag and can sit outside the ISA more comfortably.",
                    "However, growth assets with long holding periods create large eventual capital gains. The ISA eliminates CGT on these gains too. For very long-term holdings, the compounded CGT saving on growth assets inside an ISA can rival or exceed the dividend tax saving from income assets. Most financial planners suggest holding the highest total-return assets inside the ISA first, which often means high-dividend income funds for higher-rate taxpayers, and high-growth assets for basic-rate taxpayers whose dividend tax drag is modest.",
                ],
            },
            {
                "heading": "Pension Contributions as a Dividend Tax Lever",
                "paragraphs": [
                    "For investors close to the higher-rate threshold (£50,270), pension contributions can shift dividend income from the 33.75% band back into the 8.75% band. A salary of £52,000 with £3,000 of dividends would normally have all dividends in the higher-rate band. A £2,000 pension contribution reduces adjusted net income to £50,000, keeping dividends in the basic-rate band.",
                    "The annual allowance for pension contributions in 2026/27 is £60,000 (subject to the tapered allowance for high earners). This gives most investors substantial scope to make contributions that both reduce dividend tax and build retirement savings. The pension contribution itself receives income tax relief, at 40% for higher-rate taxpayers, making the combined benefit of dividend tax reduction and contribution relief significant.",
                ],
            },
        ],
        "faqs": [
            {"q": "Do I pay dividend tax on all shares outside an ISA?", "a": "Yes. Dividends from shares or funds held in a general investment account are subject to UK dividend tax above the £500 annual allowance. Dividends inside an ISA or pension are exempt."},
            {"q": "How do I reduce dividend tax on my investment portfolio?", "a": "Use a Stocks and Shares ISA (£20,000 annual allowance per person) to hold dividend-producing investments. For higher-rate taxpayers, prioritising high-yield income funds inside the ISA gives the largest annual tax saving. Pension contributions can also reduce total income below the higher-rate threshold."},
            {"q": "Do I need to file Self Assessment for portfolio dividends?", "a": "Yes, if total dividends from GIA holdings exceed £500 in a tax year. You report UK dividends on the SA100 and foreign dividends on the SA106 supplementary pages."},
        ],
    },
    {
        "slug": "dividend-tax-pension-contributions-2026",
        "title": "Pension Contributions to Reduce Dividend Tax 2026/27",
        "description": "Making pension contributions reduces your adjusted net income, which can shift dividends from the 33.75% higher-rate band to the 8.75% basic-rate band, saving 25 percentage points. This guide shows exactly how to calculate the saving, with worked examples for employees, investors and directors.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "8 min read",
        "sections": [
            {
                "heading": "How Pension Contributions Interact with Dividend Tax",
                "paragraphs": [
                    "Pension contributions reduce your adjusted net income, the figure HMRC uses to determine which income tax bands apply. For the purpose of dividend tax, this means a pension contribution can move income below the higher-rate threshold (£50,270), shifting dividends from the 33.75% higher-rate band back into the 8.75% basic-rate band. The saving is 25 percentage points on every pound of dividends that changes band.",
                    "The mechanism works through relief at source contributions (personal pensions, SIPPs) and net pay contributions (workplace pensions). For relief-at-source schemes, you contribute net of basic-rate tax and the pension provider claims basic-rate relief. You then claim higher-rate relief through Self Assessment. For net-pay schemes, contributions are deducted before tax is calculated, so the full relief is immediate. Either way, the adjusted net income figure is reduced by the gross contribution amount.",
                ],
            },
            {
                "heading": "The Calculation: How Much to Contribute",
                "paragraphs": [
                    "To calculate the pension contribution needed to shift a specific amount of dividends from higher rate to basic rate, subtract the basic-rate limit (£50,270) from your total income. The result is the amount of income in the higher-rate band. A contribution equal to that amount would bring your adjusted net income back to exactly £50,270.",
                    "However, be precise about what counts as income. Adjusted net income is not the same as gross income. It is gross income minus pension contributions minus other deductions. For most individuals, the relevant figure is: salary + dividends + any other taxable income, minus pension contributions. The dividend tax calculation then uses this net figure to determine the bands.",
                ],
            },
            {
                "heading": "Worked Example 1: Employee with Investment Portfolio",
                "paragraphs": [
                    "An employee earns a salary of £52,000 and receives £6,000 of dividends from a GIA. Total income: £58,000. Salary of £52,000 exceeds the basic-rate limit. All dividends fall in the higher-rate band.",
                    "Without pension contribution: dividend tax on £5,500 (after £500 allowance) at 33.75% = £1,856. With a £7,730 gross pension contribution: adjusted net income = £58,000 − £7,730 = £50,270, exactly at the basic-rate limit. All dividends now fall in the basic-rate band. Dividend tax on £5,500 at 8.75% = £481. Saving: £1,856 − £481 = £1,375. The pension contribution also attracts higher-rate income tax relief of 20% on the £7,730 (beyond the basic-rate relief already given at source) = £1,546. Total combined benefit: £1,375 dividend tax saving + £1,546 pension relief = £2,921 in tax savings from a £7,730 contribution.",
                ],
            },
            {
                "heading": "Worked Example 2: Company Director",
                "paragraphs": [
                    "A director has a salary of £12,570 and dividends of £45,000. Total income: £57,570. After the Personal Allowance and basic-rate band, approximately £7,300 of dividends fall in the higher-rate band at 33.75% (the amount by which total income exceeds £50,270).",
                    "The director instructs the company to make an employer pension contribution of £7,300 on their behalf. This contribution: reduces corporation tax (it is a deductible company expense), does not appear as the director's personal income at all, and does not count against any personal pension annual allowance for contribution limits. Result: the director's personal income is unchanged at £57,570, but the company's contribution effectively shelters the top £7,300 from personal dividend tax. The saving on the director's personal dividend tax bill: £7,300 × (33.75% − 8.75%) = £7,300 × 25% = £1,825. The corporation tax saving on the employer contribution (at 25% rate): £7,300 × 25% = £1,825. Combined benefit: £3,650 from a £7,300 employer pension contribution.",
                ],
            },
            {
                "heading": "The Annual Allowance, Know the Limits",
                "paragraphs": [
                    "The annual pension contribution allowance for 2026/27 is £60,000 for most individuals, covering both personal and employer contributions combined. This is subject to the tapered annual allowance for high earners: once adjusted income (gross income plus employer contributions) exceeds £260,000, the allowance tapers down by £1 for every £2 above that level, to a minimum of £10,000.",
                    "For most directors and employees with total income below £260,000, the full £60,000 allowance is available. This means substantial scope exists for pension contributions to reduce dividend tax. Contributions can also be made using unused allowances from the previous three tax years under the carry-forward rules, allowing catch-up contributions for those who did not fully use their allowance in recent years.",
                ],
            },
            {
                "heading": "Personal Allowance Restoration Above £100,000",
                "paragraphs": [
                    "If total income exceeds £100,000, the Personal Allowance (£12,570) is gradually withdrawn at £1 for every £2 of income above £100,000. It is fully withdrawn at £125,140. The effective marginal rate in the £100,000–£125,140 range is very high, income in this band effectively faces a 60% marginal rate on earned income as the Personal Allowance disappears.",
                    "Pension contributions that reduce adjusted net income back below £100,000 can restore the full Personal Allowance. For a director or investor with income in this range, the combined benefit of pension contributions is: income tax at the relevant rate, the Personal Allowance restoration effect, and the dividend tax band reduction if dividends are involved. A qualified financial planner or accountant is strongly advisable for anyone in this income range.",
                ],
            },
        ],
        "faqs": [
            {"q": "Can pension contributions reduce my dividend tax rate from 33.75% to 8.75%?", "a": "Yes, if the contribution reduces your adjusted net income below the higher-rate threshold of £50,270. Every pound of dividends that moves from the higher-rate band to the basic-rate band saves 25 percentage points of dividend tax."},
            {"q": "Are employer pension contributions (paid by my company) as effective as personal contributions?", "a": "More so, in many respects. Employer contributions reduce corporation tax, do not appear as personal income, and do not affect dividend tax thresholds directly. They are one of the most efficient ways for a director to reduce both personal and company-level tax simultaneously."},
            {"q": "What is the pension annual allowance for 2026/27?", "a": "£60,000 for most individuals (personal plus employer contributions combined). The tapered allowance reduces this for individuals with adjusted income above £260,000. Unused allowances from the previous three years can be carried forward."},
        ],
    },
    {
        "slug": "salary-vs-dividends-director-2026",
        "title": "Salary vs Dividends: Optimal Split for Company Directors 2026/27",
        "description": "The optimal director salary in 2026/27 is £9,100 (no NI) or £12,570 (full personal allowance). Dividends from post-tax profits are taxed at 8.75% basic rate. This guide shows the full worked example: taking £90,000 from a limited company, comparing salary-only vs the optimal salary-plus-dividend split.",
        "date_iso": "2026-05-27",
        "date": "May 2026",
        "reading_time": "10 min read",
        "sections": [
            {
                "heading": "Why Directors Choose Salary Plus Dividends",
                "paragraphs": [
                    "A sole-director limited company owner typically extracts income through a combination of salary and dividends rather than salary alone. The reason is straightforward: salary above the National Insurance thresholds attracts employer NI at 15% (from the company) and employee NI at 8% (from the director personally). Dividends, paid from post-corporation-tax profits, attract no National Insurance at all. Dividend tax rates are also lower than income tax rates on salary: 8.75% basic rate versus 20% income tax, and 33.75% higher rate versus 40% income tax.",
                    "The trade-off is that the company must first pay corporation tax on its profits before any dividends can be distributed. Salary, by contrast, is deductible as a business expense and reduces the profits on which corporation tax is charged. The optimal salary level sits at the point where the corporation tax saving from the salary deduction exactly offsets (or exceeds) the personal NI cost of paying the salary. For 2026/27, this analysis points to two main salary strategies.",
                ],
            },
            {
                "heading": "Optimal Salary Options for 2026/27",
                "paragraphs": [
                    "Option 1, £9,100 salary (lower earnings limit): At this level, the director pays no employee NI and the company pays no employer NI. The salary qualifies as a deductible expense, saving the company corporation tax at 19% or 25% on the amount deducted. No income tax is payable on the salary (well below the £12,570 Personal Allowance). The director also accrues a qualifying year for State Pension purposes. This is often the preferred option for directors who want to eliminate NI entirely.",
                    "Option 2, £12,570 salary (Personal Allowance): This fully utilises the Personal Allowance, so no income tax is paid on the salary. However, salary above the secondary NI threshold (approximately £5,000 for employers from April 2026) attracts employer NI at 15%. On the portion from £5,000 to £12,570 = £7,570, employer NI = £7,570 × 15% = £1,136. This £1,136 is itself deductible for corporation tax, so the net cost to the company at the main 25% rate is £1,136 × (1 − 0.25) = £852. For many directors at the main corporation tax rate, the extra personal allowance saving (no income tax on an extra £3,470 of salary compared to the £9,100 option) makes this worthwhile. At the small company 19% rate, the calculus is closer.",
                    "Above £12,570, salary becomes increasingly inefficient. Employee NI at 8% kicks in, and both employee and employer NI are payable. Taking income as dividends above this point is almost always more tax-efficient.",
                ],
            },
            {
                "heading": "Corporation Tax: The Company-Side Cost",
                "paragraphs": [
                    "For 2026/27, corporation tax is 19% on profits up to £50,000, 25% on profits above £250,000, and subject to marginal relief on profits between £50,000 and £250,000. Dividends are paid from post-tax profit, so a company earning £100,000 of profit pays £25,000 corporation tax (at the main rate) and has £75,000 available for dividends. If the director wants £60,000 of dividends, the company must have generated at least £80,000 of profit to cover both the tax and the dividend.",
                    "This is the key reason why salary and dividends are not directly comparable without modelling the company-level position. Salary reduces corporation tax; dividends do not. A £1 of salary costs the company £1 (minus the corporation tax saving), while a £1 of dividend requires approximately £1.33 of pre-tax profit at the 25% rate.",
                ],
            },
            {
                "heading": "Worked Example: Taking £90,000 from a Limited Company",
                "paragraphs": [
                    "Scenario: A sole director owns a limited company. The company earns £140,000 of profit before the director's remuneration. The director wants to extract £90,000 of personal income. Two options are compared: all salary versus optimal salary-plus-dividend split.",
                    "Option A, All salary, £90,000: The company deducts £90,000 as a salary expense. Employer NI at 15% on salary above £5,000 = (£90,000 − £5,000) × 15% = £12,750 (also deductible). Company taxable profit after remuneration: £140,000 − £90,000 − £12,750 = £37,250. Corporation tax at 19% = £7,078. Director receives £90,000 salary. Income tax: 20% on (£90,000 − £12,570) = 20% × £77,430 = £15,486; 40% on (£90,000 − £50,270) = 40% × £39,730 = £15,892. Employee NI: 8% on (£50,270 − £12,570) = £3,016; 2% on (£90,000 − £50,270) = £794. Director's total personal tax: £15,486 + £15,892 + £3,016 + £794 = £35,188. Total tax (company + personal): £7,078 + £35,188 + £12,750 employer NI = £55,016.",
                    "Option B, £12,570 salary + £77,430 dividends: Salary £12,570; employer NI on £7,570 × 15% = £1,136 (deductible). Company taxable profit: £140,000 − £12,570 − £1,136 = £126,294. Corporation tax at 25% (with marginal relief consideration, broadly 25% on profits above £250k but marginal relief applies here): at £126,294 profit, marginal relief applies. Approximate corporation tax using effective marginal rate of ~26.5% = around £33,468. Post-tax profit available for dividends: £126,294 − £33,468 = £92,826. Dividend declared: £77,430. Director's personal tax: income tax on salary = nil (covered by Personal Allowance). Dividend tax: £500 allowance free, remaining basic-rate band = £50,270 − £12,570 = £37,700. Taxable dividends: £77,430 − £500 = £76,930. Basic-rate tax: 8.75% × £37,700 = £3,299. Higher-rate tax: 33.75% × (£76,930 − £37,700) = 33.75% × £39,230 = £13,240. Director's total personal tax: £3,299 + £13,240 = £16,539. Total tax (company + personal): £33,468 + £16,539 + £1,136 employer NI = £51,143. Saving versus Option A: approximately £3,873.",
                    "The salary-plus-dividend structure saves around £3,900 in this scenario. The saving is larger at lower income levels (where more dividends fall in the 8.75% basic-rate band rather than the 33.75% higher-rate band) and can exceed £10,000 per year for directors whose total income stays below £50,270.",
                ],
            },
            {
                "heading": "Employer NI from April 2026",
                "paragraphs": [
                    "From April 2026, employer National Insurance is 15% on salary above the secondary threshold (approximately £5,000). This rate increased from 13.8% in April 2025 as part of the government's employer NI changes. The higher employer NI rate makes low salary strategies more attractive: the cost of paying salary above the secondary threshold has increased, strengthening the case for minimising salary and maximising dividends.",
                    "Directors should model this using the current 15% employer NI rate for 2026/27. The secondary threshold of approximately £5,000 means no employer NI is payable on salary up to this amount, making the £5,000–£9,100 salary range effectively free of employer NI. Above £9,100, employer NI accrues at 15% on each additional pound of salary.",
                ],
            },
        ],
        "faqs": [
            {"q": "What is the optimal director salary for 2026/27?", "a": "Most directors take £9,100 (no NI for either party, accrues State Pension credit) or £12,570 (uses full Personal Allowance, employer NI of ~£1,136 applies). The best choice depends on the company's corporation tax rate."},
            {"q": "How much can a director take as dividends before higher-rate tax applies?", "a": "For a director with a £12,570 salary, dividends above the £500 allowance up to a total income of £50,270 are taxed at 8.75% (basic rate). That means approximately £37,200 of dividends can be taken at the lower rate before 33.75% applies."},
            {"q": "Does the company pay tax before paying dividends?", "a": "Yes. Corporation tax is paid on company profits before dividends are declared. At the main rate of 25%, a company must earn approximately £1.33 of pre-tax profit to distribute £1 as a dividend after corporation tax."},
            {"q": "Is salary or dividends better for a company director in 2026/27?", "a": "A combination is almost always more efficient than salary alone. The salary-plus-dividend structure avoids NI on the dividend portion and benefits from lower dividend tax rates (8.75% basic vs 20% income tax). The exact saving depends on total income level."},
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
            {"url": "https://www.gov.uk/guidance/rates-and-allowances-income-tax", "label": "HMRC: Rates and allowances, Income Tax"},
        ],
    ))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
