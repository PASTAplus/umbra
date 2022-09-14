#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: creators

:Synopsis:
    REST APIs for retrieving and normalizing names of creators of data packages in the EDI data repository.

    To get all creators' names:
        GET creators/names

        Response is a list in JSON format:
            ["Abbaszadegan, Morteza","Abbott, Benjamin", ... ]

    To get all variants of a name:
        GET creators/name_variants/<name>
        where <name> is a name in the form it appears in the all-names list, e.g.,
            GET creators/name_variants/McKnight, Diane M

        Response is a list in JSON format:
            ["McKnight, Diane","McKnight, Diane M","Mcknight, Diane","Mcnight, Diane"]

    To update the database with names for creators of data packages added since the last update:
        POST creators/names

:Author:
    ide

:Created:
    6/1/21
"""

from datetime import datetime, date, timedelta
import glob
import os
import requests

import ast
import daiquiri
from flask import (
    Flask, Blueprint, jsonify, request, current_app
)
from unidecode import unidecode
import xml.etree.ElementTree as ET

from webapp.config import Config
import webapp.creators.corrections as corrections
import webapp.creators.db as db
import webapp.creators.propagate_names as propagate_names

creators_bp = Blueprint('creators_bp', __name__)

creator_names = {}  # key is canonical name, value is list of name variants
creator_names_reverse_lookup = {}  # key is name variant, value is list of canonical names. Usually, the canonical name
                                   #  is unique, but very rarely there are multiple canonical names for a name variant.


logger = daiquiri.getLogger(Config.LOG_FILE)


def log_info(msg):
    # If we're running code to test it outside of Flask, we'll get a TypeError, 'NoneType' object is not iterable
    try:
        app = Flask(__name__)
        with app.app_context():
            current_app.logger.info(msg)
    except TypeError as e:
        print(msg)


def log_error(msg):
    # If we're running code to test it outside of Flask, we'll get a TypeError, 'NoneType' object is not iterable
    try:
        app = Flask(__name__)
        with app.app_context():
            current_app.logger.error(msg)
    except TypeError as e:
        print(msg)


@creators_bp.before_request
def init_names():
    global creator_names

    creator_names = {}

    with open(f'{Config.DATA_FILES_PATH}/creator_names.txt', 'r') as names_file:
        creator_names = ast.literal_eval(names_file.read())

    # Names that have been overridden (e.g., typos) need to be included in the list of variants
    #  associated with a canonical name so that their data packages will be found in a search
    override_corrections = corrections.init_override_corrections()
    override_lookup = {}
    for override_correction in override_corrections:
        surname = override_correction.surname
        givenname = override_correction.givenname
        original_surname = override_correction.original_surname
        original_givenname = override_correction.original_givenname
        original_surname_raw = override_correction.original_surname_raw
        lookup = override_lookup.get(f"{surname}, {givenname}", [])
        lookup.append(
            f"{original_surname_raw if original_surname_raw else original_surname}, {original_givenname}")
        override_lookup[f"{surname}, {givenname}"] = lookup
    for name, variants in creator_names.items():
        for variant in variants:
            if override_lookup.get(variant):
                for raw_variant in override_lookup.get(variant):
                    variants.append(raw_variant)


def save_last_update_date(now):
    last_update_path = f'{Config.DATA_FILES_PATH}/last_update.txt'
    with open(last_update_path, 'w') as last_update_file:
        last_update_file.write(now.strftime("%Y-%m-%d"))


def get_existing_eml_files():
    filelist = glob.glob(f'{Config.EML_FILES_PATH}/*.xml')
    package_ids = []
    for filename in filelist:
        filename = os.path.basename(filename)
        root, ext = os.path.splitext(filename)
        package_ids.append(root)
    return package_ids


def parse_package_id(package_id):
    substrs = package_id.split('.')
    return substrs


def delete_earlier_revisions(existing_package_ids, scope, identifier, revision, removed_package_ids):
    for package_id in existing_package_ids:
        this_scope, this_identifier, this_revision = parse_package_id(package_id)
        if this_scope == scope and this_identifier == identifier:
            if int(this_revision) < int(revision):
                removing = f'{scope}.{identifier}.{this_revision}'
                filename = f'{Config.EML_FILES_PATH}/{removing}.xml'
                try:
                    log_info(f'removing {removing}')
                    # print(f'removing {removing}')
                    removed_package_ids.append(removing)
                    os.remove(filename)
                except FileNotFoundError:
                    # We may have already deleted this file on an earlier pass
                    pass


def delete_old_revisions(removed_package_ids):
    package_ids = get_existing_eml_files()
    identifiers = {}
    for package_id in package_ids:
        scope, identifier, revision = parse_package_id(package_id)
        revisions = identifiers.get((scope, identifier), [])
        revisions.append(revision)
        identifiers[(scope, identifier)] = revisions
    for key, revisions in identifiers.items():
        if len(revisions) > 1:
            scope, identifier = key
            for revision in revisions:
                delete_earlier_revisions(package_ids, scope, identifier, revision, removed_package_ids)


def get_changes():
    # See what the from date is
    from_date = '2021-10-01'
    last_update_path = f'{Config.DATA_FILES_PATH}/last_update.txt'
    if os.path.exists(last_update_path):
        with open(last_update_path, 'r') as last_update_file:
            from_date = last_update_file.readline().strip()
    now = datetime.now()
    # Get changes since the from date
    url = f'https://pasta.lternet.edu/package/changes/eml?fromDate={from_date}'
    log_info(f'getting changes from PASTA: {url}')
    added_package_ids = []
    removed_package_ids = []
    updates = requests.get(url).text
    if not updates:
        return
    # print(updates)
    root = ET.fromstring(updates)
    package_id_elements = root.findall('./dataPackage/packageId')
    for package_id_element in package_id_elements:
        added_package_ids.append(package_id_element.text)
    existing_package_ids = get_existing_eml_files()
    for package_id in added_package_ids:
        if package_id in existing_package_ids:
            continue
        log_info(f'adding {package_id}')
        scope, identifier, revision = parse_package_id(package_id)
        # If revision > 1, delete older revisions
        if int(revision) > 1:
            delete_earlier_revisions(existing_package_ids, scope, identifier, revision, removed_package_ids)
        existing_package_ids.append(package_id)
        # Get the EML and save as xml file
        url = f'https://pasta.lternet.edu/package/metadata/eml/{scope}/{identifier}/{revision}'
        log_info(f'getting EML from PASTA:  {url}')
        eml = requests.get(url).text
        filename = f'{Config.EML_FILES_PATH}/{scope}.{identifier}.{revision}.xml'
        with open(filename, 'w') as xml_file:
            xml_file.write(eml)
    delete_old_revisions(removed_package_ids)
    save_last_update_date(now)
    return added_package_ids, removed_package_ids


def update_creator_names():
    log_info(f"update_creator_names")
    added_package_ids, removed_package_ids = get_changes()
    propagate_names.gather_and_prepare_data(added_package_ids, removed_package_ids)
    propagate_names.process_names()
    _, orphan_pids = find_orphans()
    flush_orphans(orphan_pids)
    init_names()
    log_info(f"leaving update_creator_names")


def names_key(name):
    # So we sort accented names as if they were unaccented.
    # # Otherwise, they get sorted after all of the unaccented names.
    return unidecode(name.casefold())


@creators_bp.route('/names', methods=['GET', 'POST'])
def names():
    if request.method == 'POST':
        update_creator_names()
    return jsonify(sorted(list(creator_names.keys()), key=names_key)), 200


@creators_bp.route('/name_variants/<name>', methods=['GET'])
def variants(name):
    name_variants = creator_names.get(name, None)
    if name_variants:
        return jsonify(name_variants), 200
    else:
        return (f'Name "{name}" not found'), 400


def flush_old_dups():
    filelist = sorted(glob.glob(f'{Config.POSSIBLE_DUPS_FILES_PATH}/possible_dups_*.txt'))
    if filelist:
        # When the user is flushing, we assume they've resolved based on the last time they
        #  asked for possible_dups, so we delete all but the newest saved list.
        for filename in filelist[:-1]:
            os.remove(filename)


def get_old_dups():
    dups = {}

    filelist = sorted(glob.glob(f'{Config.POSSIBLE_DUPS_FILES_PATH}/possible_dups_*.txt'))
    if filelist:
        # We want to return the oldest saved list. The user may have looked at possible_dups
        #  multiple times, but until they flush, we can't assume they've resolved dups.
        old_dups_filename = filelist[0]
        with open(old_dups_filename, 'r') as dups_file:
            dups = eval(dups_file.read())

    dups_dict = {}
    for dup in dups:
        if dup.startswith('=========='):
            continue
        surname, givennames = dup.split(': ')
        dups_dict[surname.replace('** ', '')] = givennames
    return dups_dict


def flush_orphans(orphan_pids):
    conn = db.get_conn()

    with conn.cursor() as cur:
        for pid in orphan_pids:
            query = f"delete from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} " \
                    f"where pid='{pid}'"
            cur.execute(query)
            query = f"delete from {Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME} " \
                    f"where pid='{pid}'"
            cur.execute(query)


def find_orphans():
    # Get a list of PIDs for which we have EML files
    pids = []
    filelist = sorted(glob.glob(f'{Config.EML_FILES_PATH}/*.xml'))
    if filelist:
        for filename in filelist:
            pids.append(os.path.basename(filename.replace('.xml', '')))

    # Search for creators having one of those PIDs. I.e., creators that should have been removed or replaced but weren't
    conn = db.get_conn()

    orphans = []
    orphan_pids = set()
    creators = {}
    with conn.cursor() as cur:
        query = f"select serial_id, surname, givenname, pid from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} " \
                f"where rp_type='creator'"
        cur.execute(query)
        results = cur.fetchall()
        for result in results:
            serial_id, surname, givenname, pid = result
            scope, id, _ = parse_package_id(pid)
            creators_for_pid = creators.get((scope, id), [])
            creators_for_pid.append(result)
            creators[(scope, id)] = creators_for_pid

        for pid in pids:
            scope, id, revision = parse_package_id(pid)
            creators_for_pid = creators.get((scope, id), [])
            if not creators_for_pid:
                continue
            for result in creators_for_pid:
                serial_id, surname, givenname, result_pid = result
                _, _, result_revision = parse_package_id(result_pid)
                if revision != result_revision:
                    orphans.append(result)
                    orphan_pids.add(f"{scope}.{id}.{result_revision}")
    return orphans, orphan_pids


@creators_bp.route('/orphans', methods=['GET', 'POST'])
def orphans():
    log_info(f'orphans...  method={request.method}')

    orphans, orphan_pids = find_orphans()

    if request.method == 'GET':
        return jsonify(orphans)

    if request.method == 'POST':
        flush_orphans(orphan_pids)
        return jsonify(sorted(orphan_pids))


@creators_bp.route('/possible_dups', methods=['GET', 'POST'])
def possible_dups():
    log_info(f'possible_dups...  method={request.method}')
    if request.method == 'POST':
        flush_old_dups()
        return 'Flush completed', 200

    output = []
    marked_output = []
    names = sorted(list(creator_names.keys()), key=names_key)
    prev_surname = None
    old_dups = get_old_dups()
    givennames = []
    for name in names:
        surname, givenname = name.split(', ')
        if not prev_surname:
            prev_surname = surname
        if prev_surname and surname != prev_surname:
            if len(givennames) > 1:
                out_givennames = ', '.join(givennames)
                mark_change = ''
                if old_dups:
                    if not old_dups.get(prev_surname):
                        mark_change = '** '
                    elif old_dups.get(prev_surname) != out_givennames:
                        mark_change = '** '
                output.append(f"{prev_surname}: {out_givennames}")
                marked_output.append(f"{mark_change}{prev_surname}: {out_givennames}")
            prev_surname = surname
            givennames = [givenname]
        else:
            givennames.append(givenname)

    # Save output in a file for comparison later
    timestamp = datetime.now().date().strftime('%Y_%m_%d') + '__' + datetime.now().time().strftime('%H_%M_%S')
    filename = f"possible_dups_{timestamp}.txt"
    os.makedirs(f"{Config.POSSIBLE_DUPS_FILES_PATH}/", exist_ok=True)
    with open(f"{Config.POSSIBLE_DUPS_FILES_PATH}/{filename}", 'w') as dups_file:
        dups_file.write(str(jsonify(output).json))

    # Go thru and get all the lines with change markers and prepend them to the output
    changes = []
    for outline in marked_output:
        if '** ' in outline:
            changes.append(outline.replace('** ', ''))
    marked_output = changes + ['=================================================='] + marked_output
    return jsonify(marked_output)


@creators_bp.route('/init_raw_db', methods=['POST'])
def init_raw_db():
    propagate_names.init_responsible_parties_raw_db()
    return f'Table {Config.RESPONSIBLE_PARTIES_RAW_TABLE_NAME} has been initialized', 200


def create_creator_names_reverse_lookup():
    global creator_names, creator_names_reverse_lookup

    for name in creator_names.keys():
        for variant in creator_names[name]:
            value = creator_names_reverse_lookup.get(variant, [])
            value.append(name)
            creator_names_reverse_lookup[variant] = value

    return creator_names_reverse_lookup


def get_creators_for_scope(scope):
    global creator_names

    init_names()
    create_creator_names_reverse_lookup()

    conn = db.get_conn()

    scope = scope.lower()
    with conn.cursor() as cur:
        query = f"select surname, givenname from {Config.RESPONSIBLE_PARTIES_TABLE_NAME} " \
                f"where rp_type='creator' and scope='{scope}'"
        cur.execute(query)
        names_in_scope = set(cur.fetchall())

    canonical_names_in_scope = set()
    names_in_scope = set([f"{name[0]}, {name[1]}" for name in names_in_scope])
    # print('raw_names_in_scope', len(names_in_scope))
    # print_list(sorted(names_in_scope))
    # print()
    not_found = []
    for name in names_in_scope:
        if name in creator_names_reverse_lookup:
            for canonical_name in creator_names_reverse_lookup[name]:
                canonical_names_in_scope.add(canonical_name)
        else:
            # not_found should include only things like 'United States Fish and Wildlife Service'
            # The list is captured here for debugging purposes
            not_found.append(name)

    return sorted(canonical_names_in_scope, key=names_key)


@creators_bp.route('/names_for_scope/<scope>', methods=['GET'])
def names_for_scope(scope):
    return jsonify(get_creators_for_scope(scope))


def print_list(l):
    for item in l:
        print(item)


if __name__ == '__main__':
    # get_changes()
    # names = get_creators_for_scope('knb-lter-mcr')
    # print('names_in_scope', len(names))
    # print_list(sorted(names))
    # print()
    pass