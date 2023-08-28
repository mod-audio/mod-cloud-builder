#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os

from asyncio.subprocess import create_subprocess_shell, PIPE, STDOUT
from tempfile import TemporaryDirectory
from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.websocket import WebSocketHandler

class EchoWebSocket(WebSocketHandler):
    async def plugin_package(self):
        # FIXME randomize bundle name?
        self.proc = await create_subprocess_shell(f'tar -C ~/mod-workdir/moddwarf-new/plugins -chz midi-display.lv2 -O', stdout=PIPE)
        while self.proc is not None:
            stdout = await self.proc.stdout.read(8192)
            if self.proc is None:
                break
            if stdout == b'':
                self.proc = None
                self.close()
                break
            self.write_message(stdout, True)

    async def plugin_build(self):
        self.proc = await create_subprocess_shell(f'./build moddwarf-new {self.projname}', stdout=PIPE, stderr=STDOUT)
        while self.proc is not None:
            stdout = await self.proc.stdout.readline()
            if self.proc is None:
                break
            if stdout == b'':
                self.proc = None
                self.write_message(u"Build completed successfully, fetching plugin binaries...")
                self.write_message(u'--- BINARY ---')
                IOLoop.instance().add_callback(self.plugin_package)
                break
            self.write_message(stdout)

    def open(self):
        self.proc = self.projname = self.projdir = None

    def on_message(self, message):
        if self.proc is not None:
            self.write_message(u"Build already active, cannot trigger a 2nd one on the same socket")
            self.close()
            return

        message = message.strip()
        versionline = message.split('\n',1)[0].split('#',1)[0]
        versionpkg = versionline.split('_VERSION',1)[0]
        if not versionpkg or ' ' in versionpkg:
            self.write_message(u"Invalid package")
            self.close()
            return

        self.projdir = TemporaryDirectory(dir='./plugins/package')
        self.projname = os.path.basename(self.projdir.name)

        with open(os.path.join(self.projdir.name, self.projname + '.mk'), 'w') as fh:
            fh.write(message.replace(versionpkg+'_',self.projname.upper()+'_'))

        self.write_message(u"Starting build for "+versionpkg.lower()+'...')
        IOLoop.instance().add_callback(self.plugin_build)

    def on_close(self):
        if self.proc is None:
            return
        proc = self.proc
        projdir = self.projdir
        self.proc = self.projname = self.projdir = None
        proc.kill()
        projdir.cleanup()

    def check_origin(self, origin):
        return True

if __name__ == "__main__":
    print ("Starting using port 8000...")
    app = Application([
        (r'/ww', EchoWebSocket)
    ])
    app.listen(8000)
    IOLoop.instance().start()
