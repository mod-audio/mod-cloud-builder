FROM debian:bookworm
LABEL maintainer="Filipe Coelho <falktx@mod.audio>"
ENV DEBIAN_FRONTEND noninteractive

# update and upgrade system
RUN apt-get update && apt-get upgrade -qqy && apt-get clean

# install required packages
RUN apt-get install -qqy git pylint python3-flask python3-flask-socketio python3-flask-sockets python3-websocket && \
    apt-get clean

# user configuration
ENV USER builder
ENV HOME /home/$USER

# create user
RUN useradd -d $HOME -m $USER

# switch user
USER $USER
WORKDIR $HOME

# setup for this instance
ENV MOD_UI_HTML_DIR $HOME/mod-ui/html
ENV PYTHONUNBUFFERED 1

# copy builder code
RUN mkdir $HOME/static $HOME/templates
RUN git clone --depth=1 https://github.com/moddevices/mod-ui.git
COPY server.py $HOME
COPY static/*.* $HOME/static/
COPY templates/*.html $HOME/templates/

# entry point
ENTRYPOINT $HOME/server.py
