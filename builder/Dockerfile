ARG platform=UNSET
FROM mpb-minimal-$platform
LABEL maintainer="MOD Audio <https://mod.audio>"
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

# install faust + faustpp from the MOD mirror: the exact same packages the
# KXStudio PPAs used to provide (faust 2.85.5, faustpp git20220912), now
# pinned and verified instead of floating with a third-party archive
ENV FAUST_VERSION=2.85.5+ds0-1
ENV FAUSTPP_VERSION=0.0.0~git20220912
RUN arch=$(dpkg --print-architecture) && mkdir /tmp/deb && cd /tmp/deb && \
    for f in faust-common_${FAUST_VERSION}_all.deb libfaust2t64_${FAUST_VERSION}_${arch}.deb \
             faust_${FAUST_VERSION}_${arch}.deb faustpp_${FAUSTPP_VERSION}_${arch}.deb; do \
        wget -q https://download.mod.audio/mirror/deb/$f; done && \
    printf '%s\n' \
        '9a24f96fdd112dfcc856bd4b6125eb901685178cf9a80f466d5dae003c29ec4a  faust-common_2.85.5+ds0-1_all.deb' \
        '621d7e086c7ab58f05c48ddbf121a227a85451be03a26a8573a8061b9ee63a8d  faust_2.85.5+ds0-1_amd64.deb' \
        '13749d06fa5e4510a47aaa3f114b3d05a0639550f56a52eb9ed1d616f390c10b  faust_2.85.5+ds0-1_arm64.deb' \
        'a612885478ba2a108c6f83fb5c1e1df898c1334d78b707f339d6ec8af5f5f4e3  faustpp_0.0.0~git20220912_amd64.deb' \
        '600d1f19c867c5d99cfa66a7080a0540665431fb9353acabdc9523a18bf2d12a  faustpp_0.0.0~git20220912_arm64.deb' \
        'f5302a768331bb7eaa8a91ce12439c25fb89b7d613e021e7be60535b34bf78c0  libfaust2t64_2.85.5+ds0-1_amd64.deb' \
        'bd17dc3af7a4477303d6b565430144cc73223c6791a8dc40f9bbf25367c5e402  libfaust2t64_2.85.5+ds0-1_arm64.deb' \
        > SHA256SUMS && sha256sum -c --ignore-missing SHA256SUMS && \
    apt-get update && apt-get install -qqy ./*.deb && apt-get clean && cd / && rm -rf /tmp/deb

# setup for this instance
ENV PYTHONUNBUFFERED 1

# keep a known working version of dpf around, for faster builds
# (MOD fork of DISTRHO/DPF, the pin is kept on branch mod/pin-61d38eb6)
RUN git clone --branch mod/pin-61d38eb6 https://github.com/mod-audio/DPF.git /root/dpf
RUN git -C /root/dpf checkout 61d38eb638449647fb8395a35c5b8dab7e981ba7

# keep a known working version of heavylib around
# (MOD fork of Wasted-Audio/heavylib, the pin is kept on branch mod/pin-6a73fb49)
RUN git clone --branch mod/pin-6a73fb49 https://github.com/mod-audio/heavylib.git /root/heavylib
RUN git -C /root/heavylib checkout 6a73fb493a19da1152f42a2848835af62d8a08eb

# copy builder code
COPY builder.py /root

# entry point
ENTRYPOINT /root/builder.py
