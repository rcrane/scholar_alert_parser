#!/usr/bin/env python3

from lxml import etree
import html
from email.message import EmailMessage
import imaplib
import email
from mail_settings import *


BLACKLIST=[ \
    "Save", "email_library_add", "scholar_share", \
    "cancel_alert", "Facebook", "Twitter", \
    "This alert is sent by Google Scholar", "Cancel alert" \
    ]

SUBJECT_WHITELIST=[ \
    "new citations", "new results", "neue Zitate", \
    "new related research", "neue Ergebnisse", \
    "new articles", "new citation", "neue Zitationen", \
    "neue Zitation", "neue_Ergebnisse", "neue_Zitationen" \
    ]

def check_blacklist(arg: str):
    for b in BLACKLIST:
        if b in arg:
            return True
    
    return False

def check_subject_whitelist(arg: str):
    for b in SUBJECT_WHITELIST:
        if b in arg:
            return True
    
    return False


def parse_plain_body(msg):
    title = ""
    title_start = False
    link = ""
    ret = {}
   
    msg = msg.splitlines()
    checkforpatent = False

    for i in range(0, len(msg)):
        if not msg[i]:
            continue
        
        if check_blacklist(msg[i]):
            continue

        l = msg[i].strip()

        if l.startswith("<htt"):  
            if "patent" in l:
                # Not interested it patents
                continue

            link = l.replace("http://scholar.google.de/scholar_url?url=","").replace("<","").replace(">","").split(".pdf")[0] + ".pdf"
            if "&hl" in link:
                link = link.split("&hl")[0]
            title = msg[i-3].strip() + " " + msg[i-2].strip() + " " + msg[i-1].strip()
            title = title.strip().strip("[PDF]").strip()
            title = title.strip().strip("[HTML]").strip()
            ret[title] = link
            checkforpatent = True
       
        # TODO: check for "patent" in text after link, in case link url didn't contain "patent"


    #print(ret)
    return ret

def fetch_title_link_from_elements(element):
    
    return_list = []
    text = str(etree.tostring(element, pretty_print=True, method="html").decode()) 

    if text.startswith("<a href="):

        if "patent" not in text and "email_library_add" not in text and "scholar_share" not in text  and "cancel_alert_options" not in text :
           
            text = str(etree.tostring(element, pretty_print=True, method="html").decode()) + str(element.tail)
            text = html.unescape(text.replace("&#13;","").replace("\n","").replace("&#160;"," ").replace("\r"," "))
        
            title = text.split(">")[1].split("<")[0].strip()
            link = text.split(" ")[1].replace("href=","")
            if "scholar_url?url=" in text:
                link = link.split("scholar_url?url=")[1]
                link = link.split(".pdf")[0] + ".pdf"   
                link = link.split("&")[0] 
            return [[title, link]]
    
    # TODO: check for "patent" in text after link, in case link url didn't contain "patent"

    if len(element) > 0:
        for e in element:
            #print(str(etree.tostring(e)), len(e))
            return_list.extend(fetch_title_link_from_elements(e))
    
    return return_list

def parse_html_body(msg):

    parser = etree.HTMLParser(recover=True)
    hl = etree.HTML(msg, parser)
    ret = {}     
    titles = []

    for element in hl.iter('a'):
        # TODO: iter also returns img tags
        titles.extend(fetch_title_link_from_elements(element))
    
    for i in titles:
        ret[i[0]] = i[1]
    
    #print(ret)
    return ret


def scan_email_starttls():
    M = imaplib.IMAP4(host=MAIL_HOST, port=MAIL_PORT_IN)
    mydata = {}

    try:
        f = open('workfile', 'r')
        for l in f.readlines():
            mydata[l.split(";")[0]] = l.split(";")[1].replace("\n","")
        f.close
    finally:
        try:
            f.close()
        except:
            pass



    doubles = 0
    try:    
        M.starttls()
        typ, data = M.login(MAIL_USER, MAIL_PASS)
        if "OK" != str(typ):
            print("Login: " + str(typ))
            exit(-1)

        typ, data = M.select('inbox')
        if "OK" != str(typ):
            print("Select inbox: " + str(typ))
            exit(-2)

        typ, data = M.uid('search', None, "ALL")
        if "OK" != str(typ):
            print("Get all messages: " + str(typ))
            exit(-3)

        liste = data[0].split()
        total = len(liste)
        for num in reversed(liste):
            print("E-Mails left: " + str(total) + "       ", end='\r')
            total = total - 1
            
            typ, data = M.uid('fetch', num, '(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT)])')
            if "OK" != str(typ):
                print("Get Subject: " + str(typ))
                exit(-4)

            subject = email.header.decode_header(str(data[0][1],'utf-8'))
            if len(subject) == 1:
                subject = (subject[0][0]).replace("\r","").replace("\n","").replace("\xa0"," ")
            elif len(subject) > 1:
                subject = str(subject[1][0],subject[1][1]).replace("\r","").replace("\n","").replace("\xa0"," ")
            
            # get subject from raw data
            #elif not subject:
            #    subject = str(data[0][1],subject[1][1]).replace("\r","").replace("\n","").replace("\xa0"," ")
            
            if check_subject_whitelist(subject):
           
                #print(subject)
                #typ, data = M.fetch(num, '(UID BODY[TEXT])')
                typ, data = M.uid('fetch', num, '(RFC822)')
                if data[0]:
                    msg = email.message_from_bytes((data[0][1]))
                    
                    if "text/plain" == str(msg.get_content_type()):
                        for k,v in parse_plain_body(msg.get_payload()).items():
                            if k in mydata.keys():
                                doubles = doubles + 1
                                
                            mydata[k] = v 
                    elif "multipart" == str(msg.get_content_maintype()):
                        for part in msg.walk():
                            if "text/html" == str(part.get_content_type()):
                                for k,v in parse_html_body(part.get_payload(decode=True)).items():
                                    if k in mydata.keys():
                                        doubles = doubles + 1
                                        
                                    mydata[k] = v 
                                break

                
                    # Copy mail to trash and then delete it from inbox
                    typ, data = M.uid('COPY', num, 'INBOX.Trash')
                    typ, data = M.uid('STORE', num, '+FLAGS', '\\Deleted') 
                    M.expunge()
                                      
            
    
    finally:
        try:
            M.close()
        except:
            pass
            M.logout()

    f = open('workfile', 'w')
    for k,v in mydata.items():
        f.write(str(k) + ";" + str(v) + "\n")
    f.close

    print("\n" + str(doubles) + " doubles found!")

    


if __name__ == "__main__":
    if not MAIL_HOST:
        print("MAIL_HOST not set in mail_setting.py!")
        exit()
    if not MAIL_USER:
        print("MAIL_USER not set in mail_setting.py!")
        exit()
    if not MAIL_PASS:
        print("MAIL_PASS not set in mail_setting.py!")
        exit()
        
    scan_email_starttls()