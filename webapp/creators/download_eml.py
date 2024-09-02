#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: download_eml

:Synopsis: A standalone app to download EML files from PASTA in asynchronous fashion. Used to "prime the pump" on
    a server. Once a baseline of EML files has been downloaded, the update API should be used to get newly added
    EML files. See creators.py.

:Author:
    ide

:Created:
    6/1/21
"""

from aiohttp import ClientSession
import asyncio
from datetime import datetime
import os
import requests
import sys
import time
from typing import List




from webapp.config import Config

PASTA_BASE = f'https://{Config.PASTA_HOST}'
EML_FILES_PATH = Config.EML_FILES_PATH
MAX_RETRIES = 5

TO_SKIP = ['ecotrends', 'msb-cap', 'msb-paleon', 'msb-tempbiodev', 'lter-landsat', 'lter-landsat-ledaps']


def get_text(url):
    r = requests.get(url)
    r.encoding = 'utf-8'
    return r.text


def get_scopes():
    url = f'{PASTA_BASE}/package/eml/'
    scopes = get_text(url).replace('\n', ' ')
    return scopes.split()


def get_identifiers(scope):
    url = f'{PASTA_BASE}/package/eml/{scope}/'
    identifiers = requests.get(url).text.replace('\n', ' ')
    return identifiers.split()


def get_versions(scope, identifier):
    url = f'{PASTA_BASE}/package/eml/{scope}/{identifier}/'
    versions = get_text(url).replace('\n', ' ')
    return versions.split()


def get_latest_version(scope, identifier):
    url = f'{PASTA_BASE}/package/eml/{scope}/{identifier}/'
    versions = get_text(url).replace('\n', ' ')
    return versions.split()[-1]


def get_eml(scope, identifier, version):
    current_time = datetime.now().strftime('%H:%M:%S')
    print(f'{current_time} - Getting EML for {scope}.{identifier}.{version}', flush=True)
    url = f'{PASTA_BASE}/package/metadata/eml/{scope}/{identifier}/{version}'
    pid = f'{scope}.{identifier}.{version}'

    retries = 0
    while retries < MAX_RETRIES:
        try:
            r = requests.get(url)
            r.encoding = 'utf-8'
            eml = r.text
            return eml  # no exception, so break out of the retry loop
        except:
            print('Exception: ', sys.exc_info()[0], flush=True)
            retries += 1
            print('retries:', retries, ' ', pid, '  getting metadata', flush=True)
            if retries >= MAX_RETRIES:
                print('Reached max retries getting metadata. Giving up...', flush=True)
                return None
            time.sleep(1)
    return None


def get_existing_eml_files():
    return os.listdir(Config.EML_FILES_PATH)


def get_all_eml():
    existing_files = get_existing_eml_files()
    scopes = get_scopes()
    for scope in scopes:
        if scope in TO_SKIP:
            continue
        identifiers = get_identifiers(scope)
        for identifier in identifiers:
            version = get_latest_version(scope, identifier)
            if f'{scope}.{identifier}.{version}.xml' in existing_files:
                print(f'Skipping {scope}.{identifier}.{version}', flush=True)
                continue
            eml = get_eml(scope, identifier, version)
            if not eml:
                continue
            filepath = f'{Config.EML_FILES_PATH}/{scope}.{identifier}.{version}.xml'
            with open(filepath, 'w', encoding='utf-8') as fp:
                fp.write(eml)


BURST_SIZE = 10

async def get_response(url: str, session: ClientSession, **kwargs) -> str:
    resp = await session.request(method='GET', url=url, **kwargs)
    resp.raise_for_status()
    return await resp.text()


async def get_metadata(scope: str, identifier: str, session: ClientSession):
    # Get latest version number
    retries = 0
    version = None
    while retries < MAX_RETRIES:
        try:
            url = f'{PASTA_BASE}/package/eml/{scope}/{identifier}/'
            versions = get_text(url).replace('\n', ' ')
            version = versions.split()[-1]
            break  # no exception, so break out of the retry loop
        except:
            print('Exception: ', sys.exc_info()[0], flush=True)
            retries += 1
            print(f'retries:{retries}  {scope}.{identifier} getting latest version', flush=True)
            if retries >= MAX_RETRIES:
                print('Reached max retries getting latest version. Giving up...', flush=True)
                return
            time.sleep(1)
    if not version:
        return
    # Get the EML metadata
    retries = 0
    eml = None
    while retries < MAX_RETRIES:
        try:
            url = f'{PASTA_BASE}/package/metadata/eml/{scope}/{identifier}/{version}'
            eml = await get_response(url, session)
            break  # no exception, so break out of the retry loop
        except:
            print('Exception: ', sys.exc_info()[0], flush=True)
            retries += 1
            print(f'retries:{retries}  {scope}.{identifier}.{version}  getting metadata', flush=True)
            if retries >= MAX_RETRIES:
                print('Reached max retries getting metadata. Giving up...', flush=True)
                return
            time.sleep(1)
    if not eml:
        return
    filepath = f'{Config.EML_FILES_PATH}/{scope}.{identifier}.{version}.xml'
    with open(filepath, 'w', encoding='utf-8') as fp:
        fp.write(eml)


async def run_get_metadata_tasks(scope: str, identifiers: List[str]):
    async with ClientSession() as session:
        tasks = [get_metadata(scope, identifier, session) for identifier in identifiers]
        await asyncio.gather(*tasks)


async def get_all_eml_async():
    existing_files = get_existing_eml_files()
    scopes = get_scopes()
    for scope in scopes:
        if scope in TO_SKIP:
            continue
        current_time = datetime.now().strftime('%H:%M:%S')
        print(f'{current_time} - Starting scope {scope}', flush=True)
        identifiers = get_identifiers(scope)
        count = 0
        identifiers_burst = []
        for identifier in identifiers:
            identifiers_burst.append(identifier)
            count += 1
            if count % BURST_SIZE == 0:
                # Create tasks to get metadata
                # Use the asyncio.run statement outside of jupyter. Use the await form within jupyter.
                #                 asyncio.run(run_get_metadata_tasks(scope, identifiers_burst))
                await run_get_metadata_tasks(scope, identifiers_burst)
                time.sleep(1)
                identifiers_burst = []
        #         asyncio.run(run_get_metadata_tasks(scope, identifiers_burst))
        await run_get_metadata_tasks(scope, identifiers_burst)


def get_all():
    asyncio.run(get_all_eml_async())


def get_single_eml_file(scope, identifier, version):
    eml = get_eml(scope, identifier, version)
    if eml:
        filepath = f'/Users/jide/Downloads/{scope}.{identifier}.{version}.xml'
        with open(filepath, 'w', encoding='utf-8') as fp:
            fp.write(eml)
