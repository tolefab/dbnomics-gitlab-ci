# DB.nomics GitLab-CI

This repository contains scripts interacting with the GitLab Continuous Integration of DB.nomics.

It also defines a `Dockerfile` allowing Docker Hub to build a container image for us.
Unfortunately, Docker Hub is only compatible with GitHub for now, and DB.nomics is hosted on its own [GitLab platform](https://git.nomics.world/). That's why we created a mirror of this project [on GitHub](https://github.com/cbenz/dbnomics-gitlab-ci), but the real home is [on DB.nomics GitLab](https://git.nomics.world/dbnomics/dbnomics-gitlab-ci).

The Docker image is referenced in `gitlab-ci.template.yml` with the line `image: cbenz/dbnomics-gitlab-ci:latest`.

## Obtain the private token

The private token is stored in a private Wiki page: https://git.nomics.world/cepremap-private/servers-and-services/blob/master/dbnomics-gitlab-private-tokens.md

## Configure CI for a provider

```sh
PRIVATE_TOKEN=<hidden> ./configure-ci-for-provider.py -v <provider_slug>
```

## Open URLs for provider

```sh
./open-urls-for-provider.py <provider_slug>
```

## Trigger download for a provider

```sh
PRIVATE_TOKEN=<hidden> ./trigger-job-for-provider.py <download or convert> <provider_slug>
```
