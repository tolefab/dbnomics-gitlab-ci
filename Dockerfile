FROM debian:latest

MAINTAINER DBnomics Project

RUN apt --yes update
RUN apt --yes install git openssh-client python3 python3-pip unzip wget
# From https://github.com/docker-library/python/blob/master/Dockerfile-debian.template
ENV LANG C.UTF-8
