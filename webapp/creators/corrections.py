#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: corrections

:Synopsis:
    Read in the various corrections files in XML format:
        NICKNAMES_FILE = 'corrections_nicknames.xml'
        ORCID_CORRECTIONS_FILE = 'corrections_orcids.xml'
        ORGANIZATIONS_FILE = 'organizations.xml'
        OVERRIDES_FILE = 'corrections_overrides.xml'
        PERSON_VARIANTS_FILE = 'corrections_name_variants.xml'

:Author:
    ide

:Created:
    6/1/21
"""
from lxml import etree

from config import Config


class Override:
    def __init__(self, original_surname, original_givenname, surname, givenname, scope, _original_surname_raw=None):
        self._original_surname = original_surname
        self._original_givenname = original_givenname
        self._surname = surname
        self._givenname = givenname
        self._scope = scope
        self._original_surname_raw = _original_surname_raw

    def __repr__(self):
        return f'{self.original_surname}, {self.original_givenname} -> {self.surname}, {self.givenname} - {self.scope}'

    @property
    def original_surname(self):
        return self._original_surname

    @property
    def original_givenname(self):
        return self._original_givenname

    @property
    def surname(self):
        return self._surname

    @property
    def givenname(self):
        return self._givenname

    @property
    def scope(self):
        return self._scope

    @property
    def original_surname_raw(self):
        return self._original_surname_raw


class PersonVariant:
    def __init__(self, surname, givenname, scope):
        self._surname = surname
        self._givenname = givenname
        self._scope = scope

    def __repr__(self):
        return f'{self.surname}, {self.givenname} - {self.scope}'

    @property
    def surname(self):
        return self._surname

    @property
    def givenname(self):
        return self._givenname

    @property
    def scope(self):
        return self._scope

    def __hash__(self):
        return hash((self.surname, self.givenname, self.scope))

    def __eq__(self, other):
        return (self.surname, self.givenname, self.scope) == (other.surname, other.givenname, other.scope)


class Person:
    def __init__(self, variants, comment):
        self._variants = variants
        self._comment = comment

    def __repr__(self):
        return f'{self.variants} - {self.comment if self.comment else ""}'

    @property
    def variants(self):
        return self._variants

    @property
    def comment(self):
        return self._comment


class ORCIDCorrection:
    def __init__(self, type, surname, givenname, orcid):
        self._type = type
        self._surname = surname
        self._givenname = givenname
        self._orcid = orcid

    def __repr__(self):
        return f'{self.surname}, {self.givenname} - {self.orcid}  ({self.type})'

    @property
    def surname(self):
        return self._surname

    @property
    def givenname(self):
        return self._givenname

    @property
    def orcid(self):
        return self._orcid

    @property
    def type(self):
        return self._type


def init_person_variants():
    with open(f'{Config.DATA_FILES_PATH}/{Config.PERSON_VARIANTS_FILE}', 'r') as variants_file:
        xml = variants_file.read()

    persons = []
    root = etree.fromstring(xml.encode("utf-8"))
    person_elements = root.findall('person')
    for person_element in person_elements:
        variants = set()
        variant_elements = person_element.findall('variant')
        for variant_element in variant_elements:
            surname = variant_element.find('surname').text
            givenname = variant_element.find('givenname').text
            scope = variant_element.find('scope').text
            variant = PersonVariant(surname, givenname, scope)
            variants.add(variant)
        comment_element = person_element.find('comment')
        if comment_element is not None:
            comment = comment_element.text
        else:
            comment = None
        person = Person(variants, comment)
        persons.append(person)
    return persons


def init_nicknames():
    with open(f'{Config.DATA_FILES_PATH}/{Config.NICKNAMES_FILE}', 'r') as nicknames_file:
        xml = nicknames_file.read()

    nicknames = []
    root = etree.fromstring(xml.encode("utf-8"))
    nickname_elements = root.findall('nickname')
    for nickname_element in nickname_elements:
        name1 = nickname_element.find('name1').text
        name2 = nickname_element.find('name2').text
        nicknames.append((name1, name2))
    return nicknames


def init_override_corrections():
    with open(f'{Config.DATA_FILES_PATH}/{Config.OVERRIDES_FILE}', 'r') as overrides_file:
        xml = overrides_file.read()

    override_corrections = []
    root = etree.fromstring(xml.encode("utf-8"))
    override_correction_elements = root.findall('override')
    for override_correction_element in override_correction_elements:
        original_element = override_correction_element.find('original')
        original_surname = original_element.find('surname').text
        original_givenname = original_element.find('givenname').text
        corrected_element = override_correction_element.find('corrected')
        surname = corrected_element.find('surname').text
        givenname = corrected_element.find('givenname').text
        scope = override_correction_element.find('scope').text
        original_surname_raw = original_element.find('surname_raw')
        if original_surname_raw is not None:
            original_surname_raw = original_surname_raw.text
        override_correction = Override(original_surname, original_givenname, surname, givenname, scope, original_surname_raw)
        override_corrections.append(override_correction)
    return override_corrections


def init_orcid_corrections():
    with open(f'{Config.DATA_FILES_PATH}/{Config.ORCID_CORRECTIONS_FILE}', 'r') as orcids_file:
        xml = orcids_file.read()

    orcid_corrections = []
    root = etree.fromstring(xml.encode("utf-8"))
    orcid_correction_elements = root.findall('correction')
    for orcid_correction_element in orcid_correction_elements:
        surname = orcid_correction_element.find('surname').text
        givenname = orcid_correction_element.find('givenname').text
        orcid = orcid_correction_element.find('orcid').text
        orcid_correction = ORCIDCorrection('correction', surname, givenname, orcid)
        orcid_corrections.append(orcid_correction)
    orcid_correction_elements = root.findall('stipulation')
    for orcid_correction_element in orcid_correction_elements:
        surname = orcid_correction_element.find('surname').text
        givenname = orcid_correction_element.find('givenname').text
        orcid = orcid_correction_element.find('orcid').text
        orcid_correction = ORCIDCorrection('stipulation', surname, givenname, orcid)
        orcid_corrections.append(orcid_correction)
    return orcid_corrections


if __name__ == '__main__':
    persons = init_person_variants()
    for person in persons:
        print(person)
    print()
    orcid_corrections = init_orcid_corrections()
    for orcid_correction in orcid_corrections:
        print(orcid_correction)
    print()
    override_corrections = init_override_corrections()
    for override_correction in override_corrections:
        print(override_correction)