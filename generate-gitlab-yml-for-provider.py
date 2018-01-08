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


"""Print to stdout a `.gitlab-ci.yml` file, for a provider.

Uses the template `gitlab-ci.template.yml`.

The goal of this script is to centralize a reference configuration file,
but each fetcher still has its own configuration file committed in its repository.
"""

import argparse
import logging
import os
import sys

script_dir_path = os.path.dirname(os.path.abspath(__file__))


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    args = parser.parse_args()

    with open(os.path.join(script_dir_path, "gitlab-ci.template.yml")) as template_file:
        template = template_file.read()

    print(template.replace("{provider_slug}", args.provider_slug.lower()))

    return 0


if __name__ == '__main__':
    sys.exit(main())
