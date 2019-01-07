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


"""Trigger a job for a specific provider.

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""

import argparse
import logging
import os
import sys

import gitlab

dbnomics_namespace = "dbnomics"
dbnomics_fetchers_namespace = "dbnomics-fetchers"
log = logging.getLogger(__name__)


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('job_name', choices=['download', 'convert', 'index', 'validate'], help='job name to trigger')
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    parser.add_argument('--gitlab-url', default='https://git.nomics.world', help='base URL of GitLab instance')
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

    if args.gitlab_url.endswith('/'):
        args.gitlab_url = args.gitlab_url[:-1]

    gl = gitlab.Gitlab(args.gitlab_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    gl.auth()

    dbnomics_group_url = args.gitlab_url + '/' + dbnomics_namespace
    fetchers_group_url = args.gitlab_url + '/' + dbnomics_fetchers_namespace

    if args.job_name in {"download", "convert"}:
        fetcher_project = gl.projects.get("{}/{}-fetcher".format(dbnomics_fetchers_namespace, args.provider_slug))
        log.debug('fetcher project: {}'.format(fetcher_project))

        fetcher_repo_url = '/'.join([fetchers_group_url, args.provider_slug + '-fetcher'])

        triggers = fetcher_project.triggers.list()
        if len(triggers) != 1:
            fetcher_ci_settings_url = fetcher_repo_url + '/settings/ci_cd'
            log.error("Project should have one trigger, exit. See {}".format(fetcher_ci_settings_url))
            return 1
        trigger = triggers[0]
        log.debug('trigger of fetcher repo fetched')

        pipeline_variables = {'JOB': args.job_name}
        fetcher_project.trigger_pipeline(args.ref, trigger.token, pipeline_variables)
        log.debug('pipeline triggered for ref {!r} with variables {!r}'.format(args.ref, pipeline_variables))

        fetcher_jobs_url = fetcher_repo_url + '/-/jobs'
        print('Check job: {}'.format(fetcher_jobs_url))
    elif args.job_name == "validate":
        data_model_repo_url = '/'.join([dbnomics_group_url, 'dbnomics-data-model'])

        data_model_project = gl.projects.get("{}/dbnomics-data-model".format(dbnomics_namespace))
        log.debug('data_model project: {}'.format(data_model_project))

        triggers = data_model_project.triggers.list()
        if len(triggers) != 1:
            data_model_ci_settings_url = data_model_repo_url + '/settings/ci_cd'
            log.error("Project should have one trigger, exit. See {}".format(data_model_ci_settings_url))
            return 1
        trigger = triggers[0]
        log.debug('trigger of data_model repo fetched')

        pipeline_variables = {'PROVIDER_SLUG': args.provider_slug}
        data_model_project.trigger_pipeline(args.ref, trigger.token, pipeline_variables)
        log.debug('pipeline triggered for ref {!r} with variables {!r}'.format(args.ref, pipeline_variables))

        data_model_jobs_url = data_model_repo_url + '/-/jobs'
        print('Check job: {}'.format(data_model_jobs_url))
    else:
        assert args.job_name == "index", args.job_name

        importer_repo_url = '/'.join([dbnomics_group_url, 'dbnomics-importer'])

        importer_project = gl.projects.get("{}/dbnomics-importer".format(dbnomics_namespace))
        log.debug('importer project: {}'.format(importer_project))

        triggers = importer_project.triggers.list()
        if len(triggers) != 1:
            importer_ci_settings_url = importer_repo_url + '/settings/ci_cd'
            log.error("Project should have one trigger, exit. See {}".format(importer_ci_settings_url))
            return 1
        trigger = triggers[0]
        log.debug('trigger of importer repo fetched')

        pipeline_variables = {'PROVIDER_SLUG': args.provider_slug}
        importer_project.trigger_pipeline(args.ref, trigger.token, pipeline_variables)
        log.debug('pipeline triggered for ref {!r} with variables {!r}'.format(args.ref, pipeline_variables))

        importer_jobs_url = importer_repo_url + '/-/jobs'
        print('Check job: {}'.format(importer_jobs_url))

    return 0


if __name__ == '__main__':
    sys.exit(main())
