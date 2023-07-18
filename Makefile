# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

all: images

# TODO make images target use a single job
images: modduo-image modduox-image moddwarf-image webserver-image

%-image: .stamp-%

.stamp-mod%:
	docker build mod-plugin-builder/docker --build-arg platform=mod$*-new --build-arg target=minimal --tag mpb-minimal-mod$*-new && touch $@

.stamp-webserver:
	docker build webserver --tag mod-cloud-builder && touch $@
