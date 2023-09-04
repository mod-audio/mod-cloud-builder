# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

all: images

# TODO make images target use a single job
images: .stamp-modduo-builder .stamp-modduox-builder .stamp-moddwarf-builder .stamp-webserver-image
# modduo-image modduox-image moddwarf-image

# .PHONY: .stamp-modduo-builder .stamp-modduox-builder .stamp-moddwarf-builder

# %-builder: .stamp-%-builder
# 	@

# %-image: .stamp-%-image
# 	@

.stamp-mod%-image: mod-plugin-builder/docker/Dockerfile
	$(shell which docker) build mod-plugin-builder/docker --build-arg platform=mod$*-new --build-arg target=minimal --tag mpb-minimal-mod$*-new && touch $@

.stamp-%-builder: .stamp-%-image builder/Dockerfile builder/builder.py
	$(shell which docker) build builder --build-arg platform=$* --tag mcb-builder-$* && touch $@

.stamp-webserver-image: webserver/Dockerfile webserver/server.py webserver/templates/*.html
	$(shell which docker) build webserver --tag mcb-webserver && touch $@

run: images
	$(shell which docker-compose) down -t 1
	$(shell which docker-compose) up -d
	$(shell which docker) logs mod-cloud-builder_webserver_1 -t -f
