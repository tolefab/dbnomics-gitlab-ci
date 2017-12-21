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


"""Open GitLab-CI URLs in a browser useful to control Continuous Integrations for a provider.

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs
"""

import argparse
import sys
import webbrowser

gitlab_base_url = 'https://git.nomics.world'
dbnomics_group_url = gitlab_base_url + '/dbnomics'
fetchers_group_url = gitlab_base_url + '/dbnomics-fetchers'
source_data_group_url = gitlab_base_url + '/dbnomics-source-data'
json_data_group_url = gitlab_base_url + '/dbnomics-json-data'


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('provider_slug', help='slug of the provider to configure')
    args = parser.parse_args()

    fetcher_repo_url = '/'.join([fetchers_group_url, args.provider_slug + '-fetcher'])

    fetcher_jobs_url = fetcher_repo_url + '/-/jobs'
    webbrowser.open(fetcher_jobs_url)

    fetcher_ci_settings_url = fetcher_repo_url + '/settings/ci_cd'
    webbrowser.open(fetcher_ci_settings_url)

    source_data_repo_url = '/'.join([source_data_group_url, args.provider_slug + '-source-data'])

    source_data_repository_settings_url = source_data_repo_url + '/settings/repository'
    webbrowser.open(source_data_repository_settings_url)

    source_data_integrations_settings_url = source_data_repo_url + '/settings/integrations'
    webbrowser.open(source_data_integrations_settings_url)

    json_data_repo_url = '/'.join([json_data_group_url, args.provider_slug + '-json-data'])

    json_data_repository_settings_url = json_data_repo_url + '/settings/repository'
    webbrowser.open(json_data_repository_settings_url)

    json_data_repo_url = '/'.join([json_data_group_url, args.provider_slug + '-json-data'])

    json_data_integrations_settings_url = json_data_repo_url + '/settings/integrations'
    webbrowser.open(json_data_integrations_settings_url)

    importer_jobs_url = 'https://git.nomics.world/dbnomics/dbnomics-importer/-/jobs'
    webbrowser.open(importer_jobs_url)

    schedules_url = fetcher_repo_url + '/pipeline_schedules'
    webbrowser.open(schedules_url)

    return 0


if __name__ == '__main__':
    sys.exit(main())
