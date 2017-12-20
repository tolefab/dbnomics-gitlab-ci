#! /usr/bin/env python3


# dbnomics-gitlab-ci -- Scripts around DB.nomics GitLab-CI
# By: Christophe Benz <christophe.benz@cepremap.org>
#
# Copyright (C) 2017 Cepremap
# https://git.nomics.world/dbnomics/dbnomics-gitlab-ci
#
# dbnomics-gitlab-ci is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# dbnomics-gitlab-ci is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Configure a provider in DB.nomics GitLab-CI.

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""


import argparse
import http.client
import logging
import os
import subprocess
import sys
import tempfile

import requests

args = None
log = logging.getLogger(__name__)

gitlab_base_url = 'https://git.nomics.world'
api_base_url = gitlab_base_url + '/api/v4'


def request_api(method, path, headers={}, json=None, raise_for_status=True):
    assert method in {'GET', 'POST', 'PUT', 'DELETE'}, method
    f = requests.get if method == 'GET' \
        else requests.post if method == 'POST' \
        else requests.put if method == 'PUT' \
        else requests.delete
    headers_ = {'PRIVATE-TOKEN': os.environ.get('PRIVATE_TOKEN')}
    headers_.update(headers)
    response = f(
        api_base_url + path,
        headers=headers_,
        json=json,
    )
    if raise_for_status:
        response.raise_for_status()
    return response.json() \
        if method != 'DELETE' \
        else None


# Deploy keys


def create_deploy_key(project_id, data):
    return request_api(
        'POST',
        '/projects/{}/deploy_keys'.format(project_id),
        headers={'Content-Type': 'application/json'},
        json=data,
    )


def delete_deploy_key(project_id, deploy_key_id):
    return request_api('DELETE', '/projects/{}/deploy_keys/{}'.format(project_id, deploy_key_id))


def enable_deploy_key(project_id, deploy_key_id):
    return request_api('POST', '/projects/{}/deploy_keys/{}/enable'.format(project_id, deploy_key_id))


def get_deploy_key(project_id):
    return request_api('GET', '/projects/{}/deploy_keys'.format(project_id))


# Hooks


def create_hook(project_id, url):
    return request_api('POST', '/projects/{}/hooks'.format(project_id), json={
        'url': url,
        'push_events': True,
        'enable_ssl_verification': True,
    })


def get_hooks(project_id):
    return request_api('GET', '/projects/{}/hooks'.format(project_id))


# Pipeline schedules


def create_pipeline_schedule(project_id, provider_slug):
    return request_api('POST', '/projects/{}/pipeline_schedules'.format(project_id), json={
        'active': True,
        'description': provider_slug,
        'ref': 'master',
        'cron': '0 1 * * *',
    })


def create_pipeline_schedule_variable(project_id, pipeline_schedule_id):
    return request_api('POST', '/projects/{}/pipeline_schedules/{}/variables'.format(project_id, pipeline_schedule_id), json={
        'key': 'JOB',
        'value': 'download',
    })


def get_pipeline_schedules(project_id):
    return request_api('GET', '/projects/{}/pipeline_schedules'.format(project_id))


# Projects


def get_project(name):
    projects = request_api('GET', '/projects?search={}'.format(name))
    assert len(projects) == 1, projects
    return projects[0]


# Triggers

def create_trigger(project_id, description):
    return request_api('POST', '/projects/{}/triggers'.format(project_id), json={'description': description})


def get_triggers(project_id):
    return request_api('GET', '/projects/{}/triggers'.format(project_id))


# Variables


def create_variable(project_id, key, value):
    return request_api('POST', '/projects/{}/variables'.format(project_id), json={"key": key, "value": value})


def get_variable(project_id, key):
    variable = request_api('GET', '/projects/{}/variables/{}'.format(project_id, key), raise_for_status=False)
    if variable.get('message'):
        # variable is a dict returned by requests, representing the HTTP error as JSON.
        return None
    return variable


def update_variable(project_id, key, value):
    return request_api('PUT', '/projects/{}/variables/{}'.format(project_id, key), json={"key": key, "value": value},
                       raise_for_status=False)


def upsert_variable(project_id, key, value):
    return create_variable(project_id, key, value) \
        if get_variable(project_id, key) is None \
        else update_variable(project_id, key, value)


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--debug-http', action='store_true', help='display http.client debug messages')
    parser.add_argument('-v', '--verbose', action='store_true', help='display logging messages from debug level')
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(asctime)s:%(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stdout,
    )

    logging.getLogger("urllib3").setLevel(logging.DEBUG if args.debug_http else logging.WARNING)
    if args.debug_http:
        http.client.HTTPConnection.debuglevel = 1

    # Get projects IDs.

    fetcher_project = get_project("{}-fetcher".format(args.provider_slug))
    log.debug('fetcher project ID: {}'.format(fetcher_project['id']))
    source_data_project = get_project("{}-source-data".format(args.provider_slug))
    log.debug('source data project ID: {}'.format(source_data_project['id']))
    json_data_project = get_project("{}-json-data".format(args.provider_slug))
    log.debug('JSON data project ID: {}'.format(json_data_project['id']))

    # Remove source data repo deploy keys.

    source_data_deploy_keys = get_deploy_key(source_data_project['id'])
    for source_data_deploy_key in source_data_deploy_keys:
        delete_deploy_key(source_data_project['id'], source_data_deploy_key['id'])
        log.debug('deleted source data project deploy key: {}'.format(source_data_deploy_key))

    # Remove JSON data repo deploy keys.

    json_data_deploy_keys = get_deploy_key(json_data_project['id'])
    for json_data_deploy_key in json_data_deploy_keys:
        delete_deploy_key(json_data_project['id'], json_data_deploy_key['id'])
        log.debug('deleted JSON data project deploy key: {}'.format(json_data_deploy_key))

    # Generate a deploy key.

    with tempfile.NamedTemporaryFile(prefix='_' + args.provider_slug) as tmpfile:
        ssh_key_file_path = tmpfile.name
    print('Press "Enter" when passphrase is asked.')
    subprocess.run(
        [
            'ssh-keygen', '-f', ssh_key_file_path, '-t', 'rsa', '-C',
            args.provider_slug + '-fetcher@db.nomics.world', '-b', '4096',
        ],
        check=True,
    )
    with open('{}.pub'.format(ssh_key_file_path)) as ssh_key_file:
        public_key = ssh_key_file.read()
    deploy_key = create_deploy_key(source_data_project['id'], {
        'title': args.provider_slug,
        'key': public_key,
        'can_push': True,
    })
    enable_deploy_key(json_data_project['id'], deploy_key['id'])

    # Create or update SSH_PRIVATE_KEY secret variable.

    with open(ssh_key_file_path) as ssh_key_file:
        private_key = ssh_key_file.read()
    upsert_variable(fetcher_project['id'], 'SSH_PRIVATE_KEY', private_key)
    log.debug('SSH_PRIVATE_KEY variable created or updated (not printed here)')

    # Create trigger if no one exists.

    triggers = get_triggers(fetcher_project['id'])
    assert len(triggers) <= 1, triggers  # Projects are designed to have only one trigger.
    trigger = triggers[0] if triggers else None
    if trigger is None:
        log.debug('trigger was not found')
        trigger = create_trigger(fetcher_project['id'], description=args.provider_slug)
    log.debug('trigger created or updated (not printed here)')

    # Create hook for convert job.

    hooks = get_hooks(source_data_project['id'])
    assert len(hooks) <= 1, hooks  # Projects are designed to have only one hook.
    hook = hooks[0] if hooks else None
    if hook is None:
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[JOB]=convert'.format(
            fetcher_project['id'],
            trigger['token'],
        )
        hook = create_hook(source_data_project['id'], url=trigger_url)
        log.debug('created hook for convert job')

    # Create hook for indexation job.

    importer_project_id = 42
    triggers = get_triggers(importer_project_id)
    assert len(triggers) == 1, triggers  # dbnomics-importer does not have to be updated by this script.
    trigger = triggers[0]
    hooks = get_hooks(json_data_project['id'])
    assert len(hooks) <= 1, hooks  # Projects are designed to have only one hook.
    hook = hooks[0] if hooks else None
    if hook is None:
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[PROVIDER_SLUG]={}'.format(
            importer_project_id,
            trigger['token'],
            args.provider_slug,
        )
        hook = create_hook(json_data_project['id'], url=trigger_url)
        log.debug('created hook for indexation job')

    # Create pipeline schedule.

    pipeline_schedules = get_pipeline_schedules(fetcher_project['id'])
    assert len(pipeline_schedules) <= 1, pipeline_schedules  # Projects are designed to have only one hook.
    pipeline_schedule = pipeline_schedules[0] if pipeline_schedules else None
    if pipeline_schedule is None:
        pipeline_schedule = create_pipeline_schedule(fetcher_project['id'], args.provider_slug)
        create_pipeline_schedule_variable(fetcher_project['id'], pipeline_schedule['id'])
        log.debug('created pipeline schedule')

    return 0


if __name__ == '__main__':
    sys.exit(main())
