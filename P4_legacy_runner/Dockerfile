ARG BASE_IMAGE=s.egorkin/heinz_p4:latest
FROM ${BASE_IMAGE}

ENV P4_LEGACY_APP_PATH=/opt/P4_app
ENV P4_LEGACY_PYTHON=python2.7

WORKDIR /opt/P4_legacy_runner

COPY . /opt/P4_legacy_runner

RUN chmod +x \
    /opt/P4_legacy_runner/bin/p4-legacy-runner \
    /opt/P4_legacy_runner/scripts/run-generate-pdf.sh

ENTRYPOINT ["/opt/P4_legacy_runner/bin/p4-legacy-runner"]
CMD ["--help"]
