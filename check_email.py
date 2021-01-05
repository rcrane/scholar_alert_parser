#!/usr/bin/env python3
'''A tool to parse emails from Google-Scholar.'''

from lxml import etree
import html
import imaplib
from email import header
import email
from socket import gaierror
from mail_settings import MAIL_HOST, MAIL_PORT_IN, MAIL_USER, MAIL_PASS


BLACKLIST = [
    "Save", "email_library_add", "scholar_share",
    "cancel_alert", "Facebook", "Twitter",
    "This alert is sent by Google Scholar", "Cancel alert"
    ]

SUBJECT_WHITELIST = [
    "new citations", "new results", "neue Zitate",
    "new related research", "neue Ergebnisse",
    "new articles", "new citation", "neue Zitationen",
    "neue Zitation", "neue_Ergebnisse", "neue_Zitationen"
    ]


def check_blacklist(arg: str):
    '''Check if arg contains a keyword from the blacklist.
       Returns True if keyword is found, False otherwise'''

    for word in BLACKLIST:
        if word in arg:
            return True

    return False


def check_subject_whitelist(arg: str):
    '''Check if arg contains a keyword from the subject_whitelist.
       Returns True if keyword is found, False otherwise'''

    for word in SUBJECT_WHITELIST:
        if word in arg:
            return True

    return False


def parse_plain_body(msg):
    '''Parse plain-text e-mail messages.
       Returns a set containing title:link entries'''

    title = ""
    link = ""
    ret = {}

    msg = msg.splitlines()

    for i in range(0, len(msg)):
        if not msg[i]:
            continue

        if check_blacklist(msg[i]):
            continue

        line = msg[i].strip()

        if line.startswith("<htt"):
            if "patent" in line:
                # Not interested in patents
                continue

            link = line.replace("http://scholar.google.de/scholar_url?url=", "").replace("<", "").replace(">", "").split(".pdf")[0] + ".pdf"
            if "&hl" in link:
                link = link.split("&hl")[0]
            title = msg[i-3].strip() + " " + msg[i-2].strip() + " " + msg[i-1].strip()
            title = title.strip().strip("[PDF]").strip()
            title = title.strip().strip("[HTML]").strip()
            ret[title] = link

        # TODO: check for "patent" in text after link, in case link url didn't contain "patent"

    # print(ret)
    return ret


def fetch_title_link_from_elements(element):
    '''Parse an html element and extract a paper title and link from <a> tags.
       Returns a list with title,link pairs'''

    return_list = []
    text = str(etree.tostring(element, pretty_print=True, method="html").decode())

    if text.startswith("<a href="):

        if "patent" not in text and "email_library_add" not in text \
          and "scholar_share" not in text and "cancel_alert_options" not in text:

            text = str(etree.tostring(element, pretty_print=True, method="html").decode()) + str(element.tail)
            text = html.unescape(text.replace("&#13;", "").replace("\n", "").replace("&#160;", " ").replace("\r", " "))

            title = text.split(">")[1].split("<")[0].strip()
            link = text.split(" ")[1].replace("href=", "")
            if "scholar_url?url=" in text:
                link = link.split("scholar_url?url=")[1]
                link = link.split(".pdf")[0] + ".pdf"
                link = link.split("&")[0]
            return [[title, link]]

    # TODO: check for "patent" in text after link, in case link url didn't contain "patent"

    if len(element) > 0:
        for child in element:
            # print(str(etree.tostring(e)), len(e))
            return_list.extend(fetch_title_link_from_elements(child))

    return return_list


def parse_html_body(msg):
    '''Parse html e-mail messages.
       Returns a set containing title:link entries'''

    parser = etree.HTMLParser(recover=True)
    html_tree = etree.HTML(msg, parser)
    ret = {}
    titles = []

    for element in html_tree.iter('a'):
        # TODO: iter also returns img tags
        titles.extend(fetch_title_link_from_elements(element))

    for i in titles:
        ret[i[0]] = i[1]

    # print(ret)
    return ret


def scan_email_starttls():
    '''Establishes an IMAP connection and scans for e-mails with subjects of interest.
       E-Mails are parsed for paper titles and links.
       A list of paper titles and links is stored in a csv file.'''

    try:
        mail_client = imaplib.IMAP4(host=MAIL_HOST, port=MAIL_PORT_IN)
    except ConnectionRefusedError:
        print("The server did not accept the connection request!\nCheck if MAIL_PORT_IN is correct.")
        exit(-5)
    except gaierror:
        print("The server did not accept the connection request!\nCheck if MAIL_HOST is correct.")
        exit(-5)

    papers = {}

    try:
        paper_file = open('papers.csv', 'r')
        for line in paper_file.readlines():
            papers[line.split(";")[0]] = line.split(";")[1].replace("\n", "")
        paper_file.close
    except FileNotFoundError:
        print("papers.csv does not exist.")

    doubles = 0

    print("Loaded " + str(len(papers)) + " papers from papers.csv")

    mail_client.starttls()
    try:
        typ, data = mail_client.login(MAIL_USER, MAIL_PASS)
    except imaplib.IMAP4.error:
        print("Login failed.\nCheck if MAIL_USER and MAIL_PASS are correct.")
        exit(-5)
    if "OK" != str(typ):
        print("Login: " + str(typ))
        exit(-1)

    typ, data = mail_client.select('inbox')
    if "OK" != str(typ):
        print("Select inbox: " + str(typ))
        exit(-2)

    typ, data = mail_client.uid('search', None, "ALL")
    if "OK" != str(typ):
        print("Search for messages: " + str(typ))
        exit(-3)

    liste = data[0].split()
    total = len(liste)
    print("Found " + str(total) + " E-Mails")
    for num in reversed(liste):

        typ, data = mail_client.uid('fetch', num, '(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT)])')
        if "OK" != str(typ):
            print("Get Subject: " + str(typ))
            exit(-4)

        subject = email.header.decode_header(str(data[0][1], 'utf-8'))
        if len(subject) == 1:
            subject = (subject[0][0]).replace("\r", "").replace("\n", "").replace("\xa0", " ")
        elif len(subject) > 1:
            subject = str(subject[1][0], subject[1][1]).replace("\r", "").replace("\n", "").replace("\xa0", " ")

        # get subject from raw data
        # elif not subject:
        #    subject = str(data[0][1],subject[1][1]).replace("\r","").replace("\n","").replace("\xa0"," ")

        if check_subject_whitelist(subject):

            # print(subject)
            typ, data = mail_client.uid('fetch', num, '(RFC822)')
            if data[0]:
                msg = email.message_from_bytes((data[0][1]))

                if "text/plain" == str(msg.get_content_type()):
                    for key, val in parse_plain_body(msg.get_payload()).items():
                        if key in papers.keys():
                            doubles = doubles + 1

                        papers[key] = val
                elif "multipart" == str(msg.get_content_maintype()):
                    for part in msg.walk():
                        if "text/html" == str(part.get_content_type()):
                            for key, val in parse_html_body(part.get_payload(decode=True)).items():
                                if key in papers.keys():
                                    doubles = doubles + 1

                                papers[key] = val
                            break

                # Copy mail to trash and then delete it from inbox
                typ, data = mail_client.uid('COPY', num, 'INBOX.Trash')
                typ, data = mail_client.uid('STORE', num, '+FLAGS', '\\Deleted')
                mail_client.expunge()

        total = total - 1
        print("E-Mails left: " + str(total) + "       ", end='\r')

    print("A total of " + str(len(papers)) + " papers now listed.\n" + str(doubles) + " papers where already present in papers.csv.\nWriting to disk (papers.csv).")

    paper_file = open('papers.csv', 'w')
    for key, val in papers.items():
        paper_file.write(str(key) + ";" + str(val) + "\n")
    paper_file.close


if __name__ == "__main__":
    if not MAIL_HOST:
        print("MAIL_HOST not set in mail_settings.py!")
        exit()
    if not MAIL_USER:
        print("MAIL_USER not set in mail_settings.py!")
        exit()
    if not MAIL_PASS:
        print("MAIL_PASS not set in mail_settings.py!")
        exit()

    scan_email_starttls()
