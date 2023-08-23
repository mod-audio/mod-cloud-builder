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
    async def procrun(self):
        self.proc = await create_subprocess_shell(f'./build moddwarf-new {self.projname}', stdout=PIPE, stderr=STDOUT)
        while self.proc is not None:
            stdout = await self.proc.stdout.readline()
            if stdout == b'':
                self.proc = None
                self.close()
                break
            self.write_message(stdout)

    def open(self):
        self.proc = self.projname = self.projdir = None

    def on_message(self, message):
        if self.proc is not None:
            self.write_message(u"Build already active, cannot trigger a 2nd one on the same socket")
            return

        message = message.strip()
        versionline = message.split('\n',1)[0].split('#',1)[0]
        versionpkg = versionline.split('_VERSION',1)[0]
        if not versionpkg or ' ' in versionpkg:
            self.write_message(u"Invalid package")
            return

        self.projdir = TemporaryDirectory(dir='./plugins/package')
        self.projname = os.path.basename(self.projdir.name)

        with open(os.path.join(self.projdir.name, self.projname + '.mk'), 'w') as fh:
            fh.write(message.replace(versionpkg+'_',self.projname.upper()+'_'))

        self.write_message(u"Starting build for "+versionpkg.lower()+'...' )
        IOLoop.instance().add_callback(self.procrun)

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
