#! /usr/bin/env python3


# dbnomics-gitlab-ci -- Scripts around DBnomics GitLab-CI
# By: Christophe Benz <christophe.benz@cepremap.org>
#
# Copyright (C) 2017-2020 Cepremap
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


"""Cancel all the pipelines of a GitLab project."""

# Inspired from https://gitlab.com/gitlab-org/gitlab/issues/16259#note_214895132

import argparse
import itertools
import logging
import os
import sys

import daiquiri
import gitlab
from dotenv import load_dotenv

logger = daiquiri.getLogger(__name__)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "project",
        help='GitLab project to cancel its pipelines (example: "organization1/project1")',
    )
    parser.add_argument(
        "--gitlab-url",
        default=os.getenv("GITLAB_URL", "https://git.nomics.world"),
        help="base URL of GitLab instance",
    )
    parser.add_argument(
        "--debug", action="store_true", help="display debug logging messages",
    )
    args = parser.parse_args()

    daiquiri.setup(level=logging.DEBUG if args.debug else logging.INFO)

    gl = gitlab.Gitlab(
        args.gitlab_url, private_token=os.getenv("PRIVATE_TOKEN"), api_version=4
    )
    gl.auth()
    if args.debug:
        gl.enable_debug()

    project = gl.projects.get(args.project)
    pipelines = itertools.chain.from_iterable(
        project.pipelines.list(aslist=False, all=True, status=status)
        for status in ["running", "pending"]
    )
    for pipeline in pipelines:
        logger.info("Cancelling pipeline {} ({})".format(pipeline.id, pipeline.status))
        pipeline.cancel()


if __name__ == "__main__":
    sys.exit(main())
