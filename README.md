# DB.nomics GitLab-CI

This repository contains scripts interacting with the GitLab Continuous Integration of DB.nomics.

It also defines a `Dockerfile` allowing Docker Hub to build a container image for us.
Unfortunately, Docker Hub is only compatible with GitHub for now, and DB.nomics is hosted on its own [GitLab platform](https://git.nomics.world/). That's why we created a mirror of this project [on GitHub](https://github.com/dbnomics/dbnomics-gitlab-ci), but the real home is [on DB.nomics GitLab](https://git.nomics.world/dbnomics/dbnomics-gitlab-ci).

The Docker image is referenced in `gitlab-ci.template.yml` with the line `image: dbnomics/dbnomics-gitlab-ci:latest`.

## Obtain the private token

The private token is stored in a private Wiki page: https://git.nomics.world/cepremap-private/servers-and-services/blob/master/dbnomics-gitlab-private-tokens.md

## Configure CI for a provider

- copy `gitlab-ci.template.yml` from here to `.gitlab-ci.yml` in the fetcher directory
- set the PROVIDER_SLUG variable in the `variables` section of the YAML file
- [optional] if the fetcher scripts are designed to read/write Git objects (blobs and trees) instead of files, add the `--bare` option to `git clone` lines in the `job.script` section of the YAML file
- commit `.gitlab-ci.yml` and push
- run `configure-ci-for-provider.py` and follow instructions
    ```sh
    PRIVATE_TOKEN=<hidden> ./configure-ci-for-provider.py --purge -v <provider_slug>
    ```
- to test averything is okay, trigger a job using `trigger-job-for-provider.py` (see below)

## Trigger a job for a provider

```sh
PRIVATE_TOKEN=<hidden> ./trigger-job-for-provider.py <download|convert|index> <provider_slug>
```

## Other scripts

- `create-repositories-for-provider.py` creates the `{provider_slug}-source-data` and `{provider_slug}-json-data` repositories to gain time when creating a new fetcher
- `open-urls-for-provider.py` opens all URLs related to GitLab-CI management for a provider. It's a quick helper meant to help debugging the CI.
