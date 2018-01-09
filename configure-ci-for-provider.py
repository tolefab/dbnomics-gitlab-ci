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
default_importer_project_id = 42  # Project ID of repo https://git.nomics.world/dbnomics/dbnomics-importer/
source_data_group_url = gitlab_base_url + '/dbnomics-source-data'


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


def delete_deploy_keys(project_id, title):
    deploy_keys = get_deploy_keys(project_id)
    for deploy_key in deploy_keys:
        if deploy_key['title'] == title:
            delete_deploy_key(project_id, deploy_key['id'])
            log.debug('deleted deploy key of project ID {}: {}'.format(project_id, deploy_key))


def enable_deploy_key(project_id, deploy_key_id):
    return request_api('POST', '/projects/{}/deploy_keys/{}/enable'.format(project_id, deploy_key_id))


def get_deploy_key(project_id, title):
    deploy_keys = get_deploy_keys(project_id)
    for deploy_key in deploy_keys:
        if deploy_key['title'] == title:
            return deploy_key
    return None


def get_deploy_keys(project_id):
    return request_api('GET', '/projects/{}/deploy_keys'.format(project_id))


# Hooks


def create_hook(project_id, url):
    return request_api('POST', '/projects/{}/hooks'.format(project_id), json={
        'url': url,
        'push_events': True,
        'enable_ssl_verification': True,
    })


def delete_hook(project_id, hook_id):
    return request_api('DELETE', '/projects/{}/hooks/{}'.format(project_id, hook_id))


def delete_hooks(project_id, trigger_project_id):
    hooks = get_hooks(project_id)
    for hook in hooks:
        if '/projects/{}'.format(trigger_project_id) in hook['url']:
            delete_hook(project_id, hook['id'])
            log.debug('deleted hook of project ID {}: {}'.format(project_id, hook))


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


def delete_trigger(project_id, trigger_id):
    return request_api('DELETE', '/projects/{}/triggers/{}'.format(project_id, trigger_id))


def delete_triggers(project_id, description):
    triggers = get_triggers(project_id)
    for trigger in triggers:
        if trigger['description'] == description:
            delete_trigger(project_id, trigger['id'])
            log.debug('deleted trigger of project ID {}: {}'.format(project_id, trigger))


def get_triggers(project_id):
    return request_api('GET', '/projects/{}/triggers'.format(project_id))


# Variables


def create_variable(project_id, key, value):
    return request_api('POST', '/projects/{}/variables'.format(project_id), json={"key": key, "value": value})


def delete_variable(project_id, key):
    return request_api('DELETE', '/projects/{}/variables/{}'.format(project_id, key), raise_for_status=False)


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--debug-http', action='store_true', help='display http.client debug messages')
    parser.add_argument('--importer-project-id', type=int, default=default_importer_project_id,
                        help='ID of the dbnomics-importer project')
    parser.add_argument('--no-delete', action='store_true', help='disable deletion of existing items - for debugging')
    parser.add_argument('--no-create', action='store_true', help='disable creation of items - for debugging')
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

    # Get projects IDs. Importer project ID is passed by a script argument, because it almost never changes.
    fetcher_project = get_project("{}-fetcher".format(args.provider_slug))
    log.debug('fetcher project ID: {}'.format(fetcher_project['id']))
    source_data_project = get_project("{}-source-data".format(args.provider_slug))
    log.debug('source data project ID: {}'.format(source_data_project['id']))
    json_data_project = get_project("{}-json-data".format(args.provider_slug))
    log.debug('JSON data project ID: {}'.format(json_data_project['id']))

    # Get importer repo trigger.
    importer_triggers = get_triggers(args.importer_project_id)
    assert len(importer_triggers) == 1, importer_triggers
    importer_trigger = importer_triggers[0]
    log.debug('importer repo trigger fetched')

    if not args.no_delete:
        # Delete fetcher repo secret variable.
        delete_variable(fetcher_project['id'], "SSH_PRIVATE_KEY")
        log.debug('SSH_PRIVATE_KEY variable deleted')

        # Delete source data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        delete_deploy_keys(source_data_project['id'], title=args.provider_slug)
        log.debug('source repo deploy key deleted')

        # Delete JSON data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        delete_deploy_keys(json_data_project['id'], title=args.provider_slug)
        log.debug('JSON repo deploy key deleted')

        # Delete fetcher repo triggers, named as the provider slug (keep eventual other triggers).
        delete_triggers(fetcher_project['id'], description=args.provider_slug)
        log.debug('fetcher repo trigger deleted')

        # Delete hooks of the source data repo, that trigger the converter job (keep eventual other hooks).
        delete_hooks(source_data_project['id'], trigger_project_id=fetcher_project['id'])
        log.debug('source repo hook deleted')

        # Delete hooks of the JSON data repo, that trigger the Solr indexation job (keep eventual other hooks).
        delete_hooks(json_data_project['id'], trigger_project_id=args.importer_project_id)
        log.debug('JSON repo hook deleted')

    if not args.no_create:
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
        with open(ssh_key_file_path) as ssh_key_file:
            private_key = ssh_key_file.read()

        # Create trigger in the fetcher repo.
        fetcher_trigger = create_trigger(fetcher_project['id'], description=args.provider_slug)
        log.debug('trigger created')

        # Create a hook in the source data repo, to trigger the convert job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[JOB]=convert'.format(
            fetcher_project['id'], fetcher_trigger['token'])
        hook = create_hook(source_data_project['id'], url=trigger_url)
        log.debug('created hook for convert job')

        # Create or update SSH_PRIVATE_KEY secret variable.
        create_variable(fetcher_project['id'], 'SSH_PRIVATE_KEY', private_key)
        log.debug('SSH_PRIVATE_KEY variable created')

        # Add public key to source data repo.
        # See bug https://gitlab.com/gitlab-org/gitlab-ce/issues/37458 – Deploy keys added via API do not trigger CI
        # Workaround: create deploy key manually.
        # deploy_key = create_deploy_key(source_data_project['id'], {
        #     'title': args.provider_slug,
        #     'key': public_key,
        #     'can_push': True,
        # })
        # log.debug('deploy key created in source repository')
        source_data_repo_url = '/'.join([source_data_group_url, args.provider_slug + '-source-data'])
        source_data_repository_settings_url = source_data_repo_url + '/settings/repository'
        print(
            '\n\n\nWARNING! Please create deploy key manually:\n'
            '1. Go to {}\n'.format(source_data_repository_settings_url),
            '2. Copy-paste the public key below:\n',
            public_key, '\n',
            '3. Check "Write access allowed"'
        )
        input("Press Enter when done...")
        deploy_key = get_deploy_key(source_data_project['id'], title=args.provider_slug)
        assert deploy_key is not None

        # Enable public key in JSON data repo.
        enable_deploy_key(json_data_project['id'], deploy_key['id'])
        log.debug('deploy key enabled in JSON repository')

        # Create a hook in the JSON data repo, to trigger the Solr indexation job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[PROVIDER_SLUG]={}'.format(
            args.importer_project_id, importer_trigger['token'], args.provider_slug)
        hook = create_hook(json_data_project['id'], url=trigger_url)
        log.debug('created hook for indexation job')

        # Create pipeline schedule in the fetcher repo.
        # "dummy" provider should not be scheduled.
        if args.provider_slug != 'dummy':
            pipeline_schedules = get_pipeline_schedules(fetcher_project['id'])
            assert len(pipeline_schedules) <= 1, pipeline_schedules
            pipeline_schedule = pipeline_schedules[0] if pipeline_schedules else None
            if pipeline_schedule is None:
                pipeline_schedule = create_pipeline_schedule(fetcher_project['id'], args.provider_slug)
                create_pipeline_schedule_variable(fetcher_project['id'], pipeline_schedule['id'])
                log.debug('created pipeline schedule')

    return 0


if __name__ == '__main__':
    sys.exit(main())
