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
import subprocess
import sys
from pathlib import Path

import gitlab

script_dir = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    args = parser.parse_args()

    gl = gitlab.Gitlab(url=args.gitlab_url)
    dbnomics_fetchers_group = gl.groups.get('dbnomics-fetchers')
    for project in dbnomics_fetchers_group.projects.list(order_by="name", sort="asc", all=True):
        provider_slug = project.name.replace("-fetcher", "")
        print(provider_slug)

    return 0


if __name__ == '__main__':
    sys.exit(main())
