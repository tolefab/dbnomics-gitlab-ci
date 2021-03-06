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


"""Create repositories for a provider in DBnomics GitLab-CI:
   - dbnomics-fetchers/XXX-fetcher
   - dbnomics-source-data/XXX-source-data
   - dbnomics-json-data/XXX-json-data
"""


import argparse
import http.client
import logging
import os
import sys

import gitlab
from dotenv import load_dotenv
from gitlab.v4.objects import VISIBILITY_PUBLIC

args = None
log = logging.getLogger(__name__)


def main():
    global args
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
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

    load_dotenv()

    if args.provider_slug != args.provider_slug.lower():
        parser.error("provider_slug must be lowercase.")

    if not os.getenv('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    if args.gitlab_url.endswith('/'):
        args.gitlab_url = args.gitlab_url[:-1]

    gl = gitlab.Gitlab(args.gitlab_url, private_token=os.getenv('PRIVATE_TOKEN'), api_version=4)
    gl.auth()

    # Create fetcher repo
    fetchers_namespace_name = 'dbnomics-fetchers'
    fetchers_namespaces = gl.namespaces.list(search=fetchers_namespace_name)
    assert len(fetchers_namespaces) == 1, fetchers_namespaces
    fetchers_namespace = fetchers_namespaces[0]

    fetcher_project_name = '{}-fetcher'.format(args.provider_slug)
    existing_fetcher_projects = gl.projects.list(search=fetcher_project_name)
    if existing_fetcher_projects:
        log.info('fetcher repositories exist: {}'.format(existing_fetcher_projects))
    else:
        fetcher_project = gl.projects.create({
            'name': fetcher_project_name,
            'namespace_id': fetchers_namespace.id,
            'description': "DBnomics fetcher for series from {} database.".format(args.provider_slug),
            'visibility': VISIBILITY_PUBLIC,
        })
        http_url_to_repo = fetcher_project.http_url_to_repo
        log.info('Repository created: {}'.format(http_url_to_repo))
        log.debug('JSON info: {}'.format(fetcher_project))

    # Create source data repo
    source_data_namespace_name = 'dbnomics-source-data'
    source_data_namespaces = gl.namespaces.list(search=source_data_namespace_name)
    assert len(source_data_namespaces) == 1, source_data_namespaces
    source_data_namespace = source_data_namespaces[0]

    source_data_project_name = '{}-source-data'.format(args.provider_slug)
    existing_source_data_projects = gl.projects.list(search=source_data_project_name)
    if existing_source_data_projects:
        log.info('source data repositories exist: {}'.format(existing_source_data_projects))
    else:
        source_data_project = gl.projects.create({
            'name': source_data_project_name,
            'namespace_id': source_data_namespace.id,
            'description': "Source data as downloaded from provider {}".format(args.provider_slug),
            'visibility': VISIBILITY_PUBLIC,
        })
        http_url_to_repo = source_data_project.http_url_to_repo
        log.info('Repository created: {}'.format(http_url_to_repo))
        log.debug('JSON info: {}'.format(source_data_project))

    # Create json data repo
    json_data_namespace_name = 'dbnomics-json-data'
    json_data_namespaces = gl.namespaces.list(search=json_data_namespace_name)
    assert len(json_data_namespaces) == 1, json_data_namespaces
    json_data_namespace = json_data_namespaces[0]

    json_data_project_name = '{}-json-data'.format(args.provider_slug)
    existing_json_data_projects = gl.projects.list(search=json_data_project_name)
    if existing_json_data_projects:
        log.info('JSON data repositories exist: {}'.format(existing_json_data_projects))
    else:
        json_data_project = gl.projects.create({
            'name': json_data_project_name,
            'namespace_id': json_data_namespace.id,
            'description': "JSON data as converted from source data of provider {}".format(args.provider_slug),
            'visibility': VISIBILITY_PUBLIC,
        })
        http_url_to_repo = json_data_project.http_url_to_repo
        log.info('Repository created: {}'.format(http_url_to_repo))
        log.debug('JSON info: {}'.format(json_data_project))

    return 0


if __name__ == '__main__':
    sys.exit(main())
