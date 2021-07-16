#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: db

:Synopsis:
    Functions to update and manage the PostgreSQL database containing the information on responsible parties
    extracted from the EML files obtained from PASTA.

:Author:
    ide

:Created:
    6/1/21
"""

import psycopg2

from webapp.config import Config
import webapp.creators.corrections as corrections

import nlp
import utils


def get_conn():
    conn = psycopg2.connect(f'dbname={Config.DB_NAME} user={Config.DB_USER} host={Config.DB_HOST} password={Config.DB_PASSWORD}')
    conn.autocommit = True
    return conn


def get_all_pids():
    conn = get_conn()

    with conn.cursor() as cur:
        query = f"select distinct pid from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} order by pid"
        cur.execute(query)
        results = cur.fetchall()
    return [result[0] for result in results]


def get_pids_by_name(givenname, surname):
    conn = get_conn()

    with conn.cursor() as cur:
        givenname = givenname.replace("'", "''")
        surname = surname.replace("'", "''")
        query = f"select distinct pid from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} " \
                f"where givenname='{givenname}' and surname='{surname}' order by pid"
        cur.execute(query)
        results = cur.fetchall()
    return [result[0] for result in results]


# ------------------------------------------------------------------------------------------------
# Building the raw responsible party database table
# ------------------------------------------------------------------------------------------------

def find_entries(line, tag):
    entries = []
    for item in line:
        if item[0] == tag:
            entries.append(item[1])
    return ' '.join(entries)


def parse_responsible_parties_file(filename):
    filepath = f'{Config.EML_FILES_PATH}/{filename}'
    try:
        with open(filepath, 'r') as rp_file:
            lines = rp_file.read().split('\n')
    except FileNotFoundError:
        lines = []
    responsible_parties = {}
    for line in lines:
        try:
            pid, *_ = eval(line)
        except:
            continue
        pid_lines = responsible_parties.get(pid, set())
        pid_lines.add(line)
        responsible_parties[pid] = pid_lines
    return responsible_parties


def prune_pids(responsible_parties, pids_to_remove):
    # As PIDs are removed (older revisions, for example), remove their entries from the database
    if pids_to_remove:
        for pid in pids_to_remove:
            responsible_parties.pop(pid, None)


def insert_responsible_party_raw(conn, pid=None, rp_type=None, givenname=None, surname=None,
                                 organization=None, position=None, address=None, city=None,
                                 country=None, email=None, url=None, orcid=None,
                                 scope=None, identifier=None):
    cur = conn.cursor()
    sql = f"INSERT INTO {Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME} VALUES ('{pid}','{rp_type}'," + \
        f"'{givenname}','{surname}','{organization}','{position}','{address}','{city}','{country}'," \
        f" '{email}','{url}','{orcid}','{scope}',{identifier})"
    cur.execute(sql)
    conn.commit()


def remove_duplicate_records(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    conn = get_conn()

    with conn.cursor() as cur:
        sql = f"delete from {table_name} T1 using {table_name} T2 where T1.ctid<T2.ctid and " \
              f"T1.givenname = T2.givenname and T1.surname = T2.surname and T1.pid = T2.pid and T1.rp_type = T2.rp_type"
        cur.execute(sql)
        conn.commit()


def build_responsible_party_raw_db(filename, added_package_ids):
    if added_package_ids == []:
        return

    conn = get_conn()

    filepath = f'{Config.EML_FILES_PATH}/{filename}'
    with open(filepath, 'r') as rp_file:
        lines = rp_file.read().split('\n')
    for line in lines:
        try:
            pid, rp_type, vals = eval(line)
        except:
            continue
        if added_package_ids and pid not in added_package_ids:
            continue
        givenname = find_entries(vals, 'givenName').replace("'", "''")
        surname = find_entries(vals, 'surName').replace("'", "''")  # FIXME
        organization = find_entries(vals, 'organizationName').replace("'", "''")
        position = find_entries(vals, 'positionName').replace("'", "''")
        address = find_entries(vals, 'deliveryPoint').replace("'", "''")
        city = find_entries(vals, 'city').replace("'", "")
        country = find_entries(vals, 'country').replace("'", "")
        email = find_entries(vals, 'electronicMailAddress').replace("'", "''")
        url = find_entries(vals, 'onlineUrl').replace("'", "''")
        orcid = find_entries(vals, 'userId')
        scope, identifier, version = pid.split('.')

        insert_responsible_party_raw(conn, pid, rp_type, givenname, surname, organization, position, address,
                                     city, country, email, url, orcid, scope, identifier)


def init_responsible_parties_table(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME,
                                   raw_table_name=Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME):
    conn = get_conn()

    with conn.cursor() as cur:
        query = f"truncate {table_name} restart identity"
        cur.execute(query)

        query = f"insert into {table_name} (pid, rp_type, givenname, surname, organization, position, address, city, country, email, url, orcid, scope, identifier) " \
                f"(select pid, rp_type, givenname, surname, organization, position, address, city, country, email, url, orcid, scope, identifier FROM {raw_table_name})"
        cur.execute(query)

        query = f"update {table_name} set skip=false"
        cur.execute(query)
        query = f"update {table_name} set skip=true " \
                f" where givenname like 'National%' or givenname like '(%' or givenname  like 'Center%'or givenname like '%Manager%' or surname like '%Manager%' or " \
                f" surname like '%LTER%' or surname = 'Lead PI' or surname like '%USDA%' or givenname = ''"
        cur.execute(query)


# ------------------------------------------------------------------------------------------------


def fix_misplaced_middle_initials(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    conn = get_conn()

    with conn.cursor() as cur:
        query = f"select serial_id, surname, givenname from {table_name} where surname ~* '^[a-z]\.\s[a-z]+\s*'"
        cur.execute(query)
        results = cur.fetchall()
        for serial_id, surname, givenname in results:
            initial, surname = surname.split(' ')
            givenname = f"{givenname} {initial}".replace("'", "''")
            surname = surname.replace("'", "''")
            query = f"update {table_name} set surname='{surname}', givenname='{givenname}' where serial_id={serial_id}"
            cur.execute(query)


def clean_text_field(cur, colname, table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):

    # Get rid of newlines
    query = f"update {table_name} set {colname} = trim(regexp_replace({colname}, '\n', ' ', 'g'))"
    cur.execute(query)

    # Get rid of multiple consecutive spaces
    query = f"update {table_name} set {colname} = trim(regexp_replace({colname}, '\s+', ' ', 'g'))"
    cur.execute(query)


def clean_database_text(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    conn = get_conn()

    with conn.cursor() as cur:
        query = f"select serial_id, orcid from {table_name} where orcid <> ''"
        cur.execute(query)

        # Clean periods from names
        query = f"update {table_name} set givenname=translate(givenname, '.', '')"
        cur.execute(query)
        query = f"update {table_name} set surname=translate(surname, '.', '')"
        cur.execute(query)

        # Clean newlines and multiple consecutive spaces in organization, position, and address
        clean_text_field(cur, 'organization')
        clean_text_field(cur, 'position')
        clean_text_field(cur, 'address')

        # Clear address if it's just a comma
        query = f"update {table_name} set address='' where address=','"
        cur.execute(query)


def clean_responsible_party_orcids(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    conn = get_conn()

    with conn.cursor() as cur:
        query = f"select serial_id, orcid from {table_name} where orcid <> ''"
        cur.execute(query)
        nonempty_orcids = cur.fetchall()

        for serial_id, raw_orcid in nonempty_orcids:
            cleaned_orcid = utils.trim_orcid(raw_orcid)
            if cleaned_orcid != raw_orcid:
                query = f"update {table_name} set orcid='{cleaned_orcid}' where serial_id='{serial_id}'"
                cur.execute(query)
                conn.commit()


def make_orcid_corrections(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    orcids = corrections.init_orcid_corrections()
    conn = get_conn()
    with conn.cursor() as cur:
        for orcid_obj in orcids:
            surname = orcid_obj.surname.replace("'", "''")
            givenname = orcid_obj.givenname.replace("'", "''")
            orcid = orcid_obj.orcid
            if orcid_obj.type == 'correction':
                query = f"update {table_name} set orcid='{orcid}', correction_codes = '0' where " \
                        f"orcid <> '' and orcid <> '{orcid}' and givenname like '{givenname}' and surname='{surname}'"
            elif orcid_obj.type == 'stipulation':
                query = f"update {table_name} set orcid='{orcid}', correction_codes = '99' where " \
                        f"orcid <> '' and givenname like '{givenname}' and surname='{surname}'"
            cur.execute(query)


def apply_overrides(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    override_corrections = corrections.init_override_corrections()

    conn = get_conn()
    with conn.cursor() as cur:
        for override_correction in override_corrections:
            original_surname = override_correction.original_surname.replace("'", "''")
            surname = override_correction.surname.replace("'", "''")

            original_givenname = override_correction.original_givenname.replace("'", "''")
            givenname = override_correction.givenname.replace("'", "''")

            if '%' not in override_correction.original_surname:
                surname_condition = f"surname='{original_surname}'"
            else:
                surname_condition = f"surname like '{original_surname}'"
            query = f"update {table_name} " \
                    f"set surname='{surname}', givenname='{givenname}' " \
                    f"where {surname_condition} and " \
                    f" givenname='{original_givenname}' and scope='{override_correction.scope}'"
            cur.execute(query)


def special_cases(s):
    s = s.replace("¡", "")
    s = s.replace("!", "")
    s = s.replace("•", "-")
    s = s.replace("/", "-")
    s = s.replace('a€"', "-")
    s = s.replace('a€¢', "-")
    s = s.replace("­", "-")
    s = s.replace("–", "-")
    s = s.replace('+', '')
    s = s.replace('?', '')
    s = s.replace('>', '')
    s = s.replace('‐', '-')
    return s


def normalize_name_field(field_name, table_name):
    conn = get_conn()
    with conn.cursor() as cur:
        query = f"update {table_name} set {field_name}=unaccent({field_name}) where {field_name} != unaccent({field_name})"
        cur.execute(query)


def normalize_data_field(field_name, table_name):
    conn = get_conn()
    with conn.cursor() as cur:
        subquery = '[^0-9a-zA-Z \*\-\,\/\(\)\|@\.;"&:''\#]'
        query = f"select serial_id, {field_name} from {table_name} where {field_name} ~* '{subquery}' order by serial_id;"
        cur.execute(query)
        problem_cases = cur.fetchall()
        for serial_id, problem_case in problem_cases:
            problem_case = nlp.normalize(problem_case).replace("'", "''")  # Need to normalize before replace so quote char is normalized
            problem_case = special_cases(problem_case)
            query = f"update {table_name} set {field_name}='{problem_case}' where serial_id={serial_id}"
            cur.execute(query)


def normalize_db_text(table_name=Config.RESPONSIBLE_PARTIES_TABLE_NAME):
    for field in ['surname', 'givenname']:
        normalize_name_field(field, table_name)
    for field in ['position', 'address', 'organization']:
        normalize_data_field(field, table_name)


def clean_names(givenname, surname):
    normalized_givenname = nlp.ormalize(givenname).replace("'", "''")
    normalized_surname = nlp.normalize(surname).replace("'", "''")
    # special cases
    normalized_givenname = normalized_givenname.replace('M&eacute;lanie', 'Melanie')
    normalized_surname = normalized_surname.replace(' (In Memorium)', '')
    normalized_surname = normalized_surname.replace(' (deceased)', '')
    normalized_surname = normalized_surname.replace('PA©rez', 'Perez')
    normalized_surname = normalized_surname.replace('JofreRodriguez', 'Jofre-Rodriguez')
    if normalized_givenname == 'Zoe' and normalized_surname.startswith('Rodr'):
        normalized_surname = 'Rodriquez'
    return normalized_givenname, normalized_surname


def create_cleaned_names_table(rp_type=None):
    conn = get_conn()
    with conn.cursor() as cur:
        # get names with special characters
        subquery = "[^a-zA-Z\-'' ]"
        rp_subquery = ''
        if rp_type:
            rp_subquery = f" and rp_type='{rp_type}' "
        query = f"select distinct givenname, surname from {RESPONSIBLE_PARTIES_TABLE_NAME} where " \
                f"(givenname ~* '{subquery}' or surname ~* '{subquery}') and not skip {rp_subquery} " \
                f"order by surname, givenname"
        cur.execute(query)
        results = cur.fetchall()
        for givenname, surname in results:
            normalized_givenname, normalized_surname = clean_names(givenname, surname)
            givenname = givenname.replace("'", "''")
            surname = surname.replace("'", "''")
            query = f"insert into eml_files.cleaned_names " \
                    f"(cleaned_givenname, cleaned_surname, original_givenname, original_surname) " \
                    f"values ('{normalized_givenname}', '{normalized_surname}', '{givenname}', '{surname}')"
            cur.execute(query)


if __name__ == '__main__':
    pass
    # ic.configureOutput(prefix=utils.time_format)
    # g, s = clean_names('Maria J', 'González')


