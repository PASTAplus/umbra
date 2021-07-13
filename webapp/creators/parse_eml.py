#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: propagate_names

:Synopsis: Parse EML files to collect information on the responsible parties, creating RESPONSIBLE_PARTIES_TEXT_FILE.

:Author:
    ide

:Created:
    6/1/21
"""

from enum import Enum, auto
import glob
import os
import pickle

from recordclass import recordclass

from config import Config
import db
from metapype.eml import names
from metapype.model.metapype_io import from_xml
import nlp


class EMLTextComponents(Enum):
    DATASET_TITLE = auto(),
    DATASET_ABSTRACT = auto(),
    DATASET_KEYWORDS = auto(),
    DATATABLE_DESCRIPTIONS = auto(),
    DATASET_GEO_DESCRIPTIONS = auto(),
    METHOD_STEP_DESCRIPTIONS = auto(),
    PROJECT_TITLES = auto(),
    PROJECT_ABSTRACTS = auto(),
    RELATED_PROJECT_TITLES = auto(),
    RELATED_PROJECT_ABSTRACTS = auto()


ProjectText = recordclass(
    'ProjectText',
    'project_title project_abstract'
)

EMLText = recordclass(
    'EMLText',
    'dataset_title dataset_abstract dataset_keywords datatable_descriptions dataset_geographic_descriptions method_step_descriptions projects related_projects'
)

eml_text_by_pid = {}


def xml_to_json(filepath):
    cwd = os.getcwd()
    with open(filepath, 'r') as fp:
        xml = fp.read()
        try:
            return from_xml(xml)
        except Exception as err:
            print(f'Metapype failed to convert xml to json for file {filepath}. Error:{err}')
            return None


def parse_section(node):
    text = []
    if node.content:
        text.append(node.content)
        return text
    title = node.find_child(names.TITLE)
    if title and title.content:
        text.append(title.content)
    section = node.find_child(names.SECTION)
    if section:
        text.extend(parse_section(section))
        return text
    para = node.find_child(names.PARA)
    if para:
        text.extend(parse_para(para))
        return text
    return text


def parse_para(node):
    text = []
    if node.content:
        text.append(node.content)
        return text
    value = node.find_child(names.VALUE)
    if value and value.content:
        return [value.content]
    return text


def parse_text_type(node):
    text = []
    if node.content:
        text.append(node.content)
        return text
    section = node.find_child(names.SECTION)
    if section:
        return parse_section(section)
    para = node.find_child(names.PARA)
    if para:
        return parse_para(para)
    return text


def get_existing_eml_files():
    filelist = glob.glob(f'{Config.EML_FILES_PATH}/*.xml')
    return [os.path.basename(x) for x in filelist]


def get_dataset_title(eml_node):
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE, names.VALUE])
    if not title_node:
        title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    return [title_node.content]


def get_dataset_abstract(eml_node):
    abstract_node = eml_node.find_single_node_by_path([names.DATASET, names.ABSTRACT, names.PARA])
    if not abstract_node:
        abstract_node = eml_node.find_single_node_by_path([names.DATASET, names.ABSTRACT, names.SECTION, names.PARA])
    if abstract_node:
        return parse_text_type(abstract_node)
    else:
        return []


def harvest_projects(eml_node):
    project_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT])
    project_text = get_project_text(project_nodes)
    related_project_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
    related_project_text = get_project_text(related_project_nodes)
    return project_text, related_project_text


def get_project_text(project_nodes):
    project_text = []
    for project_node in project_nodes:
        title = ''
        abstract = ''
        title_node = project_node.find_child(names.TITLE)
        if title_node:
            title = [title_node.content]
        abstract_node = project_node.find_child(names.ABSTRACT)
        if abstract_node:
            abstract = parse_text_type(abstract_node)
        project_text.append(ProjectText(
            project_title=title,
            project_abstract=abstract))
    return project_text


def get_project_titles(eml_node):
    project_titles = []
    title_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.TITLE])
    for title_node in title_nodes:
        if title_node.content:
            project_titles.append([title_node.content])
    return project_titles


def get_project_abstracts(eml_node):
    project_abstracts = []
    abstract_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.ABSTRACT, names.PARA])
    for abstract_node in abstract_nodes:
        project_abstracts.extend(parse_text_type(abstract_node))
    return project_abstracts


def get_keywords(eml_node):
    kw = []
    keyword_nodes = []
    eml_node.find_all_descendants(names.KEYWORD, keyword_nodes)
    for keyword_node in keyword_nodes:
        kw.append(keyword_node.content)
    return kw


def get_all_ranks(eml_node, rank):
    rank_nodes = []
    eml_node.find_all_descendants(names.TAXONRANKNAME, rank_nodes)
    found = set()
    for rank_node in rank_nodes:
        if rank_node.content.lower() == rank:
            parent = rank_node.parent
            rank_value = parent.find_child(names.TAXONRANKVALUE).content
            found.add(rank_value)
    return sorted(found)


def get_all_genera(eml_node):
    return get_all_ranks(eml_node, 'genus')


def get_all_species(eml_node):
    return get_all_ranks(eml_node, 'species')


def get_children(parent_node, child_name):
    children = []
    child_nodes = parent_node.find_all_children(child_name)
    for child_node in child_nodes:
        if child_node.content:
            children.append((child_name, child_node.content))
    return children


def get_person(rp_node):
    person = []
    individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
    if individual_name_node:
        person.extend(get_children(individual_name_node, names.SALUTATION))
        person.extend(get_children(individual_name_node, names.GIVENNAME))
        person.extend(get_children(individual_name_node, names.SURNAME))
    person.extend(get_children(rp_node, names.ORGANIZATIONNAME))
    person.extend(get_children(rp_node, names.POSITIONNAME))
    return person


def get_address(rp_node):
    address = []
    address_node = rp_node.find_child(names.ADDRESS)
    if address_node:
        address.extend(get_children(address_node, names.DELIVERYPOINT))
        address.extend(get_children(address_node, names.CITY))
        address.extend(get_children(address_node, names.ADMINISTRATIVEAREA))
        address.extend(get_children(address_node, names.POSTALCODE))
        address.extend(get_children(address_node, names.COUNTRY))
    return address


def get_responsible_party(rp_node):
    party = []
    party.extend(get_person(rp_node))
    party.extend(get_address(rp_node))
    party.extend(get_children(rp_node, names.PHONE))
    party.extend(get_children(rp_node, names.ELECTRONICMAILADDRESS))
    party.extend(get_children(rp_node, names.ONLINEURL))
    party.extend(get_children(rp_node, names.USERID))
    return party


def get_responsible_parties(pid, eml_node, path):
    rp_nodes = eml_node.find_all_nodes_by_path(path)
    parties = []
    for rp_node in rp_nodes:
        party = get_responsible_party(rp_node)
        parties.append((pid, path[-1], party))
    return parties


def get_creators(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.CREATOR])


def get_contacts(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.CONTACT])


def get_associated_parties(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.ASSOCIATEDPARTY])


def get_metadata_providers(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.METADATAPROVIDER])


def get_project_personnel(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.PROJECT, names.PERSONNEL])


def get_related_project_personnel(pid, eml_node):
    return get_responsible_parties(pid, eml_node, [names.DATASET, names.PROJECT, names.RELATED_PROJECT, names.PERSONNEL])


def get_all_responsible_parties(pid, eml_node):
    responsible_parties = []
    responsible_parties.extend(get_creators(pid, eml_node))
    responsible_parties.extend(get_contacts(pid, eml_node))
    responsible_parties.extend(get_associated_parties(pid, eml_node))
    responsible_parties.extend(get_metadata_providers(pid, eml_node))
    responsible_parties.extend(get_project_personnel(pid, eml_node))
    responsible_parties.extend(get_related_project_personnel(pid, eml_node))
    return responsible_parties


def get_data_table_descriptions(eml_node):
    data_table_descriptions = []
    description_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE, names.ENTITYDESCRIPTION])
    for description_node in description_nodes:
        data_table_descriptions.extend(parse_text_type(description_node))

    return data_table_descriptions


def get_method_step_descriptions(eml_node):
    method_step_descriptions = []

    description_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.METHODS,
                                                         names.METHODSTEP, names.DESCRIPTION])
    for description_node in description_nodes:
        method_step_descriptions.extend(parse_text_type(description_node))

    return method_step_descriptions


def get_all_titles_and_abstracts(eml_node):
    dataset_title = get_dataset_title(eml_node)
    dataset_abstract = get_dataset_abstract(eml_node)
    project_titles = []
    project_abstracts = []
    all_text = dataset_title[0] + " "
    if dataset_abstract:
        all_text += ' '.join(dataset_abstract)
    for title in project_titles:
        all_text += title[0] + " "
    for abstract in project_abstracts:
        all_text += ' '.join(dataset_abstract)
    return dataset_title, dataset_abstract, project_titles, project_abstracts, all_text


def get_dataset_geographic_descriptions(eml_node):
    geographic_descriptions = []
    geographic_description_nodes = eml_node.find_all_nodes_by_path([names.DATASET,
                                                                    names.COVERAGE,
                                                                    names.GEOGRAPHICCOVERAGE,
                                                                    names.GEOGRAPHICDESCRIPTION])
    for geographic_description_node in geographic_description_nodes:
        description = geographic_description_node.content
        if description:
            geographic_descriptions.append(description)

    return geographic_descriptions


def parse_eml_file(filename):
    pid = filename[:-4]
    filepath = f'{Config.EML_FILES_PATH}/{filename}'
    eml_node = xml_to_json(filepath)
    return pid, eml_node


def collect_responsible_parties(filename, added_package_ids, removed_package_ids):
    if added_package_ids == [] and removed_package_ids == []:
        return
    responsible_parties = db.parse_responsible_parties_file(filename)
    db.prune_pids(responsible_parties, removed_package_ids)
    # write the existing responsible parties, minus the ones to be removed
    output_filename = f'{Config.EML_FILES_PATH}/{filename}'
    with open(output_filename, 'w') as output_file:
        for _, val in responsible_parties.items():
            for line in val:
                output_file.write(line)
                output_file.write('\n')
    # now, append the new responsible parties
    with open(output_filename, 'a') as output_file:
        filelist = get_existing_eml_files()
        for index, filename in enumerate(filelist):
            pid = os.path.splitext(filename)[0]
            if added_package_ids and pid not in added_package_ids:
                continue
            pid, eml_node = parse_eml_file(filename)
            if eml_node:
                responsible_parties = get_all_responsible_parties(pid, eml_node)
                for responsible_party in responsible_parties:
                    output_file.write(str(responsible_party))
                    output_file.write('\n')
                    output_file.flush()


def collect_titles_and_abstracts(output_filename):
    with open(output_filename, 'w') as output_file:
        filelist = get_existing_eml_files()
        for index, filename in enumerate(filelist):
            # if filename.startswith('edi.'):  # TEMP
            pid = filename[:-4]
            filepath = f'{Config.EML_FILES_PATH}/{filename}'
            eml_node = xml_to_json(filepath)
            if not eml_node:
                continue
            dataset_title, dataset_abstract, project_titles, project_abstracts, all_text = get_all_titles_and_abstracts(eml_node)
            all_text = all_text.replace('\n', '')
            output_file.write(f'{pid}\n')
            output_file.write(f'{all_text}\n')


def collect_method_step_descriptions(output_filename):
    with open(output_filename, 'w') as output_file:
        filelist = get_existing_eml_files()
        for index, filename in enumerate(filelist):
            # if filename.startswith('edi.'):  # TEMP
            pid = filename[:-4]
            filepath = f'{Config.EML_FILES_PATH}/{filename}'
            eml_node = xml_to_json(filepath)
            if not eml_node:
                continue
            text = get_data_table_descriptions(eml_node)
            text = get_method_step_descriptions(eml_node)
            # all_text = all_text.replace('\n', '')
            # output_file.write(f'{pid}\n')
            # output_file.write(f'{all_text}\n')


def collect_text_for_scope(scope):
    text = []
    filelist = get_existing_eml_files()
    for index, filename in enumerate(filelist):
        if filename.startswith(scope):
            filepath = f'{Config.EML_FILES_PATH}/{filename}'
            eml_node = xml_to_json(filepath)
            if not eml_node:
                continue
            text1 = get_data_table_descriptions(eml_node)
            text2 = [] #get_method_step_descriptions(eml_node)
            *_, text3 = get_all_titles_and_abstracts(eml_node)
            text.append(' '.join(text1) + ' '.join(text2) + text3)
    return ' '.join(text)


def collect_text(pids):
    text = []
    for pid in pids:
        filename = pid + '.xml'
        filepath = f'{Config.EML_FILES_PATH}/{filename}'
        eml_node = xml_to_json(filepath)
        if not eml_node:
            continue
        text1 = [] #get_data_table_descriptions(eml_node)
        text2 = [] #get_method_step_descriptions(eml_node)
        *_, text3 = get_all_titles_and_abstracts(eml_node)
        text.append(' '.join(text1) + ' '.join(text2) + text3)
    return ' '.join(text)


def init_eml_text_by_pid():
    global eml_text_by_pid

    filename = 'eml_text_by_pid.pkl'
    filepath = f'{Config.DATA_FILES_PATH}/{filename}'

    try:
        with open(filepath, 'rb') as pf:
            eml_text_by_pid = pickle.load(pf)
            print(f'Init harvest EML text... count={len(eml_text_by_pid)}')
            return eml_text_by_pid
    except FileNotFoundError:
        pass


def save_eml_text_by_pid():
    global eml_text_by_pid

    filename = 'eml_text_by_pid.pkl'
    filepath = f'{Config.DATA_FILES_PATH}/{filename}'

    with open(filepath, 'wb') as pickle_file:
        pickle.dump(eml_text_by_pid, pickle_file)


def clean_projects(projects):
    cleaned = []
    for project in projects:
        project.project_title = clean_list(project.project_title)
        project.project_abstract = clean_list(project.project_abstract)
        cleaned.append(project)
    return cleaned


def clean_list(l):
    return [nlp.clean(s, remove_digits=True) for s in l]


def harvest_eml_text(pids=None):
    global eml_text_by_pid

    if not pids:
        pids = db.get_all_pids()

    init_eml_text_by_pid()

    count = len(eml_text_by_pid)
    for pid in pids:
        if eml_text_by_pid.get(pid):
            continue
        filename = pid + '.xml'
        filepath = f'{Config.EML_FILES_PATH}/{filename}'
        eml_node = xml_to_json(filepath)
        if not eml_node:
            continue

        dataset_title = get_dataset_title(eml_node)
        dataset_abstract = get_dataset_abstract(eml_node)
        dataset_keywords = get_keywords(eml_node)
        datatable_descriptions = get_data_table_descriptions(eml_node)
        dataset_geographic_descriptions = get_dataset_geographic_descriptions(eml_node)
        method_step_descriptions = get_method_step_descriptions(eml_node)
        projects, related_projects = harvest_projects(eml_node)

        eml_text_by_pid[pid] = EMLText(
            dataset_title=clean_list(dataset_title),
            dataset_abstract=clean_list(dataset_abstract),
            dataset_keywords=clean_list(dataset_keywords),
            datatable_descriptions=clean_list(datatable_descriptions),
            dataset_geographic_descriptions=clean_list(dataset_geographic_descriptions),
            method_step_descriptions=clean_list(method_step_descriptions),
            projects=clean_projects(projects),
            related_projects=clean_projects(related_projects)
        )

        count += 1
        if count % 100 == 0:
            print(f'Saving... count={count}')
            save_eml_text_by_pid()

    save_eml_text_by_pid()


def concat_project_text(projects, related_projects,
                        components=(EMLTextComponents.PROJECT_TITLES,
                                    EMLTextComponents.PROJECT_ABSTRACTS,
                                    EMLTextComponents.RELATED_PROJECT_TITLES,
                                    EMLTextComponents.RELATED_PROJECT_ABSTRACTS)):
    project_text = ''
    for project in projects:
        if EMLTextComponents.PROJECT_TITLES in components:
            project_text += ' '.join(project.project_title)
        if EMLTextComponents.PROJECT_ABSTRACTS in components:
            project_text += ' '.join(project.project_abstract)
    for related_project in related_projects:
        if EMLTextComponents.PROJECT_TITLES in components:
            project_text += ' '.join(related_project.project_title)
        if EMLTextComponents.PROJECT_ABSTRACTS in components:
            project_text += ' '.join(related_project.project_abstract)
    return project_text


def get_eml_text_as_string(pid, components=(EMLTextComponents.DATASET_TITLE,
                                            EMLTextComponents.DATASET_ABSTRACT,
                                            EMLTextComponents.DATASET_KEYWORDS,
                                            EMLTextComponents.DATATABLE_DESCRIPTIONS,
                                            EMLTextComponents.PROJECT_TITLES,
                                            EMLTextComponents.PROJECT_ABSTRACTS,
                                            EMLTextComponents.RELATED_PROJECT_TITLES,
                                            EMLTextComponents.RELATED_PROJECT_ABSTRACTS)):
    if not eml_text_by_pid:
        init_eml_text_by_pid()

    eml_string = ''
    eml_text = eml_text_by_pid.get((pid))
    if not eml_text:
        return ''
    if EMLTextComponents.DATASET_TITLE in components:
        eml_string += ' '.join(eml_text.dataset_title)
    if EMLTextComponents.DATASET_ABSTRACT in components:
        eml_string += ' '.join(eml_text.dataset_abstract)
    if EMLTextComponents.DATASET_KEYWORDS in components:
        eml_string += ' '.join(eml_text.dataset_keywords)
    if EMLTextComponents.DATATABLE_DESCRIPTIONS in components:
        eml_string += ' '.join(eml_text.datatable_descriptions)
    if EMLTextComponents.DATASET_GEO_DESCRIPTIONS in components:
        eml_string += ' '.join(eml_text.dataset_geographic_descriptions)
    if EMLTextComponents.METHOD_STEP_DESCRIPTIONS in components:
        eml_string += ' '.join(eml_text.method_step_descriptions)
    eml_string += concat_project_text(eml_text.projects,
                                      eml_text.related_projects,
                                      components)
    return eml_string


def get_eml_text_as_string_by_name(givenname, surname,
                                   components=(EMLTextComponents.DATASET_TITLE,
                                            EMLTextComponents.DATASET_ABSTRACT,
                                            EMLTextComponents.DATASET_KEYWORDS,
                                            EMLTextComponents.DATATABLE_DESCRIPTIONS,
                                            EMLTextComponents.PROJECT_TITLES,
                                            EMLTextComponents.PROJECT_ABSTRACTS,
                                            EMLTextComponents.RELATED_PROJECT_TITLES,
                                            EMLTextComponents.RELATED_PROJECT_ABSTRACTS)):

    if not eml_text_by_pid:
        init_eml_text_by_pid()

    pids = db.get_pids_by_name(givenname, surname)
    eml_string = ''
    for pid in pids:
        eml_string += get_eml_text_as_string(pid, components)
    return eml_string


def get_eml_keywords_by_name(givenname, surname):
    if not eml_text_by_pid:
        init_eml_text_by_pid()

    pids = db.get_pids_by_name(givenname, surname)
    keywords = []
    for pid in pids:
        eml_text = eml_text_by_pid.get((pid))
        if not eml_text:
            continue
        keywords.extend(eml_text.dataset_keywords)
    return keywords


if __name__ == '__main__':
    pass

    # collect_responsible_parties(f'{EML_FILES_PATH}/responsible_parties.txt')
    # harvest_eml_text()
    # raise ValueError
    #
    # from collections import Counter
    # givenname = 'Diana'
    # surname = 'Wall'
    # keywords = get_eml_keywords_by_name(givenname, surname)
    # counter = Counter(keywords)
    # highest = counter.most_common(20)
    #
    # text = get_eml_text_as_string_by_name(givenname, surname)
    # lemmas = nlp.lemmatize(text)
    # counter = Counter(lemmas)
    # highest = counter.most_common(30)

    # pids = db.get_all_pids()
    # harvest_eml_text(pids)
    # for pid in pids:
    #     eml_string = get_eml_text_as_string(pid)

    # text = collect_text_for_scope('knb-lter-sbc')
    # collect_method_step_descriptions('foo.txt')
    # filename = 'knb-lter-fce.1143.2.xml'
    # pid, eml_node = parse_eml_file(filename)
    # if eml_node:
    #     text1 = get_data_table_descriptions(eml_node)
    #     text2 = get_method_step_descriptions(eml_node)
    #     *_, text3 = get_all_titles_and_abstracts(eml_node)
    #     all_text = ' '.join(text1) + ' '.join(text1) + text3
    # collect_responsible_parties(f'{EML_FILES_PATH}/responsible_parties.txt')
    # collect_titles_and_abstracts(f'{EML_FILES_PATH}/titles_and_abstracts.txt')

