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


"""Trigger job for a provider (download or convert).

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""

import argparse
import logging
import os
import sys

import requests

gitlab_base_url = 'https://git.nomics.world'
api_base_url = gitlab_base_url + '/api/v4'
fetchers_group_url = gitlab_base_url + '/dbnomics-fetchers'

log = logging.getLogger(__name__)


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
    return response.json()


def get_project(name):
    projects = request_api('GET', '/projects?search={}'.format(name))
    assert len(projects) == 1, projects
    return projects[0]


def get_triggers(project_id):
    return request_api('GET', '/projects/{}/triggers'.format(project_id))


def trigger_job(project_id, ref, token, job_name):
    return request_api('POST', '/projects/{}/ref/{}/trigger/pipeline?token={}&variables[JOB]={}'.format(
        project_id, ref, token, job_name))


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('job_name', choices=['download', 'convert'], help='job name to trigger')
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--ref', default='master', help='ref of fetcher repo (branch name) on which to start the job')
    parser.add_argument('-v', '--verbose', action='store_true', help='display logging messages from debug level')
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(asctime)s:%(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
        stream=sys.stdout,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if not os.environ.get('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    fetcher_project = get_project("{}-fetcher".format(args.provider_slug))

    triggers = get_triggers(fetcher_project['id'])
    nb_triggers = len(triggers)
    if nb_triggers > 1:
        log.error("Project should have one trigger at most, exit.")
        return 1
    elif nb_triggers == 0:
        log.error("Project does not have any trigger, exit.")
        return 1
    else:
        trigger = triggers[0]

    trigger_job(fetcher_project['id'], args.ref, trigger['token'], args.job_name)

    fetcher_repo_url = '/'.join([fetchers_group_url, args.provider_slug + '-fetcher'])
    fetcher_jobs_url = fetcher_repo_url + '/-/jobs'
    print('Check job: {}'.format(fetcher_jobs_url))

    return 0


if __name__ == '__main__':
    sys.exit(main())
