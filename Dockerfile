FROM debian:buster

LABEL maintainer="contact+docker@nomics.world"

RUN apt update && apt --yes install git openssh-client python3 python3-pip unzip wget

# From https://github.com/docker-library/python/blob/master/Dockerfile-debian.template
ENV LANG C.UTF-8
