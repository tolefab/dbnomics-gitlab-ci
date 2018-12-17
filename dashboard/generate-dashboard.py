#! /usr/bin/env python3


# dbnomics-gitlab-ci -- Scripts around DBnomics GitLab-CI
# By: Christophe Benz <christophe.benz@cepremap.org>
#
# Copyright (C) 2018 Cepremap
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


"""Generate a dashboard for all providers, viewing:

- if scheduler is enabled or not; if it is: next run at, cron string
- last N downloads with status, created_at, started_at, finished_at, duration; link to job page
- last N converts with the same infos than downloads
- last N indexations with the same infos than downloads

See https://git.nomics.world/dbnomics-fetchers/documentation/wikis/Setup-CI-jobs

The following definitions help developing in a REPL environment:

numeric_level = "DEBUG"
logging.basicConfig(level=numeric_level, stream=sys.stdout)
logging.getLogger("urllib3").setLevel(logging.INFO)
log.debug("Test")

from unittest.mock import MagicMock
args = MagicMock(solr_url="http://localhost:8983/solr/dbnomics")

provider_slug = 'scsmich'
"""

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from string import Template

import gitlab
import humanfriendly
import pysolr
from solrq import Q
from toolz import take

dbnomics_namespace = "dbnomics"
dbnomics_fetchers_namespace = "dbnomics-fetchers"
dbnomics_source_data_namespace = "dbnomics-source-data"
dbnomics_json_data_namespace = "dbnomics-json-data"
dbnomics_importer_nb_jobs = 100
star_providers_slugs = ["bis", "ecb", "eurostat", "imf", "oecd", "ilo", "wto", "wb"]

args = None
log = logging.getLogger(__name__)
script_dir = Path(__file__).parent


def local_time_tag(datetime_str):
    return """<local-time datetime='{datetime_str}' day='numeric' month='short' year='numeric' hour='numeric' minute='numeric'>
        {datetime_str}
    </local-time>""".format(datetime_str=datetime_str)


def get_pipeline_schedule(project):
    """Return the only pipeline schedule of the project. Fetchers should not have more than one."""
    pipeline_schedules = project.pipelineschedules.list()
    assert len(pipeline_schedules) <= 1, pipeline_schedules
    return pipeline_schedules[0] if pipeline_schedules else None


def get_fetcher_job_variables(job):
    """Return job variables specific to dbnomics-importer: JOB.

    Getting job variables is not supported by GitLab API v4.
    """
    try:
        job_trace_bytes = job.trace()
    except gitlab.exceptions.GitlabGetError:
        # Sometimes the trace is missing. It happened when we deleted some of them accidentally.
        log.exception("Error fetching trace for job %r", job)
        return None

    job_trace = job_trace_bytes.decode('utf-8')
    values = re.findall('Running job ([^$ ]+)', job_trace)
    assert len(values) <= 1, values
    if not values:
        return None

    return {"JOB": values[0]}


def get_importer_job_variables(job):
    """Return job variables specific to dbnomics-importer: PROVIDER_SLUG.

    Getting job variables is not supported by GitLab API v4.
    """
    job_trace = job.trace().decode('utf-8')
    values = re.findall('Importing provider ([^$. ]+)', job_trace)
    assert len(values) <= 1, values
    return {"PROVIDER_SLUG": values[0] if values else None}


def print_html_dashboard(fetchers_projects, importer_project, pipeline_schedule_by_fetcher_id, jobs_by_fetcher_id,
                         index_jobs_by_provider_slug, start_time):
    tbody_io = StringIO()
    for provider_number, project in enumerate(fetchers_projects, start=1):
        provider_slug = project.name[:-len("-fetcher")]
        pipeline_schedule = pipeline_schedule_by_fetcher_id.get(project.id)
        fetcher_jobs = jobs_by_fetcher_id[project.id]
        download_jobs = list(take(3, fetcher_jobs["download"]))
        convert_jobs = list(take(3, fetcher_jobs["convert"]))
        index_jobs = index_jobs_by_provider_slug.get(provider_slug)
        tbody_io.write(format_fetcher_tr(project, importer_project, provider_number, provider_slug, pipeline_schedule,
                                         download_jobs, convert_jobs, index_jobs))

    dashboard_template = Template((script_dir / "dashboard.template.html").read_text())  # pylint: disable=E1101
    tbody = tbody_io.getvalue()
    print(dashboard_template.substitute(
        generation_local_time_tag=local_time_tag(datetime.utcnow().isoformat() + 'Z'),
        generation_duration=humanfriendly.format_timespan(time.time() - start_time),
        tbody=tbody,
    ))


def format_job_link(project, job):
    job_url = "{}/{}/-/jobs/{}".format(args.gitlab_base_url, project.path_with_namespace, job.id)

    job_status = job.status
    if not job.started_at:
        job_status = "stuck"  # Introduce a new status for jobs that never started.

    title = "<br>".join([
        "status: {}".format(job_status),
        "duration: {}".format(humanfriendly.format_timespan(job.duration) if job.duration else "?"),
        "created: {}".format(local_time_tag(job.created_at) if job.created_at else "?"),
        "started: {}".format(local_time_tag(job.started_at) if job.started_at else "?"),
        "finished: {}".format(local_time_tag(job.finished_at) if job.finished_at else "?"),
    ])

    # Class names are from https://fontawesome.com/icons
    i_classes = "fa-check-circle text-success"
    if job_status == "running":
        i_classes = "fa-clock text-info"
    elif job_status == "failed":
        i_classes = "fa-exclamation-circle text-danger"
    elif job_status == "stuck":
        i_classes = "fa-exclamation-circle text-dark"
    elif job_status == "canceled":
        i_classes = "fa-minus-circle text-dark"

    return """<a href="{job_url}" class="mr-1" target="_blank" data-toggle="tooltip" data-html="true" data-placement="auto" title="{title}"><i class="fas {i_classes}"></i></a>""".format(
        job_url=job_url, i_classes=i_classes, title=title)


def format_pipeline_schedule_link(project, pipeline_schedule):
    if pipeline_schedule is None:
        pipeline_schedule_url = "{}/{}/pipeline_schedules".format(args.gitlab_base_url, project.path_with_namespace)
        pipeline_schedule_link = """<a href="{pipeline_schedule_url}" target="_blank" data-toggle="tooltip" data-placement="auto" title="Scheduler does not exist"><i class="fas fa-exclamation-triangle text-danger"></i></a>""".format(
            pipeline_schedule_url=pipeline_schedule_url)
    else:
        pipeline_schedule_url = "{}/{}/pipeline_schedules/{}/edit".format(
            args.gitlab_base_url, project.path_with_namespace, pipeline_schedule.id)
        scheduler_title = "<br>".join([
            "status: {}".format("active" if pipeline_schedule.active else "inactive"),
            "next run: {}".format(local_time_tag(pipeline_schedule.next_run_at)),
            "cron expression: {!r}".format(pipeline_schedule.cron),
        ])
        pipeline_schedule_link = """<a href="{pipeline_schedule_url}" target="_blank" data-toggle="tooltip" data-html="true" data-placement="auto" title="{scheduler_title}"><i class="fas {i_class}"></i></a>""".format(
            i_class="fa-check text-success" if pipeline_schedule.active else "fa-times text-warning",
            pipeline_schedule_url=pipeline_schedule_url,
            scheduler_title=scheduler_title,
        )
    return pipeline_schedule_link


def format_fetcher_tr(project, importer_project, provider_number, provider_slug, pipeline_schedule,
                      download_jobs, convert_jobs, index_jobs):
    pipeline_schedule_link = format_pipeline_schedule_link(project, pipeline_schedule)

    fetcher_jobs_url = "{}/{}/-/jobs".format(args.gitlab_base_url, project.path_with_namespace)

    if download_jobs:
        download_links = "".join(
            format_job_link(project, job)
            for job in download_jobs
        )
    else:
        title = "No download jobs found in the latest jobs of {}".format(project.path)
        download_links = """<a href="{fetcher_jobs_url}" target="_blank" data-toggle="tooltip" data-placement="auto" title="{title}"><i class="fas fa-question-circle text-warning"></i></a>""".format(
            fetcher_jobs_url=fetcher_jobs_url,
            title=title,
        )

    if convert_jobs:
        conversion_links = "".join(
            format_job_link(project, job)
            for job in convert_jobs
        )
    else:
        title = "No conversion jobs found in the latest jobs of {}".format(project.path)
        conversion_links = """<a href="{fetcher_jobs_url}" target="_blank" data-toggle="tooltip" data-placement="auto" title="{title}"><i class="fas fa-question-circle text-warning"></i></a>""".format(
            fetcher_jobs_url=fetcher_jobs_url,
            title=title,
        )

    if index_jobs:
        indexation_links = "".join(
            format_job_link(importer_project, job)
            for job in index_jobs
        )
    else:
        index_jobs_url = "{}/{}/-/jobs".format(args.gitlab_base_url, importer_project.path_with_namespace)
        title = "No indexation jobs found in the {} latest jobs of dbnomics-importer".format(dbnomics_importer_nb_jobs)
        indexation_links = """<a href="{index_jobs_url}" target="_blank" data-toggle="tooltip" data-placement="auto" title="{title}"><i class="fas fa-question-circle text-warning"></i></a>""".format(
            index_jobs_url=index_jobs_url,
            title=title,
        )

    if not args.disable_solr_info:
        solr = pysolr.Solr(args.solr_url)

        provider_solr_results = solr.search(Q(type='provider', slug=provider_slug))
        if not provider_solr_results:
            log.warning("Could not find provider from slug %r in Solr", provider_slug)
            provider_solr = None
        elif len(provider_solr_results) > 1:
            log.warning("Many providers were found from slug %r in Solr", provider_slug)
            provider_solr = None
        else:
            provider_solr = provider_solr_results.docs[0]

        nb_datasets = solr.search(Q(type='dataset', provider_code=provider_solr["code"])).hits \
            if provider_solr is not None \
            else None
        nb_series = solr.search(Q(type='series', provider_code=provider_solr["code"])).hits \
            if provider_solr is not None \
            else None
    else:
        provider_solr = nb_datasets = nb_series = None

    return """<tr id="{provider_slug}">
        <th scope="row">
            <span class="mr-2">{provider_number}</span>
            {star}
        </th>
        <th scope="row">
            {ui_link}
            <a href="{git_href}" class="ml-2 small" target="_blank">fetcher</a>
            <a href="{source_data_href}" class="ml-2 small" target="_blank">source</a>
            <a href="{converted_data_href}" class="ml-2 small" target="_blank">converted</a>
            <a href="{jobs_href}" class="ml-2 small" target="_blank">jobs</a>
        </th>
        <td>{pipeline_schedule_link}</td>
        <td>{download_links}</td>
        <td>{conversion_links}</td>
        <td>{indexation_links}</td>
        <td>{nb_datasets}</td>
        <td>{nb_series}</td>
    </tr>""".format(
        pipeline_schedule_link=pipeline_schedule_link,
        provider_number=provider_number,
        star=('<i class="fas fa-star"></i>'
              if provider_slug in star_providers_slugs
              else ""),
        provider_slug=provider_slug,
        ui_link=('<a href="{}/{}" target="_blank">{}</a>'.format(args.ui_base_url, provider_solr["code"], provider_slug)
                 if provider_solr is not None
                 else provider_slug),
        git_href="{}/{}".format(args.gitlab_base_url, project.path_with_namespace),
        source_data_href="{}/{}/{}-source-data".format(args.gitlab_base_url,
                                                       dbnomics_source_data_namespace, provider_slug),
        converted_data_href="{}/{}/{}-json-data".format(args.gitlab_base_url,
                                                        dbnomics_json_data_namespace, provider_slug),
        jobs_href="{}/{}/-/jobs".format(args.gitlab_base_url, project.path_with_namespace),
        download_links=download_links,
        conversion_links=conversion_links,
        indexation_links=indexation_links,
        nb_datasets=humanfriendly.format_number(nb_datasets) if nb_datasets is not None else "?",
        nb_series=humanfriendly.format_number(nb_series) if nb_series is not None else "?",
    )


def get_json_errors_artifact_dict(job):
    """Return errors artifact as dict, or None if no 'errors.json' present in job artifacts or job has no artifact.
    Raise a ValueError if json fails to load
    """
    if 'artifacts_file' in job.attributes:
        zf = zipfile.ZipFile(io.BytesIO(job.artifacts()), "r")
        if 'errors.json' in zf.namelist():
            with zf.open('errors.json') as _f:
                errors_dict = json.loads(_f.read())  # can raise a ValueError
                return errors_dict
    return None


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('--gitlab-base-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--ui-base-url', default='https://db.nomics.world', help='base URL of DBnomics UI')
    parser.add_argument('--solr-url', default='http://localhost:8983/solr/dbnomics', help='base URL of Solr core')
    parser.add_argument('--providers', help='generate dashboard for those providers only (comma-separated)')
    parser.add_argument('--all-branches', action="store_true",
                        help='consider all branches for source-data and json-data jobs (not only master)')
    parser.add_argument('--disable-solr-info', action="store_true", help='disable requesting Solr to get additional information')
    parser.add_argument('--log', default='WARNING', help='level of logging messages')
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(asctime)s:%(message)s",
        level=numeric_level,
        stream=sys.stderr,  # Script already outputs to stdout.
    )
    logging.getLogger("pysolr").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(args.log.upper())

    if not os.environ.get('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    if args.providers is not None:
        args.providers = [
            provider_code.lower()
            for provider_code in args.providers.strip().split(",")
        ]

    if args.gitlab_base_url.endswith('/'):
        args.gitlab_base_url = args.gitlab_base_url[:-1]

    start_time = time.time()

    gl = gitlab.Gitlab(args.gitlab_base_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    gl.auth()

    # Get dbnomics-fetchers projects.
    dbnomics_fetchers_group = gl.groups.get(dbnomics_fetchers_namespace)
    fetchers_projects = [
        gl.projects.get(group_project.id)
        for group_project in dbnomics_fetchers_group.projects.list(order_by="name", sort="asc", all=True)
        # Skip other projects like "documentation".
        if group_project.name.endswith("-fetcher") and not group_project.name.startswith("dummy") and
        (not args.providers or group_project.name[:-len("-fetcher")] in args.providers)
    ]

    # For each fetcher get its pipeline schedule.
    pipeline_schedule_by_fetcher_id = {
        fetcher_project.id: get_pipeline_schedule(fetcher_project)
        for fetcher_project in fetchers_projects
    }

    # For each fetcher get its latest jobs.
    def get_fetcher_jobs_by_type(project):
        log.debug("Fetching jobs for %r", project.name)
        fetcher_jobs_by_type = {"download": [], "convert": []}
        for job in project.jobs.list():
            if not args.all_branches and job.ref != "master":
                continue
            job_variables = get_fetcher_job_variables(job) or {}
            job_type = job_variables.get("JOB")
            if job_type is None:
                continue
            fetcher_jobs_by_type[job_type].append(job)
        return fetcher_jobs_by_type

    jobs_by_fetcher_id = {
        project.id: get_fetcher_jobs_by_type(project)
        for project in fetchers_projects
    }

    importer_project = gl.projects.get("{}/dbnomics-importer".format(dbnomics_namespace))
    importer_jobs_with_variables = [
        (job, get_importer_job_variables(job))
        for job in importer_project.jobs.list(per_page=dbnomics_importer_nb_jobs)
    ]

    index_jobs_by_provider_slug = {}
    for job, job_variables in importer_jobs_with_variables:
        provider_slug = job_variables.get("PROVIDER_SLUG")
        if provider_slug is not None:
            index_jobs_by_provider_slug.setdefault(provider_slug, []).append(job)

    # Render the dashboard.

    print_html_dashboard(fetchers_projects, importer_project, pipeline_schedule_by_fetcher_id, jobs_by_fetcher_id,
                         index_jobs_by_provider_slug, start_time)

    return 0


if __name__ == '__main__':
    sys.exit(main())
