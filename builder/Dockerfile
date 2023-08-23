ARG platform=moddwarf
FROM mpb-minimal-$platform-new
LABEL maintainer="Filipe Coelho <falktx@mod.audio>"
ENV DEBIAN_FRONTEND noninteractive
WORKDIR /root/mod-plugin-builder

# update and upgrade system
RUN apt-get update && apt-get upgrade -qqy && apt-get clean

# install packages for webserver
RUN apt-get install python3-tornado

# setup for this instance
ENV PYTHONUNBUFFERED 1

# copy builder code
COPY builder.py /root

# entry point
ENTRYPOINT /root/builder.py
