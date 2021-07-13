#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: nlp

:Synopsis: Normalize text using Natural Language Processing library

:Author:
    ide

:Created:
    7/7/21
"""

import textacy.preprocessing as tprep


def normalize(text):
    text = tprep.normalize.hyphenated_words(text)
    text = tprep.normalize.quotation_marks(text)
    text = tprep.normalize.unicode(text)
    text = tprep.remove.accents(text)
    return text


if __name__ == '__main__':
    pass