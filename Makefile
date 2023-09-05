# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

all: webserver

# TODO make images target use a single job

modduo: .stamp-modduo-builder

modduox: .stamp-modduox-builder

modduox: .stamp-moddwarf-builder

webserver: .stamp-webserver .stamp-modduo-builder .stamp-modduox-builder .stamp-moddwarf-builder

mod%-image: mod-plugin-builder/docker/Dockerfile
	$(shell which docker) build mod-plugin-builder/docker --build-arg platform=mod$*-new --build-arg target=minimal --tag mpb-minimal-mod$*-new

.stamp-%-builder: %-image builder/Dockerfile builder/builder.py
	$(shell which docker) build builder --build-arg platform=$* --tag mcb-builder-$* && touch $@

.stamp-webserver: webserver/Dockerfile webserver/server.py webserver/templates/*.html
	$(shell which docker) build webserver --tag mcb-webserver && touch $@

run: webserver
	$(shell which docker-compose) down -t 1
	$(shell which docker-compose) up -d
	$(shell which docker) logs mod-cloud-builder_webserver_1 -t -f
