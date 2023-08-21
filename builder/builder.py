#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

from asyncio.subprocess import create_subprocess_shell, PIPE, STDOUT
from asyncio import run
from tempfile import TemporaryDirectory
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.websocket import WebSocketHandler

class EchoWebSocket(WebSocketHandler):
    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        print(message)
        self.write_message(u"You said: " + message)

    def on_close(self):
        print("WebSocket closed")

    def check_origin(self, origin):
        return True

if __name__ == "__main__":
    print ("Starting...")
    app = Application([
        (r'/ww', EchoWebSocket)
    ])
    app.listen(8000)
    IOLoop.instance().start()

#projdir = TemporaryDirectory()

#with open(projdir, "aether.mk", "w") as fh:
    #fh.write("""
#AETHER_VERSION = 2ccae056a612d2075650f2913a93cc4aa0df95ad
#AETHER_SITE = https://github.com/Dougal-s/Aether.git
#AETHER_SITE_METHOD = git
#AETHER_CONF_OPTS = -DBUILD_GUI="Off" -DFORCE_DISABLE_DENORMALS="Off"
#AETHER_BUNDLES = aether.lv2

## needed for submodules support
#AETHER_PRE_DOWNLOAD_HOOKS += MOD_PLUGIN_BUILDER_DOWNLOAD_WITH_SUBMODULES

#define AETHER_INSTALL_TARGET_CMDS
	#cp -rL $(@D)/aether.lv2 $(TARGET_DIR)/usr/lib/lv2/
#endef

#$(eval $(cmake-package))
#""")

#async def main():
    #c = f'docker run -v {projdir}:/opt/mount  --rm mpb-minimal-modduo-new:latest /root/build-and-copy-bundles.sh'
    #p = await create_subprocess_shell(c, stdout=PIPE, stderr=STDOUT)
    #while True:
        #stdout = await p.stdout.readline()
        #if stdout == b'':
            #break
        #print('----------------------', stdout.decode('utf-8'), end='')

#run(main())
