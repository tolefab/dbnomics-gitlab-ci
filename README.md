# DBnomics GitLab-CI

This repository contains scripts interacting with the GitLab Continuous Integration of DBnomics.

It also defines a `Dockerfile` allowing Docker Hub to build a container image for us.
Unfortunately, Docker Hub is only compatible with GitHub for now, and DBnomics is hosted on its own [GitLab platform](https://git.nomics.world/). That's why we created a mirror of this project [on GitHub](https://github.com/dbnomics/dbnomics-gitlab-ci), but the real home is [on DBnomics GitLab](https://git.nomics.world/dbnomics/dbnomics-gitlab-ci).

The Docker image is referenced in `.gitlab-ci.yml` files of each fetcher, with the line `image: dbnomics/dbnomics-gitlab-ci:latest`.

## Configuration

### Requirements

Install the Python requirements.

```sh
pip install -r requirements.txt
```

### Private token

The scripts of this repository use GitLab API in a way that requires authentication.
They read a "private token" from an environment variable which can be also configured via a `.env` file.

First, copy the private token from this private file: https://git.nomics.world/cepremap-private/servers-and-services/blob/master/dbnomics-gitlab-private-tokens.md

If you don't have access, ask DBnomics team.

Copy the `.env.example` file to `.env` and replace the value of `PRIVATE_TOKEN`.

Now you can use the scripts of this repository.

## Configure CI for a provider

- Use [dbnomics-fetcher-cookiecutter](https://git.nomics.world/dbnomics/dbnomics-fetcher-cookiecutter), or copy its `.gitlab-ci.yml` to the fetcher directory, and subtitute `{{ }}` placeholders by real values.
- Set the PROVIDER_SLUG variable in the `variables` section of the YAML file.
- [optional] If the fetcher scripts are designed to read/write Git objects (blobs and trees) instead of files and create the commit, for example because they implement incremental mode, adapt the CI in consequence. Look at [IMF CI config file](https://git.nomics.world/dbnomics-fetchers/imf-fetcher/blob/master/.gitlab-ci.yml) for an example.
- Check that you keep lines of `.gitlab-ci.yml` specific to this fetcher (for example `apt install wget`).
- Commit `.gitlab-ci.yml` and push.
- Run `configure-ci-for-provider.py` and follow the instructions.
    ```sh
    ./configure-ci-for-provider.py --purge -v <provider_slug>
    ```
- To test averything is okay, trigger a job using `trigger-job-for-provider.py` (see below).

## Trigger a job for a provider

This script runs a job in GitLab-CI using the configured webhooks. The triggered job can be followed by clicking on the link printed by the script.

```sh
./trigger-job-for-provider.py <download|convert|index> <provider_slug>
```

## Other scripts

- `create-repositories-for-provider.py` creates the `{provider_slug}-source-data` and `{provider_slug}-json-data` repositories to gain time when creating a new fetcher
- `open-urls-for-provider.py` opens all URLs related to GitLab-CI management for a provider. It's a quick helper meant to help debugging the CI.

## What to do after changing a provider code

Example: rename `bank-of-england` to `BOE`.

- Rename the fetcher, source data and JSON data repositories in advanced settings
- Rename your local directories and update Git remote URLs with:
  ```
  git remote set-url origin git@git.nomics.world:dbnomics-fetchers/boe-fetcher.git
  ```
  (this time by ssh)
- Remove all documents from Solr index with `./delete_provider.sh bank-of-england`
- In the fetcher repo:
  - change the code in `convert.py` in `PROVIDER_JSON` constant (use `BOE`)
  - change the `PROVIDER_SLUG` variable in `.gitlab-ci.yml` (use `boe`)
- On the server `dolos`, rename the JSON data directory under `/home/gitlab-runner/json-data` and update thew Git remote URL:
  ```
  git remote set-url origin https://git.nomics.world/dbnomics-json-data/boe-json-data.git
  ```
  (this time by `https`)
- Update the `PROVIDER_SLUG` job variable in the [webhook](https://git.nomics.world/dbnomics-json-data/boe-json-data/settings/integrations)
- Trigger a convert job: `./trigger-job-for-provider.py convert boe`