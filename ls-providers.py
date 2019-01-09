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


"""Print all providers slugs on stdout. Useful to combine other scripts like:

./ls-providers.py | xargs -n1 ./trigger-job-for-provider.py validate
"""


import argparse
import os
import subprocess
import sys
from pathlib import Path

import gitlab

GENERATED_OBJECTS_TAG = 'CI jobs'

script_dir = Path(__file__).resolve().parent


def iter_scheduled_fetcher_projects(gl, fetcher_projects):
    for fetcher_group_project in fetcher_projects:
        fetcher_project = gl.projects.get(fetcher_group_project.id)
        provider_slug = fetcher_project.name.replace("-fetcher", "")
        for pipeline_schedule in fetcher_project.pipelineschedules.list():
            if pipeline_schedule.description == provider_slug + ' ' + GENERATED_OBJECTS_TAG and pipeline_schedule.active:
                yield fetcher_project
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--only-scheduled', action='store_true', help='display providers with an active scheduler')
    args = parser.parse_args()

    gl = gitlab.Gitlab(url=args.gitlab_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    dbnomics_fetchers_group = gl.groups.get('dbnomics-fetchers')

    fetcher_projects = dbnomics_fetchers_group.projects.list(order_by="name", sort="asc", all=True)
    if args.only_scheduled:
        fetcher_projects = iter_scheduled_fetcher_projects(gl, fetcher_projects)

    for fetcher_project in fetcher_projects:
        if not fetcher_project.name.endswith("-fetcher"):
            # Skip project named "management"
            continue
        if fetcher_project.name.startswith("dummy"):
            continue
        provider_slug = fetcher_project.name.replace("-fetcher", "")
        print(provider_slug)

    return 0


if __name__ == '__main__':
    sys.exit(main())
