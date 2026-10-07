"""Paragraph cross-references, shared by normalize (dashes) and build (links).

A list counts as references only in parentheses on its own or after "paragraph(s)"
or "Manual", which keeps dates, the salary tables and "30-180 days" out. A lone one-
or two-digit number in parentheses followed by a word is an inline enumeration, not
a reference: "namely (1) active and (2) inactive". A longer one is a reference even
mid-sentence: "not incorporated civilly (102) may officiate".
"""
import re

PNUM = r'\d+(?:\.\d+)*'
PREF = r'%s(?:\s*[-–—]\s*%s)?' % (PNUM, PNUM)
PLIST = r'%s(?:\s*(?:[,;]|,? or|,? and)\s*%s)*' % (PREF, PREF)
PARA_CITATION = re.compile(r'(?<=\()(?!\d{1,2}\)\s*[a-z])%s(?=\))|(?:(?<=paragraphs )|'
                           r'(?<=paragraph )|(?<=Manual )|(?<=Manual</em> ))%s' % (PLIST, PLIST))
PARA_ITEM = re.compile(PREF)
PARA_FIRST = re.compile(PNUM)
PARA_RANGE = re.compile(r'(%s)\s*[-–—]\s*(%s)' % (PNUM, PNUM))
