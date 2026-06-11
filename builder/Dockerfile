ARG platform=UNSET
FROM mpb-minimal-$platform
LABEL maintainer="Filipe Coelho <falktx@mod.audio>"
ENV DEBIAN_FRONTEND noninteractive
WORKDIR /root/mod-plugin-builder

# update and upgrade system
RUN apt-get update && apt-get upgrade -qqy && apt-get clean

# install packages for pip and tornado
# qemu-user-static is also installed as belt-and-suspenders for the binfmt
# registration the host must provide (see README "Host requirements"): if the
# host registers the handler with the F flag the container doesn't need its
# own qemu binary, but installing one here makes other registration modes
# work too.
RUN apt-get install -qqy python3-pip python3-tornado qemu-user-static && apt-get clean

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

# keep a known working version of heavylib around
RUN git clone https://github.com/Wasted-Audio/heavylib.git /root/heavylib
RUN git -C /root/heavylib checkout 6a73fb493a19da1152f42a2848835af62d8a08eb

# copy builder code
COPY builder.py /root

# entry point
ENTRYPOINT /root/builder.py
