# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

all: images

# TODO make images target use a single job
images: modduo-image modduox-image moddwarf-image

modduo-image: .stamp-modduo

modduox-image: .stamp-modduox

moddwarf-image: .stamp-moddwarf

.stamp-%:
	docker build mod-plugin-builder/docker --build-arg platform=$*-new --build-arg target=minimal --tag mpb-minimal-$*-new && touch $@
