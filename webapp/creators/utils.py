#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: utils

:Synopsis: Miscellaneous utility functions

:Author:
    ide

:Created:
    6/1/21
"""

from datetime import datetime
import re


def time_format():
    return f'{datetime.now().strftime("%H:%M:%S")}|> '


def trim_orcid(s):
    # The orcid field may have forms like:
    #   https://orcid.org/0000-0002-9312-7910
    #   http://orcid.org/0000-0002-1017-9599
    #   tjass
    #   egoldstein http://orcid.org/0000-0001-9358-1016
    #   orcid.org/0000-0001-8592-1316
    # etc.
    # We want just the ORCID ID part, e.g.,
    #   0000-0002-9312-7910
    p = re.compile('\d{4}-\d{4}-\d{4}-(\d{3}X|\d{4})')
    m = p.search(s.upper())
    if m:
        x = m.span()
        return (s[x[0]:x[1]]).upper()
    else:
        return ''
