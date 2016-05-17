FROM python:2.7
MAINTAINER Clément Grimal <cgrimal@devatics.com>

RUN pip install pip --upgrade
RUN pip install --upgrade \
    pyquery

ENV PYTHONPATH=/usr/lib/python2.7/dist-packages

ADD . .

ENTRYPOINT ["python", "lbc_alertes.py"]