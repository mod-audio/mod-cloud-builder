ARG platform=moddwarf
FROM mpb-minimal-$platform-new
LABEL maintainer="Filipe Coelho <falktx@mod.audio>"
ENV DEBIAN_FRONTEND noninteractive
WORKDIR /root/mod-plugin-builder

# update and upgrade system
RUN apt-get update && apt-get upgrade -qqy && apt-get clean

# install packages for pip and tornado
RUN apt-get install -qqy python3-pip python3-tornado && apt-get clean

# install faustpp
RUN echo "deb https://ppa.launchpadcontent.net/kxstudio-debian/toolchain/ubuntu focal main" | tee /etc/apt/sources.list.d/kxstudio.list
RUN echo "deb https://ppa.launchpadcontent.net/kxstudio-debian/libs/ubuntu focal main" | tee -a /etc/apt/sources.list.d/kxstudio.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys DF1BC724E4ED8A947FF0B0A1F8599E482BD84BD9
RUN apt-get update && apt-get upgrade -qqy && apt-get install -qqy faustpp && apt-get clean

# setup for this instance
ENV PYTHONUNBUFFERED 1

# keep a known working version of dpf around, for faster builds
RUN git clone https://github.com/DISTRHO/DPF.git /root/dpf
RUN git -C /root/dpf checkout 61d38eb638449647fb8395a35c5b8dab7e981ba7

# copy builder code
COPY builder.py /root

# entry point
ENTRYPOINT /root/builder.py
