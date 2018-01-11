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

import gitlab
import requests

args = None
log = logging.getLogger(__name__)

dbnomics_fetchers_namespace = "dbnomics-fetchers"
dbnomics_source_data_namespace = "dbnomics-source-data"
dbnomics_json_data_namespace = "dbnomics-json-data"
default_importer_project_id = 42  # Project ID of repo https://git.nomics.world/dbnomics/dbnomics-importer/


def find(f, seq):
    for item in seq:
        if f(item):
            return item
    return None


def generate_ssh_key():
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
    return public_key, private_key


# Pipeline schedules are not ready yet: https://github.com/python-gitlab/python-gitlab/pull/398

def create_pipeline_schedule(api_base_url, project_id, provider_slug, schedule_time):
    hour, minute = schedule_time
    response = requests.post(
        api_base_url + '/projects/{}/pipeline_schedules'.format(project_id),
        headers={'PRIVATE-TOKEN': os.environ.get('PRIVATE_TOKEN')},
        json={
            'active': True,
            'description': provider_slug,
            'ref': 'master',
            'cron': '{} {} * * *'.format(minute, hour),
        },
    )
    response.raise_for_status()
    return response.json()


def create_pipeline_schedule_variable(api_base_url, project_id, pipeline_schedule_id, key, value):
    response = requests.post(
        api_base_url + '/projects/{}/pipeline_schedules/{}/variables'.format(project_id, pipeline_schedule_id),
        headers={'PRIVATE-TOKEN': os.environ.get('PRIVATE_TOKEN')},
        json={'key': key, 'value': value},
    )
    response.raise_for_status()
    return response.json()


def get_pipeline_schedules(api_base_url, project_id):
    response = requests.get(
        api_base_url + '/projects/{}/pipeline_schedules'.format(project_id),
        headers={'PRIVATE-TOKEN': os.environ.get('PRIVATE_TOKEN')},
    )
    response.raise_for_status()
    return response.json()


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--debug-http', action='store_true', help='display http.client debug messages')
    parser.add_argument('--gitlab-base-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--importer-project-id', type=int, default=default_importer_project_id,
                        help='ID of the dbnomics-importer project')
    parser.add_argument('--no-delete', action='store_true', help='disable deletion of existing items - for debugging')
    parser.add_argument('--no-create', action='store_true', help='disable creation of items - for debugging')
    parser.add_argument('--schedule-time', default='1:0', type=parse_time, help='time to run the scheduled pipeline')
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

    if not os.environ.get('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    if args.gitlab_base_url.endswith('/'):
        args.gitlab_base_url = args.gitlab_base_url[:-1]

    api_base_url = args.gitlab_base_url + '/api/v4'
    source_data_group_url = args.gitlab_base_url + '/dbnomics-source-data'

    gl = gitlab.Gitlab(args.gitlab_base_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    gl.auth()

    # Get projects IDs. Importer project ID is passed by a script argument, because it almost never changes.
    fetcher_project = gl.projects.get("{}/{}-fetcher".format(dbnomics_fetchers_namespace, args.provider_slug))
    log.debug('fetcher project: {}'.format(fetcher_project))
    source_data_project = gl.projects.get(
        "{}/{}-source-data".format(dbnomics_source_data_namespace, args.provider_slug))
    log.debug('source data project: {}'.format(source_data_project))
    json_data_project = gl.projects.get("{}/{}-json-data".format(dbnomics_json_data_namespace, args.provider_slug))
    log.debug('JSON data project: {}'.format(json_data_project))
    importer_project = gl.projects.get(args.importer_project_id)
    log.debug('importer project: {}'.format(importer_project))

    # Get importer repo trigger.
    importer_triggers = importer_project.triggers.list()
    assert len(importer_triggers) == 1, importer_triggers
    importer_trigger = importer_triggers[0]
    log.debug('importer repo trigger fetched')

    if not args.no_delete:
        # Delete fetcher repo secret variable.
        variable = find(lambda variable: variable.key == "SSH_PRIVATE_KEY", fetcher_project.variables.list())
        if variable is not None:
            variable.delete()
            log.debug('SSH_PRIVATE_KEY variable deleted')

        # Delete source data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        key = find(lambda key: key.title == args.provider_slug, source_data_project.keys.list())
        if key is not None:
            key.delete()
            log.debug('source repo deploy key deleted')

        # Delete JSON data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        key = find(lambda key: key.title == args.provider_slug, json_data_project.keys.list())
        if key is not None:
            key.delete()
            log.debug('JSON repo deploy key deleted')

        # Delete fetcher repo triggers, named as the provider slug (keep eventual other triggers).
        trigger = find(lambda trigger: trigger.description == args.provider_slug, fetcher_project.triggers.list())
        if trigger is not None:
            trigger.delete()
            log.debug('fetcher repo trigger deleted')

        # Delete hooks of the source data repo, that trigger the converter job (keep eventual other hooks).
        hook = find(lambda hook: '/projects/{}/'.format(fetcher_project.id) in hook.url,
                    source_data_project.hooks.list())
        if hook is not None:
            hook.delete()
            log.debug('source repo hook deleted')

        # Delete hooks of the JSON data repo, that trigger the Solr indexation job (keep eventual other hooks).
        hook = find(lambda hook: '/projects/{}/'.format(importer_project.id) in hook.url,
                    json_data_project.hooks.list())
        if hook is not None:
            hook.delete()
            log.debug('JSON repo hook deleted')

    if not args.no_create:
        public_key, private_key = generate_ssh_key()

        # Create trigger in the fetcher repo.
        fetcher_trigger = fetcher_project.triggers.create({"description": args.provider_slug})
        log.debug('trigger created: {}'.format(fetcher_trigger))

        # Create a hook in the source data repo, to trigger the convert job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[JOB]=convert'.format(
            fetcher_project.id, fetcher_trigger.token)
        source_data_project.hooks.create({"url": trigger_url})
        log.debug('created hook for convert job')

        # Create or update SSH_PRIVATE_KEY secret variable.
        fetcher_project.variables.create({"key": "SSH_PRIVATE_KEY", "value": private_key})
        log.debug('SSH_PRIVATE_KEY variable created')

        # Add public key to source data repo.
        # See bug https://gitlab.com/gitlab-org/gitlab-ce/issues/37458 – Deploy keys added via API do not trigger CI
        # Workaround: create deploy key manually.
        # deploy_key = create_deploy_key(source_data_project.id, {
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
        key = find(lambda key: key.title == args.provider_slug, source_data_project.keys.list())
        assert key is not None
        log.debug('deploy key created and enabled for source repository')

        # Enable public key in JSON data repo.
        json_data_project.keys.enable(key.id)
        log.debug('deploy key enabled for JSON repository')

        # Create a hook in the JSON data repo, to trigger the Solr indexation job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[PROVIDER_SLUG]={}'.format(
            args.importer_project_id, importer_trigger.token, args.provider_slug)
        hook = json_data_project.hooks.create({"url": trigger_url})
        log.debug('created hook for indexation job')

        # Create pipeline schedule in the fetcher repo.
        # "dummy" provider should not be scheduled.
        if args.provider_slug != 'dummy':
            pipeline_schedules = get_pipeline_schedules(api_base_url, fetcher_project.id)
            assert len(pipeline_schedules) <= 1, pipeline_schedules
            pipeline_schedule = pipeline_schedules[0] if pipeline_schedules else None
            if pipeline_schedule is None:
                pipeline_schedule = create_pipeline_schedule(api_base_url, fetcher_project.id, args.provider_slug,
                                                             schedule_time=args.schedule_time)
                create_pipeline_schedule_variable(api_base_url, fetcher_project.id, pipeline_schedule.id,
                                                  key='JOB', value='download')
                log.debug('created pipeline schedule')

    return 0


def parse_time(time):
    """Transform a "hour:minute" string to a (hour, minute) tuple of integers.

    >>> parse_time('')
    Traceback (most recent call last):
    ValueError: Invalid time ''
    >>> parse_time(':')
    Traceback (most recent call last):
    ValueError: Invalid time ':'
    >>> parse_time('1')
    Traceback (most recent call last):
    ValueError: Invalid time '1'
    >>> parse_time('1:')
    Traceback (most recent call last):
    ValueError: Invalid time '1:'
    >>> parse_time('1:1:1')
    Traceback (most recent call last):
    ValueError: Invalid time '1:1:1'
    >>> parse_time('99:99')
    Traceback (most recent call last):
    ValueError: Invalid time '99:99'
    >>> parse_time('-1:-1')
    Traceback (most recent call last):
    ValueError: Invalid time '-1:-1'
    >>> parse_time('0:0')
    (0, 0)
    >>> parse_time('1:1')
    (1, 1)
    >>> parse_time('23:59')
    (23, 59)
    """
    parts = time.split(':')
    exc = ValueError('Invalid time {!r}'.format(time))
    if len(parts) != 2:
        raise exc
    hour, minute = parts
    try:
        hour = int(hour)
        minute = int(minute)
    except ValueError:
        raise exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise exc
    return (hour, minute)


if __name__ == '__main__':
    sys.exit(main())
