#! /usr/bin/env python3


# dbnomics-gitlab-ci -- Scripts around DBnomics GitLab-CI
# By: Christophe Benz <christophe.benz@cepremap.org>
#
# Copyright (C) 2017-2018 Cepremap
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


"""Configure a provider in DBnomics GitLab-CI.

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""


import argparse
import http.client
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import gitlab
import requests

args = None
log = logging.getLogger(__name__)

dbnomics_fetchers_namespace = "dbnomics-fetchers"
dbnomics_source_data_namespace = "dbnomics-source-data"
dbnomics_json_data_namespace = "dbnomics-json-data"
default_data_model_project_id = 40  # Project ID of repo https://git.nomics.world/dbnomics/dbnomics-data-model/
default_importer_project_id = 42  # Project ID of repo https://git.nomics.world/dbnomics/dbnomics-importer/
GENERATED_OBJECTS_TAG = 'CI jobs'


def find(f, seq):
    for item in seq:
        if f(item):
            return item
    return None


def generate_ssh_key():
    with tempfile.NamedTemporaryFile(prefix='_' + args.provider_slug) as tmpfile:
        private_key_path = Path(tmpfile.name)
    subprocess.run(['ssh-keygen', '-f', str(private_key_path), '-t', 'rsa',
                    '-C', '{}-fetcher@db.nomics.world'.format(args.provider_slug), '-b', '4096', '-N', ''],
                   check=True)
    public_key_path = private_key_path.with_suffix('.pub')
    public_key = public_key_path.read_text()
    public_key_path.unlink()
    private_key = private_key_path.read_text()
    private_key_path.unlink()
    return (public_key, private_key)


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--debug-http', action='store_true', help='display http.client debug messages')
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--data-model-project-id', type=int, default=default_data_model_project_id,
                        help='ID of the dbnomics-data-model project')
    parser.add_argument('--importer-project-id', type=int, default=default_importer_project_id,
                        help='ID of the dbnomics-importer project')
    parser.add_argument('--no-delete', action='store_true', help='disable deletion of existing items - for debugging')
    parser.add_argument('--no-create', action='store_true', help='disable creation of items - for debugging')
    parser.add_argument('--purge', action='store_true', help='delete all triggers, hooks and deploy keys')
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

    if args.provider_slug != args.provider_slug.lower():
        parser.error("provider_slug must be lowercase.")

    if args.gitlab_url.endswith('/'):
        args.gitlab_url = args.gitlab_url[:-1]

    api_base_url = args.gitlab_url + '/api/v4'
    source_data_group_url = args.gitlab_url + '/' + dbnomics_source_data_namespace
    json_data_group_url = args.gitlab_url + '/' + dbnomics_json_data_namespace

    gl = gitlab.Gitlab(args.gitlab_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    gl.auth()
    if args.debug_http:
        gl.enable_debug()

    # Get projects IDs. Importer project ID is passed by a script argument, because it almost never changes.
    fetcher_project = gl.projects.get("{}/{}-fetcher".format(dbnomics_fetchers_namespace, args.provider_slug))
    log.debug('fetcher project: {}'.format(fetcher_project))
    source_data_project = gl.projects.get(
        "{}/{}-source-data".format(dbnomics_source_data_namespace, args.provider_slug))
    log.debug('source data project: {}'.format(source_data_project))
    json_data_project = gl.projects.get("{}/{}-json-data".format(dbnomics_json_data_namespace, args.provider_slug))
    log.debug('JSON data project: {}'.format(json_data_project))
    data_model_project = gl.projects.get(args.data_model_project_id)
    log.debug('data model project: {}'.format(data_model_project))
    importer_project = gl.projects.get(args.importer_project_id)
    log.debug('importer project: {}'.format(importer_project))

    # Get data model repo trigger.
    data_model_triggers = data_model_project.triggers.list()
    assert len(data_model_triggers) == 1, data_model_triggers
    data_model_trigger = data_model_triggers[0]
    log.debug('importer repo trigger fetched')

    # Get importer repo trigger.
    importer_triggers = importer_project.triggers.list()
    assert len(importer_triggers) == 1, importer_triggers
    importer_trigger = importer_triggers[0]
    log.debug('importer repo trigger fetched')

    if not args.no_delete:
        # Delete fetcher repo secret variable.
        variable = find(
            lambda variable: variable.key == "SSH_PRIVATE_KEY",
            fetcher_project.variables.list(),
        )
        if variable is not None:
            variable.delete()
            log.debug('SSH_PRIVATE_KEY variable deleted')

        # Delete source data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        keys = filter(
            lambda key: args.purge or key.title == args.provider_slug + ' ' + GENERATED_OBJECTS_TAG,
            source_data_project.keys.list(),
        )
        for key in keys:
            key.delete()
            log.debug('source repo deploy key deleted')

        # Delete JSON data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        keys = filter(
            lambda key: args.purge or key.title == args.provider_slug + ' ' + GENERATED_OBJECTS_TAG,
            json_data_project.keys.list(),
        )
        for key in keys:
            key.delete()
            log.debug('JSON repo deploy key deleted')

        # Delete fetcher repo triggers, named as the provider slug (keep eventual other triggers).
        triggers = filter(
            lambda trigger: args.purge or trigger.description == GENERATED_OBJECTS_TAG,
            fetcher_project.triggers.list(),
        )
        for trigger in triggers:
            trigger.delete()
            log.debug('fetcher repo trigger deleted')

        # Delete hooks of the source data repo, that trigger the converter job (keep eventual other hooks).
        hooks = filter(
            lambda hook: args.purge or '/projects/{}/'.format(fetcher_project.id) in hook.url,
            source_data_project.hooks.list(),
        )
        for hook in hooks:
            hook.delete()
            log.debug('source repo hook deleted')

        # Delete hooks of the JSON data repo.
        hooks = filter(
            lambda hook: (args.purge
                          or '/projects/{}/'.format(data_model_project.id) in hook.url
                          or '/projects/{}/'.format(importer_project.id) in hook.url),
            json_data_project.hooks.list(),
        )
        for hook in hooks:
            hook.delete()
            log.debug('JSON repo hook deleted')

        # Delete pipeline schedule of the fetcher repo.
        pipeline_schedules = filter(
            lambda pipeline_schedule: args.purge or pipeline_schedule.description ==
            args.provider_slug + ' ' + GENERATED_OBJECTS_TAG,
            fetcher_project.pipelineschedules.list()
        )
        for pipeline_schedule in pipeline_schedules:
            pipeline_schedule.delete()
            log.debug('pipeline schedule of fetcher repo deleted')

    if not args.no_create:
        public_key, private_key = generate_ssh_key()

        # Create trigger in the fetcher repo.
        fetcher_trigger = fetcher_project.triggers.create({"description": GENERATED_OBJECTS_TAG})
        log.debug('trigger created: {}'.format(fetcher_trigger))

        # Create a hook in the source data repo, to trigger the convert job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[JOB]=convert'.format(
            fetcher_project.id, fetcher_trigger.token)
        source_data_project.hooks.create({"url": trigger_url})
        log.debug('created hook for convert job')

        # Create or update SSH_PRIVATE_KEY secret variable.
        fetcher_project.variables.create({"key": "SSH_PRIVATE_KEY", "value": private_key})
        log.debug('SSH_PRIVATE_KEY variable created')

        # Create deploy key to source data repo.
        key = source_data_project.keys.create({
            'title': args.provider_slug + ' ' + GENERATED_OBJECTS_TAG,
            'key': public_key,
            'can_push': True,
        })
        log.debug('deploy key created for source repository')

        # Enable deploy key for JSON data repo.
        json_data_project.keys.enable(key.id)
        json_data_project.keys.update(key.id, {'can_push': True})
        log.debug('deploy key enabled for JSON repository')

        # Create a hook in the JSON data repo, to trigger the Solr indexation job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[PROVIDER_SLUG]={}'.format(
            args.importer_project_id, importer_trigger.token, args.provider_slug)
        hook = json_data_project.hooks.create({"url": trigger_url})
        log.debug('created hook for indexation job')

        # Create a hook in the JSON data repo, to trigger the validation job.
        trigger_url = api_base_url + '/projects/{}/ref/master/trigger/pipeline?token={}&variables[PROVIDER_SLUG]={}'.format(
            args.data_model_project_id, data_model_trigger.token, args.provider_slug)
        hook = json_data_project.hooks.create({"url": trigger_url})
        log.debug('created hook for validation job')

        # Create pipeline schedule in the fetcher repo.
        # "dummy" provider should not be scheduled.
        if args.provider_slug != 'dummy':
            hour, minute = args.schedule_time
            pipeline_schedule = fetcher_project.pipelineschedules.create({
                'active': True,
                'description': args.provider_slug + ' ' + GENERATED_OBJECTS_TAG,
                'ref': 'master',
                'cron': '{} {} * * *'.format(minute, hour),
            })
            pipeline_schedule.variables.create({"key": "JOB", "value": "download"})
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
