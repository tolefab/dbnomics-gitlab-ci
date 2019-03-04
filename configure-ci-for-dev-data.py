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


"""Configure data and json test repos for given provider:
- get private key from prod source-data and enable them for source and json dev data repos
"""


import argparse
import http.client
import logging
import os
import sys

import gitlab
from dotenv import load_dotenv

args = None
log = logging.getLogger(__name__)

dbnomics_fetchers_namespace = "dbnomics-fetchers"
dbnomics_source_data_namespace = "dbnomics-source-data"
dbnomics_dev_data_namespace = "dbnomics-data-dev"


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider')
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--no-delete', action='store_true', help='disable deletion of existing items - for debugging')
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

    if not os.getenv('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    if args.provider_slug != args.provider_slug.lower():
        parser.error("provider_slug must be lowercase.")

    if args.gitlab_url.endswith('/'):
        args.gitlab_url = args.gitlab_url[:-1]
    api_base_url = args.gitlab_url + '/api/v4'

    gl = gitlab.Gitlab(args.gitlab_url, private_token=os.getenv('PRIVATE_TOKEN'), api_version=4)
    gl.auth()
    if args.debug_http:
        gl.enable_debug()

    # Get projects IDs. Importer project ID is passed by a script argument, because it almost never changes.
    fetcher_project = gl.projects.get("{}/{}-fetcher".format(dbnomics_fetchers_namespace, args.provider_slug))
    log.debug('fetcher project: {}'.format((fetcher_project.name, fetcher_project.id)))
    prod_source_data_project = gl.projects.get(
        "{}/{}-source-data".format(dbnomics_source_data_namespace, args.provider_slug))
    dev_source_data_project = gl.projects.get(
        "{}/{}-source-data".format(dbnomics_dev_data_namespace, args.provider_slug))
    log.debug('prod source data project: {}'.format((prod_source_data_project.name, prod_source_data_project.id)))
    log.debug('dev source data project: {}'.format((dev_source_data_project.name, dev_source_data_project.id)))
    dev_json_data_project = gl.projects.get("{}/{}-json-data".format(dbnomics_dev_data_namespace, args.provider_slug))
    log.debug('dev json data project: {}'.format((dev_json_data_project.name, dev_json_data_project.id)))

    public_keyname = args.provider_slug + ' CI jobs'
    if not args.no_delete:
        # Delete source data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        keys = filter(
            lambda key: args.purge or key.title == public_keyname,
            dev_source_data_project.keys.list(),
        )
        for key in keys:
            key.delete()
            log.debug('source repo deploy key deleted')

        # Delete JSON data repo deploy keys, named as the provider slug (keep eventual other deploy keys).
        keys = filter(
            lambda key: args.purge or key.title == public_keyname,
            dev_json_data_project.keys.list(),
        )
        for key in keys:
            key.delete()
            log.debug('JSON repo deploy key deleted')

    # Get public key from existing prod source-data repo
    keys = list(filter(lambda key: key.title == public_keyname, prod_source_data_project.keys.list()))
    assert len(keys) == 1, "No ssh public key named{!r} found for {!r}".format(
        public_keyname, prod_source_data_project.name)
    public_key = keys[0]

    # Enable deploy key to source data repo
    key = dev_source_data_project.keys.create({
        'title': public_keyname,
        'key': public_key.attributes['key'],
        'can_push': True,
    })
    log.debug('deploy key created for dev source repository')

    # Enable deploy key for JSON data repo
    dev_json_data_project.keys.enable(key.id)
    dev_json_data_project.keys.update(key.id, {'can_push': True})
    log.debug('deploy key enabled for dev JSON repository')

    return 0


if __name__ == '__main__':
    sys.exit(main())
