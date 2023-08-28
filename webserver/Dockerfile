FROM debian:bookworm
LABEL maintainer="Filipe Coelho <falktx@mod.audio>"
ENV DEBIAN_FRONTEND noninteractive

# update and upgrade system
RUN apt-get update && apt-get upgrade -qqy && apt-get clean

# install required packages
RUN apt-get install -qqy pylint python3-flask python3-flask-socketio python3-flask-sockets && \
    apt-get clean

# user configuration
ENV USER builder
ENV HOME /home/$USER

# create user
RUN useradd -d $HOME -m $USER

# switch user
USER $USER
WORKDIR $HOME

# CMD
CMD ["bash"]
