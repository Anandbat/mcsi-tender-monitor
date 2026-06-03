from . import tendergov, adb, worldbank, ebrd, energygov
# otmn removed — last public data was June 2024, moved to SAP Ariba (login required)

ALL_SCRAPERS = [
    ("tender.gov.mn",  tendergov.scrape),
    ("ADB",            adb.scrape),
    ("World Bank",     worldbank.scrape),
    ("EBRD",           ebrd.scrape),
    ("Energy.gov.mn",  energygov.scrape),
]
