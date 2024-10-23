FROM ubuntu:latest
LABEL authors="calm"

ENTRYPOINT ["top", "-b"]
