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


"""Trigger download job for a provider.

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""

import argparse
import os
import sys

import requests

gitlab_base_url = 'https://git.nomics.world'
api_base_url = gitlab_base_url + '/api/v4'
fetchers_group_url = gitlab_base_url + '/dbnomics-fetchers'


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


def trigger_download_job(project_id, token):
    return request_api('POST', '/projects/{}/ref/master/trigger/pipeline?token={}&variables[JOB]=download'.format(
        project_id, token))


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    args = parser.parse_args()

    fetcher_project = get_project("{}-fetcher".format(args.provider_slug))

    triggers = get_triggers(fetcher_project['id'])
    assert len(triggers) <= 1, triggers  # Projects are designed to have only one trigger.
    trigger = triggers[0] if triggers else None

    trigger_download_job(fetcher_project['id'], trigger['token'])

    fetcher_repo_url = '/'.join([fetchers_group_url, args.provider_slug + '-fetcher'])
    fetcher_jobs_url = fetcher_repo_url + '/-/jobs'
    print('Check job: {}'.format(fetcher_jobs_url))

    return 0


if __name__ == '__main__':
    sys.exit(main())
