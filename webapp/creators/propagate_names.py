#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: propagate_names

:Synopsis: Collect names, normalize, and apply various methods to match name variants

:Author:
    ide

:Created:
    6/1/21
"""

import os
import daiquiri
from flask import (
    Flask, Blueprint, jsonify, request, current_app
)

from lxml import etree

from multidict import CIMultiDict
from recordclass import recordclass

from webapp.config import Config

import webapp.creators.corrections as corrections
import webapp.creators.db as db
import webapp.creators.nlp as nlp
import webapp.creators.parse_eml as parse_eml

logger = daiquiri.getLogger(Config.LOG_FILE)


def log_info(msg):
    app = Flask(__name__)
    with app.app_context():
        current_app.logger.info(msg)


def log_error(msg):
    app = Flask(__name__)
    with app.app_context():
        current_app.logger.error(msg)


'''
A NamedPerson object represents a responsible party who may have multiple names, organizations, etc., but is deemed to
be a single person. In particular, a NamedPerson may have multiple givennames. A multidict with names (surname, givenname) 
as keys, will have NamedPersons as values. I.e., multiple keys can point to the same NamedPerson, in which case each 
NamedPerson will combine the names and other attributes of various cases that are deemed to be the same person. 
It's a multidict for a couple of reasons. During processing, there will be multiple NamedPersons for a given person --
e.g., one for each scope where the person is found. These will be merged when there is sufficient evidence to establish
that they represent the same person. Even after processing/merging, there will be cases where there are more that one 
NamedPerson with the same givenname and surname, necessitating a multidict.

Go through the list of responsible parties in successive passes.
1) For RPs with identical or similar names in the same EML file (same PID), assume they are the same person and collect
    their "evidence" -- organization, position, address, etc. By "similar" is meant names like "James T Kirk", 
    "James Kirk", "J T Kirk", "J Kirk", "Jim Kirk". When these variations occur within a single data package, they
    are assumed to represent the same person, and empirically this appears to always be the case, in fact.
2) Within a scope, NamedPersons with identical names are taken to be the same person.
3) Within a scope, NamedPersons with similar names are taken to be the same person.
4) Across scopes, NamedPersons with identical names are taken to be the same person, with evidence.

1) For RPs with identical names in same PID, combine their evidence.
2) For RPs with similar names in same PID, merge.
2) For RPs with identical names in same scope
'''

named_persons_by_surname = CIMultiDict()
named_persons_by_pid = CIMultiDict()

NamedPerson = recordclass(
    'NamedPerson',
    'serial_id, pid, rp_type, givenname, surname, organization, position, address, city, country, email, '
    'url, orcid, scope, person_variants, organization_keywords'
)

'''
class MergeJustification(Enum):
    SIMILAR_NAME_SAME_PID = auto(),
    SAME_NAME_SAME_SCOPE = auto(),
    SIMILAR_NAME_SAME_SCOPE = auto(),
    SAME_NAME_OTHER_SCOPE_WITH_EVIDENCE = auto(),
    SIMILAR_NAME_OTHER_SCOPE_WITH_EVIDENCE = auto()
'''

nicknames = None


def same_names(name1, name2):
    if not name1 or not name2:
        return False
    name1 = name1.lower().replace('.', '')
    name2 = name2.lower().replace('.', '')
    return name1 == name2


# NOTE: It's risky to apply nicknames across scopes in the absence of other evidence.
def nickname(name1, name2):
    global nicknames

    for case1, case2 in nicknames:
        if (name1.startswith(case1) and name2.startswith(case2)) or (name1.startswith(case2) and name2.startswith(case1)):
            return True
    return False


def similar_names(name1, name2, use_nicknames=True):
    if not name1 or not name2:
        return False
    name1 = nlp.normalize(name1.lower().replace('.',''))
    name2 = nlp.normalize(name2.lower().replace('.',''))
    if use_nicknames:
        if nickname(name1, name2):
            return True
    segs1 = name1.split()
    segs2 = name2.split()
    min_len = min(len(segs1), len(segs2))
    for i in range(min_len):
        if not (segs1[i].startswith(segs2[i]) or segs2[i].startswith(segs1[i])):
            return False
    return True


def same_name_sets(surnames_1, surnames_2, givennames_1, givennames_2, use_nicknames=True):
    hit = False
    for surname_1 in surnames_1:
        for surname_2 in surnames_2:
            if surname_1 and surname_2 and nlp.normalize(surname_1.lower()) == nlp.normalize(surname_2.lower()):
                hit = True
                break
    if not hit:
        return False
    hit = False
    for givenname_1 in givennames_1:
        for givenname_2 in givennames_2:
            if givenname_1 and givenname_2 and nlp.normalize(givenname_1.lower()) == nlp.normalize(givenname_2.lower()):
                hit = True
                break
    return hit


def similar_name_sets(surnames_1, surnames_2, givennames_1, givennames_2, use_nicknames=True):
    hit = False
    for surname_1 in surnames_1:
        for surname_2 in surnames_2:
            if surname_1 and surname_2 and nlp.normalize(surname_1.lower()) == nlp.normalize(surname_2.lower()):
                hit = True
                break
    if not hit:
        return False
    hit = False
    for givenname_1 in givennames_1:
        for givenname_2 in givennames_2:
            if givenname_1 and givenname_2 and similar_names(givenname_1, givenname_2, use_nicknames):
                hit = True
                break
    return hit


def track_anomalous_case(error, case):
    pass
    

def merge_named_persons(named_person_1, named_person_2):
    merged = NamedPerson(
        serial_id = named_person_1.serial_id | named_person_2.serial_id,
        pid = named_person_1.pid | named_person_2.pid,
        rp_type = named_person_1.rp_type | named_person_2.rp_type,
        givenname = named_person_1.givenname | named_person_2.givenname,
        surname = named_person_1.surname | named_person_2.surname,
        organization = named_person_1.organization | named_person_2.organization,
        position = named_person_1.position | named_person_2.position,
        address = named_person_1.address | named_person_2.address,
        city = named_person_1.city | named_person_2.city,
        country = named_person_1.country | named_person_2.country,
        email = named_person_1.email | named_person_2.email,
        url = named_person_1.url | named_person_2.url,
        orcid = named_person_1.orcid | named_person_2.orcid,
        scope = named_person_1.scope | named_person_2.scope,
        person_variants = named_person_1.person_variants | named_person_2.person_variants,
        organization_keywords = named_person_1.organization_keywords | named_person_2.organization_keywords
    )
    if len(merged.orcid) > 1:
        track_anomalous_case('Multiple orcids', merged)
    return merged


def get_pids_by_scope():
    conn = db.get_conn()

    scopes = {}
    with conn.cursor() as cur:
        query = f"select distinct pid, scope from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} where not skip " \
                f"order by scope, pid"
        cur.execute(query)
        results = cur.fetchall()

        for pid, scope in results:
            pids = scopes.get(scope, [])
            pids.append(pid)
            scopes[scope] = pids
    return scopes


'''
Go thru and create NamedPerson objects for each responsible party. Within a given PID, if the same surname
occurs with same or similar givennames, they're assumed to be the same person and their NamedPerson object
combines the attributes (organization, address, etc.) of the individual occurrences. 
'''
def collect_names_1(creators_only=True):
    global named_persons_by_surname, named_persons_by_pid

    named_persons_by_surname = CIMultiDict()
    named_persons_by_pid = CIMultiDict()

    conn = db.get_conn()

    with conn.cursor() as cur:
        where_clause = " and rp_type='creator' " if creators_only else ""
        query = f"select * from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} where not skip {where_clause}" \
                f"order by pid, surname, givenname"
        cur.execute(query)
        results = cur.fetchall()

        prev_pid = None
        prev_surname = None
        prev_givenname = None
        prev_named_person = None
        for serial_id, pid, rp_type, givenname, surname, organization, position, address, city, country, email, \
            url, orcid, scope, _, _, organization_keywords, _ in results:
            named_person = None
            if pid == prev_pid:
                if nlp.normalize(surname) == nlp.normalize(prev_surname):
                    if similar_names(f'{givenname} {surname}', f'{prev_givenname} {prev_surname}'):
                        # should have a prev_named_person; we will add to it
                        named_person = prev_named_person
            new = False
            if not named_person:
                new = True
                named_person = NamedPerson(
                    serial_id=set(),
                    pid=set(),
                    rp_type=set(),
                    givenname=set(),
                    surname=set(),
                    organization=set(),
                    position=set(),
                    address=set(),
                    city=set(),
                    country=set(),
                    email=set(),
                    url=set(),
                    orcid=set(),
                    scope=set(),
                    person_variants=set(),
                    organization_keywords=set()
                )
            named_person.serial_id.add(serial_id)
            named_person.pid.add(pid)
            named_person.rp_type.add(rp_type)
            named_person.givenname.add(givenname)
            named_person.surname.add(surname)
            if organization:
                named_person.organization.add(organization)
            if position:
                named_person.position.add(position)
            if address:
                named_person.address.add(address)
            if city:
                named_person.city.add(city)
            if country:
                named_person.country.add(country)
            if email:
                emails = email.split(' ')
                for email in emails:
                    named_person.email.add(email.lower())
            if url:
                urls = url.split(' ')
                for url in urls:
                    named_person.url.add(url.lower())
            if orcid:
                named_person.orcid.add(orcid)
            named_person.scope.add(scope)
            named_person.person_variants.add(corrections.PersonVariant(surname, givenname, scope))
            if organization_keywords:
                named_person.organization_keywords.add(organization_keywords)

            if new:
                named_persons_by_pid.add(pid, named_person)
                named_persons_by_surname.add(surname, named_person)

            prev_givenname = givenname
            prev_surname = surname
            prev_pid = pid
            prev_named_person = named_person
    return named_persons_by_surname, named_persons_by_pid


def remove_items(from_multidict, key, to_remove):
    vals = from_multidict.popall(key)
    for val in to_remove:
        try:
            vals.remove(val)
        except ValueError:
            pass
    for val in vals:
        from_multidict.add(key, val)


def merge_items(items_to_merge):
    if not items_to_merge:
        return None
    merged = items_to_merge[0]
    for item in items_to_merge[1:]:
        merged = merge_named_persons(merged, item)
    return merged


'''
Go thru the NamedPerson objects and combine them, when appropriate. The criteria that are applied differ in 
different passes:
- Within a scope, NamedPersons with identical names are taken to be the same person. I.e., equality_test=same_name_sets,
    require_evidence=False, cross_scopes=False.
- Within a scope, NamedPersons with similar names are taken to be the same person. I.e., equality_test=similar_name_sets,
    require_evidence=False, cross_scopes=False.
- Across scopes, NamedPersons with identical names are taken to be the same person if there is evidence. 
    I.e., equality_test=same_name_sets, require_evidence=True, cross_scopes=True.
- Across scopes, NamedPersons with similar names are taken to be the same person if there is evidence. 
    I.e., equality_test=similar_name_sets, require_evidence=True, cross_scopes=True.
'''
def collect_names_2(scope, equality_test=same_name_sets, require_evidence=True, cross_scopes=False, person_variants_lookup=None):
    global named_persons_by_surname

    surnames = sorted(list(set(named_persons_by_surname.keys())))
    while True:
        changed = False
        for surname in surnames:
            named_persons = named_persons_by_surname.getall(surname, [])
            enumerated = list(enumerate(named_persons))
            to_remove = []
            for i, named_person_i in enumerated:
                if named_person_i in to_remove:
                    continue
                if not cross_scopes and scope not in named_person_i.scope:
                    continue
                _, pid_i, _, givenname_i, surname_i, *_, orcid_i, scope_i, _, _ = named_person_i
                to_merge = []
                for j, named_person_j in enumerated[i + 1:]:
                    _, pid_j, _, givenname_j, surname_j, *_, orcid_j, scope_j, _, _ = named_person_j
                    if named_person_j in to_remove:
                        continue
                    if not cross_scopes and scope not in named_person_j.scope:
                        continue
                    merge = match_based_on_name_variants_corrections(named_person_i.person_variants,
                                                                     named_person_j.person_variants,
                                                                     person_variants_lookup)

                    if ((equality_test(surname_i, surname_j, givenname_i, givenname_j)) or \
                            (orcid_i and orcid_j and orcid_i == orcid_j)) and \
                            not (orcid_i and orcid_j and orcid_i != orcid_j):
                        if require_evidence:
                            if matched_named_persons(named_person_i, named_person_j):
                                merge = True
                        else:
                            merge = True
                    if merge:
                        to_remove.append(named_person_i)
                        to_remove.append(named_person_j)
                        if named_person_i not in to_merge:
                            to_merge.append(named_person_i)
                        if named_person_j not in to_merge:
                            to_merge.append(named_person_j)
                        changed = True
                if to_merge:
                    merged = merge_items(to_merge)
                    named_persons_by_surname.add(surname, merged)
            if to_remove:
                remove_items(named_persons_by_surname, surname, to_remove)
        if not changed:
            break


def match_based_on_name_variants_corrections(person_variants_1, person_variants_2, person_variants_lookup):
    if person_variants_lookup:
        for variant_1 in person_variants_1:
            lookup_1 = person_variants_lookup.get(variant_1)
            if lookup_1:
                for variant_2 in person_variants_2:
                    lookup_2 = person_variants_lookup.get(variant_2)
                    if lookup_2 and lookup_1 is lookup_2:
                        return True
    return False


def match_organization_keywords(keywords_1, keywords_2):
    if not keywords_1 or not keywords_2:
        return False
    keys_1 = ' '.join(list(keywords_1))
    keys_2 = ' '.join(list(keywords_2))
    substrs_1 = keys_1.split()
    substrs_2 = keys_2.split()
    for substr_1 in substrs_1:
        for substr_2 in substrs_2:
            if substr_1 == substr_2:
                return True
    return False


def matched_named_persons(named_person_1, named_person_2):
    *_, organization_1, position_1, address_1, city_1, _, email_1, url_1, orcid_1, scope_1, _, organization_keywords_1 = named_person_1
    *_, organization_2, position_2, address_2, city_2, _, email_2, url_2, orcid_2, scope_2, _, organization_keywords_2 = named_person_2

    if orcid_1 & orcid_2:
        return True
    if organization_1 & organization_2:
        return True
    if position_1 & position_2:
        return True
    if address_1 & address_2:
        return True
    if city_1 & city_2:
        return True
    if email_1 & email_2:
        return True
    if url_1 & url_2:
        return True
    if match_organization_keywords(organization_keywords_1, organization_keywords_2):
        return True
    return False


def find_cross_scope_names(scopes, creators_only=False, person_variants_lookup=None):
    global named_persons_by_surname

    scopes_by_name = {}
    surnames = sorted(list(set(named_persons_by_surname.keys())))

    for scope in scopes:
        for surname in surnames:
            named_persons = named_persons_by_surname.getall(surname, [])
            for named_person in named_persons:
                if scope not in named_person.scope:
                    continue
                if creators_only and 'creator' not in named_person.rp_type:
                    continue
                if named_person.orcid:
                    orcid = f"[{list(named_person.orcid)[0]}]"
                else:
                    orcid = ''
                name = f"{surname}: {', '.join(named_person.givenname)}"
                for givenname in named_person.givenname:
                    scopes = scopes_by_name.get((surname, givenname), [])
                    scopes.append((scope, named_person))
                    scopes_by_name[(surname, givenname)] = scopes
                print(f"{name.ljust(20)}\t{orcid}")

    print()
    print()
    print('Names in multiple scopes:')
    keys = sorted(scopes_by_name.keys())
    for key in keys:
        val = scopes_by_name.get(key)
        if len(val) == 1:
            continue
        surname, givenname = key
        name = f"{surname}, {givenname}"
        scope_list = ', '.join([scope for scope, _ in val])
        print(f"{name.ljust(20)}\t{scope_list}")

    print()
    print()
    print('Unmatched names in multiple scopes:')
    for key in keys:
        val = scopes_by_name.get(key)
        if len(val) == 1:
            continue
        surname, givenname = key

        named_persons = [named_person for scope, named_person in val]
        enumerated = list(enumerate(named_persons))
        for i, named_person_i in enumerated:
            for j, named_person_j in enumerated[i+1:]:
                if named_person_i.surname == named_person_j.surname and \
                    named_person_i.givenname == named_person_j.givenname:
                    continue
                if not matched_named_persons(named_person_i, named_person_j) and \
                    not match_based_on_name_variants_corrections(named_person_i.person_variants,
                                                                 named_person_j.person_variants,
                                                                 person_variants_lookup):
                    print(f"{surname}: {givenname}")


def propagate_orcids(correction_code):
    global named_persons_by_surname

    conn = db.get_conn()
    with conn.cursor() as cur:
        surnames = sorted(list(set(named_persons_by_surname.keys())))
        for surname in surnames:
            named_persons = named_persons_by_surname.getall(surname, [])
            for named_person in named_persons:
                serial_id, *_, orcid, _, _, _ = named_person
                if not orcid:
                    continue
                serial_ids = ','.join(sorted([str(id) for id in serial_id]))
                query = f"update {Config.RESPONSIBLE_PARTIES_TABLE_NAME} set orcid='{list(orcid)[0]}', correction_codes='{correction_code}' " \
                        f" where serial_id in ({serial_ids}) and orcid=''"
                cur.execute(query)
                conn.commit()


def get_lter_sites():
    lter_sites = {}

    filepath = f"{Config.DATA_FILES_PATH}/LTER_sites.csv"
    with open(filepath, 'r', encoding='utf-8-sig') as lter_file:
        lines = lter_file.readlines()
        for line in lines:
            substrs = line.strip().split(',')
            description = substrs[0]
            code = substrs[1]
            state = substrs[2]
            scope = f"knb-lter-{code.lower()}"
            lter_sites[f"{code} LTER"] = (scope, state)
            lter_sites[description] = (scope, state)
    return lter_sites


def save_creator_names():
    global named_persons_by_surname

    surnames = sorted(list(set(named_persons_by_surname.keys())), key=str.casefold)

    with open(f'{Config.DATA_FILES_PATH}/creator_names.txt', 'w') as names_file:
        for surname in surnames:
            named_persons = named_persons_by_surname.getall(surname, [])
            prev_givenname_output = ''
            for named_person in named_persons:
                if 'creator' not in named_person.rp_type:
                    continue
                serial_id, pid, rp_type, givenname, surname, organization, position, address, city, country, \
                    email, url, orcid, scope, _, organization_keywords = named_person
                if not len(surname):
                    continue
                if len(givenname) == 1:
                    givenname_output = givenname.pop()
                else:
                    givennames = sorted(givenname)
                    display_name = ''
                    for name in givennames:
                        if len(name) > len(display_name):
                            display_name = name
                    givenname_output = f"{display_name}  --> {' | '.join(sorted(givenname))}"
                if givenname_output != prev_givenname_output:
                    prev_givenname_output = givenname_output
                    try:
                        output = f"{surname.pop()}, {givenname_output}"
                    except:
                        continue
                    # print(output)
                    names_file.write(f"{output}\n")


def set_organization_keywords_in_db():
    with open(f'{Config.DATA_FILES_PATH}/{Config.ORGANIZATIONS_FILE}', 'r') as organizations_file:
        xml = organizations_file.read()

    conn = db.get_conn()
    with conn.cursor() as cur:
        root = etree.fromstring(xml.encode("utf-8"))
        organization_elements = root.findall('organization')
        for organization_element in organization_elements:
            name_elements = organization_element.findall('name')
            email_elements = organization_element.findall('email')
            keyword = organization_element.find('keyword').text
            subqueries = []
            for name_element in name_elements:
                subqueries.append(f"organization like '%{name_element.text}%'")
                subqueries.append(f"address like '%{name_element.text}%'")
            for email_element in email_elements:
                subqueries.append(f"email like '%@{email_element.text}%'")
                subqueries.append(f"email like '%.{email_element.text}%'")
                subqueries.append(f"url like '%/{email_element.text}'")
                subqueries.append(f"url like '%.{email_element.text}'")
            subquery = ' or '.join(subqueries)
            query = f"update {Config.RESPONSIBLE_PARTIES_TABLE_NAME} " \
                    f"set organization_keywords=concat(organization_keywords, ' {keyword}') " \
                    f"where ({subquery}) and rp_type='creator' and not skip"
            cur.execute(query)


def init_responsible_parties_raw_db():
    filename = Config.RESPONSIBLE_PARTIES_TEXT_FILE
    os.remove(f'{Config.EML_FILES_PATH}/{filename}')
    log_info('Collect responsible parties')
    parse_eml.collect_responsible_parties(filename, trace=True)

    log_info('Clear raw responsible parties db')
    conn = db.get_conn()
    with conn.cursor() as cur:
        query = f'delete from {Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME}'
        cur.execute(query)

    log_info('Build raw responsible parties db')
    db.build_responsible_party_raw_db(filename)
    log_info('Remove duplicates from raw responsible parties db')
    db.remove_duplicate_records(table_name=Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME)


def gather_and_prepare_data(added_package_ids=None, removed_package_ids=None):
    filename = Config.RESPONSIBLE_PARTIES_TEXT_FILE
    parse_eml.collect_responsible_parties(filename, added_package_ids, removed_package_ids)
    responsible_parties = db.parse_responsible_parties_file(filename)
    db.prune_pids(responsible_parties, removed_package_ids)
    # Prune added pids, too, because we may have already run this today. They'll just get added back in.
    db.prune_pids(responsible_parties, added_package_ids)
    db.build_responsible_party_raw_db(filename, added_package_ids)
    db.remove_duplicate_records(table_name=Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME)
    db.init_responsible_parties_table(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME,
                                      raw_table_name=Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME)
    db.fix_misplaced_middle_initials(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    db.clean_database_text(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    db.normalize_db_text(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    db.clean_responsible_party_orcids(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    db.make_orcid_corrections(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    db.apply_overrides(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME)
    set_organization_keywords_in_db()


def process_names():
    global named_persons_by_surname, named_persons_by_pid, nicknames

    # get_lter_sites()
    person_variants = corrections.init_person_variants()
    person_variants_lookup = create_person_variants_lookup(person_variants)
    nicknames = corrections.init_nicknames()

    scopes = get_pids_by_scope()
    named_persons_by_surname, named_persons_by_pid = collect_names_1()

    # Within a scope, NamedPersons with identical names are taken to be the same person.
    # Within a scope, NamedPersons with similar names are taken to be the same person.
    # Across scopes, NamedPersons with identical names are taken to be the same person, with evidence.
    # Across scopes, NamedPersons with similar names are taken to be the same person, with evidence.

    for scope in scopes:
        collect_names_2(scope, equality_test=same_name_sets, require_evidence=False, person_variants_lookup=None)
    for scope in scopes:
        collect_names_2(scope, equality_test=similar_name_sets, require_evidence=False, person_variants_lookup=None)
    collect_names_2('All, with evidence',
                    equality_test=same_name_sets,
                    require_evidence=True,
                    cross_scopes=True,
                    person_variants_lookup=person_variants_lookup)
    collect_names_2('All, similar names, with evidence',
                    equality_test=similar_name_sets,
                    require_evidence=True,
                    cross_scopes=True,
                    person_variants_lookup=person_variants_lookup)
    propagate_orcids(99)
    save_creator_names()


def create_person_variants_lookup(person_variants):
    person_variants_lookup = {}
    for person in person_variants:
        for variant in person.variants:
            person_variants_lookup[variant] = person
    return person_variants_lookup


if __name__ == '__main__':
    # init_responsible_parties_raw_db()
    pass


