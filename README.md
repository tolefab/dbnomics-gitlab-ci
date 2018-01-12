# DB.nomics GitLab-CI

This repository contains scripts interacting with the GitLab Continuous Integration of DB.nomics.

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
PRIVATE_TOKEN=<hidden> ./trigger-download-job-for-provider.py <provider_slug>
```
