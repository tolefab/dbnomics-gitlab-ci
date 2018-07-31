#! /usr/bin/env python3


# dbnomics-gitlab-ci -- Scripts around DB.nomics GitLab-CI
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
"""

import argparse
import datetime
import logging
import os
import re
import sys
from io import StringIO
from pathlib import Path
from string import Template

import dateutil.parser
import gitlab
import humanfriendly
import requests
from toolz import take

dbnomics_namespace = "dbnomics"
dbnomics_fetchers_namespace = "dbnomics-fetchers"
dbnomics_importer_nb_jobs = 100
log = logging.getLogger(__name__)
script_dir = Path(__file__).parent


def format_datetime_str(s):
    dt = dateutil.parser.parse(s)
    return "{:%c}".format(dt)


def get_pipeline_schedule(project):
    """Return the only pipeline schedule of the project. Fetchers should not have more than one."""
    pipeline_schedules = project.pipelineschedules.list()
    assert len(pipeline_schedules) <= 1, pipeline_schedules
    return pipeline_schedules[0] if pipeline_schedules else None


def get_fetcher_job_variables(job):
    """Return job variables specific to dbnomics-importer: JOB.

    Getting job variables is not supported by GitLab API v4.
    """
    job_trace = job.trace().decode('utf-8')
    values = re.findall('Running job ([^$ ]+)', job_trace)
    assert len(values) <= 1, values
    return {"JOB": values[0] if values else None}


def get_importer_job_variables(job):
    """Return job variables specific to dbnomics-importer: PROVIDER_SLUG.

    Getting job variables is not supported by GitLab API v4.
    """
    job_trace = job.trace().decode('utf-8')
    values = re.findall('Importing provider ([^$. ]+)', job_trace)
    assert len(values) <= 1, values
    return {"PROVIDER_SLUG": values[0] if values else None}


def print_job(project, job):
    job_url = "{}/{}/-/jobs/{}".format(args.gitlab_base_url, project.path_with_namespace, job.id)
    print("  - {}".format(job.id))
    print("    - url: {}".format(job_url))
    print("    - status: {}".format(job.status))
    print("    - duration: {}".format(humanfriendly.format_timespan(job.duration)))
    print("    - created at: {}".format(format_datetime_str(job.created_at)))
    print("    - started at: {}".format(format_datetime_str(job.started_at)))
    print("    - finished at: {}".format(format_datetime_str(job.finished_at)))


def print_markdown_dashboard(fetchers_projects, importer_project, pipeline_schedule_by_fetcher_id, jobs_by_fetcher_id,
                             index_jobs_by_provider_slug):
    for project in fetchers_projects:
        provider_slug = project.name[:-len("-fetcher")]
        print("# {}".format(provider_slug))

        pipeline_schedule = pipeline_schedule_by_fetcher_id.get(project.id)
        print("- scheduler")
        if pipeline_schedule is None:
            print("  - status: undefined")
        else:
            pipeline_schedule_url = "{}/{}/pipeline_schedules/{}/edit".format(
                args.gitlab_base_url, project.path_with_namespace, pipeline_schedule.id)
            print("  - url: {}".format(pipeline_schedule_url))
            print("  - status: {}".format("active" if pipeline_schedule.active else "inactive"))
            print("  - next run at: {}".format(format_datetime_str(pipeline_schedule.next_run_at)))
            print("  - cron expression: {!r}".format(pipeline_schedule.cron))

        fetcher_jobs = jobs_by_fetcher_id[project.id]

        print("- downloads")
        for job in take(3, fetcher_jobs["download"]):
            print_job(project, job)

        print("- converts")
        for job in take(3, fetcher_jobs["convert"]):
            print_job(project, job)

        index_jobs = index_jobs_by_provider_slug.get(provider_slug)
        if index_jobs:
            print("- indexations")
            for index_job in take(3, index_jobs):
                print_job(importer_project, index_job)
        else:
            print("- no indexation jobs found in the {} latest jobs of dbnomics-importer".format(dbnomics_importer_nb_jobs))

        print("")


def print_html_dashboard(fetchers_projects, importer_project, pipeline_schedule_by_fetcher_id, jobs_by_fetcher_id,
                         index_jobs_by_provider_slug):
    tbody_io = StringIO()
    for project in fetchers_projects:
        provider_slug = project.name[:-len("-fetcher")]
        pipeline_schedule = pipeline_schedule_by_fetcher_id.get(project.id)
        fetcher_jobs = jobs_by_fetcher_id[project.id]
        download_jobs = list(take(3, fetcher_jobs["download"]))
        convert_jobs = list(take(3, fetcher_jobs["convert"]))
        index_jobs = index_jobs_by_provider_slug.get(provider_slug)
        tbody_io.write(format_fetcher_tr(project, importer_project, provider_slug, pipeline_schedule,
                                         download_jobs, convert_jobs, index_jobs))

    dashboard_template = Template((script_dir / "dashboard.template.html").read_text())  # pylint: disable=E1101
    tbody_io.seek(0)
    tbody = tbody_io.read()
    generation_date_str = "{:%c}".format(datetime.datetime.now())
    print(dashboard_template.substitute(
        generation_date_str=generation_date_str,
        tbody=tbody,
    ))


def format_job_link(project, job):
    job_url = "{}/{}/-/jobs/{}".format(args.gitlab_base_url, project.path_with_namespace, job.id)
    title = "<br>".join([
        "status: {}".format(job.status),
        "duration: {}".format(humanfriendly.format_timespan(job.duration)),
        "created at: {}".format(format_datetime_str(job.created_at)),
        "started at: {}".format(format_datetime_str(job.started_at)),
        "finished at: {}".format(format_datetime_str(job.finished_at)),
    ])
    assert job.status in {"success", "failed", "canceled"}, job.status
    i_classes = "fa-exclamation-circle text-danger" if job.status == "failed" else \
        "fa-minus-circle text-dark" if job.status == "cancelled" else \
        "fa-check-circle text-success"
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
            "next run at: {}".format(format_datetime_str(pipeline_schedule.next_run_at)),
            "cron expression: {!r}".format(pipeline_schedule.cron),
        ])
        pipeline_schedule_link = """<a href="{pipeline_schedule_url}" target="_blank" data-toggle="tooltip" data-html="true" data-placement="auto" title="{scheduler_title}"><i class="fas {i_class}"></i></a>""".format(
            i_class="fa-check text-success" if pipeline_schedule.active else "fa-times text-warning",
            pipeline_schedule_url=pipeline_schedule_url,
            scheduler_title=scheduler_title,
        )
    return pipeline_schedule_link


def format_fetcher_tr(project, importer_project, provider_slug, pipeline_schedule,
                      download_jobs, convert_jobs, index_jobs):
    pipeline_schedule_link = format_pipeline_schedule_link(project, pipeline_schedule)
    download_links = "".join(
        format_job_link(project, job)
        for job in download_jobs
    )
    conversion_links = "".join(
        format_job_link(project, job)
        for job in convert_jobs
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
    return """<tr>
        <th scope="row">{provider_slug}</th>
        <td>{pipeline_schedule_link}</td>
        <td>{download_links}</td>
        <td>{conversion_links}</td>
        <td>{indexation_links}</td>
    </tr>""".format(
        pipeline_schedule_link=pipeline_schedule_link,
        provider_slug=provider_slug,
        download_links=download_links,
        conversion_links=conversion_links,
        indexation_links=indexation_links,
    )


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('--gitlab-base-url', default='https://git.nomics.world', help='base URL of GitLab instance')
    parser.add_argument('--fetchers', nargs='+', metavar='PROVIDER_SLUG',
                        help='display dashboard for those fetchers only')
    parser.add_argument('--log', default='WARNING', help='level of logging messages')
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {}'.format(args.log))
    logging.basicConfig(level=numeric_level, stream=sys.stderr)
    logging.getLogger("urllib3").setLevel(args.log.upper())

    if not os.environ.get('PRIVATE_TOKEN'):
        log.error("Please set PRIVATE_TOKEN environment variable before using this tool! (see README.md)")
        return 1

    if args.gitlab_base_url.endswith('/'):
        args.gitlab_base_url = args.gitlab_base_url[:-1]

    gl = gitlab.Gitlab(args.gitlab_base_url, private_token=os.environ.get('PRIVATE_TOKEN'), api_version=4)
    gl.auth()

    # Get dbnomics-fetchers projects.
    dbnomics_fetchers_group = gl.groups.get(dbnomics_fetchers_namespace)
    fetchers_projects = [
        gl.projects.get(group_project.id)
        for group_project in dbnomics_fetchers_group.projects.list(order_by="name", sort="asc", all=True)
        # Skip other projects like "documentation".
        if group_project.name.endswith("-fetcher") and not group_project.name.startswith("dummy") and
        (not args.fetchers or group_project.name[:len("-fetcher")] in args.fetchers)
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
            job_variables = get_fetcher_job_variables(job)
            job_type = job_variables.get("JOB")
            if job_type is not None:
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
                         index_jobs_by_provider_slug)

    return 0


if __name__ == '__main__':
    sys.exit(main())
