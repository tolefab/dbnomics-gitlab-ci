FROM debian:latest

LABEL maintainer="contact+docker@nomics.world"

RUN apt --yes update
RUN apt --yes install git openssh-client python3 python3-pip unzip wget
# From https://github.com/docker-library/python/blob/master/Dockerfile-debian.template
ENV LANG C.UTF-8
