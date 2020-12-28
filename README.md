# Google Scholar alert parser

A tool to parse emails from Google-Scholar 

# Requirements

* Python3

# How it works

* The script connects to your e-mail server via IMAP, using STARTTLS.
* Opens your inbox and scans all e-mail subjects for google-scholar keywords, e.g., "new citations".
* E-mail with matching subjects are opened and parsed for links to papers and their titles.
* Parsed e-mails (with matching subjects) are moved to the trash folder.
* A list of papers (title;link) from all parsed e-mails is generated and stored ("papers.csv") on disk.
* "papers.csv" is read at start to populate the list of papers.
* Existing titles are not added again to the list.

# Before you start

* You have to adapt `mail_settings.py` and provide the credentials and the URL to your e-mail account.

# How to start

* `python3 check_email.py`

# Issues

* Recommendations of patents are not added to the list (on purpose). This feature might not work correctly.
* Keywords for e-mail subjects are in English and German. Other languages may be added to "SUBJECT_WHITELIST".
* User credentials are stored in "mail_settings.py" in clear text.
* Only Starttls is currently implemented.
* Used imap folders (Inbox, Inbox.trash) are hard coded.
