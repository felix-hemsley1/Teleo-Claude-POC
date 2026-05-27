"""Static deny lists and PII patterns used by the redaction layer."""

DENY_LIST_PROCESSES = {
    "1password.exe", "1passwordapp.exe",
    "bitwarden.exe", "bitwarden-desktop.exe",
    "keepass.exe", "keepassxc.exe",
    "mstsc.exe",
    "credentialuibroker.exe",
    "lockapp.exe",
}

DENY_LIST_URL_PATTERNS = [
    r"chase\.com", r"bankofamerica\.com", r"wellsfargo\.com",
    r"hsbc\.com", r"barclays\.co\.uk", r"natwest\.com",
    r"paypal\.com/myaccount", r"venmo\.com",
]

PII_PATTERNS = {
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
}
