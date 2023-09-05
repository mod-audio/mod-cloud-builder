#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import json

from asyncio.subprocess import create_subprocess_shell, PIPE, STDOUT
from tempfile import TemporaryDirectory
from tornado.ioloop import IOLoop
from tornado.web import Application, HTTPError, RequestHandler
from tornado.websocket import WebSocketHandler

BUILDER_PACKAGE_DIR = './plugins/package'
TARGET_PLATFORM = os.getenv('MCB_BUILDER_TARGET', 'moddwarf-new')

os.environ['MPB_SKIP_PLUGIN_COPY'] = '1'

class Builder(object):
    active = {}

    def __init__(self, pkgbundle):
        self.proc = None
        self.projdir = TemporaryDirectory(dir=BUILDER_PACKAGE_DIR)
        self.projname = os.path.basename(self.projdir.name)
        self.pkgbundle = pkgbundle

    async def build(self, write_message_callback):
        print("Builder.build", write_message_callback)
        self.proc = await create_subprocess_shell(f'./build {TARGET_PLATFORM} {self.projname}', stdout=PIPE, stderr=STDOUT)
        while self.proc is not None:
            stdout = await self.proc.stdout.readline()
            if self.proc is None:
                break
            if stdout == b'':
                self.proc = None
                write_message_callback(u"Build completed successfully.")
                write_message_callback(u'--- END ---')
                break
            write_message_callback(stdout)

    def destroy(self):
        print("Builder.destroy")
        Builder.active.pop(self.projname)

        if self.proc is not None:
            proc = self.proc
            self.proc = None
            proc.kill()

        self.projdir.cleanup()

    @classmethod
    def create(kls, pkgbundle):
        builder = Builder(pkgbundle)
        kls.active[builder.projname] = builder
        return builder

    @classmethod
    def get(kls, projname):
        return kls.active[projname]

class BuilderRequest(RequestHandler):
    def prepare(self):
        if 'application/json' in self.request.headers.get('Content-Type'):
            self.jsonrequest = json.loads(self.request.body.decode('utf-8'))
        else:
            raise HTTPError(501, 'Content-Type != "application/json"')

    def done(self, data):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(data))
        self.finish()

    def post(self):
        # validate package contents
        package = self.jsonrequest.get('package', None)
        if package is None:
            self.done({ 'ok': False, 'error': "Missing package" })
            return

        files = self.jsonrequest.get('files', None)
        if not files:
            self.done({ 'ok': False, 'error': "Missing files" })
            return

        # get package name
        pkgname = package.split('_VERSION = ',1)[0].split('\n',1)[-1].split('#',1)[0]
        if not pkgname or not pkgname.replace('_','').isalnum() or pkgname[0].isdigit():
            self.done({ 'ok': False, 'error': "Invalid package version" })
            return

        # get package bundle
        pkgbundle = package.split('_BUNDLES = ',1)[1].split('\n',1)[0].split('#',1)[0].strip()
        if not pkgbundle:
            self.done({ 'ok': False, 'error': "Invalid package bundle name" })
            return
        if ' ' in pkgbundle:
            self.done({ 'ok': False, 'error': "Multiple bundles per package is not supported" })
            return

        # prepare for build
        builder = Builder.create(pkgbundle)

        # create plugin files
        with open(os.path.join(BUILDER_PACKAGE_DIR, builder.projname, f'{builder.projname}.mk'), 'w') as fh:
            fh.write(package.replace(f'{pkgname}_', f'{builder.projname.upper()}_'))

        for filename, content in files.items():
            with open(os.path.join(BUILDER_PACKAGE_DIR, builder.projname, filename), 'w') as fh:
                fh.write(content)

        self.done({ 'ok': True, 'id': builder.projname })

    async def get(self):
        builder = Builder.get(self.jsonrequest['id'])
        folder = os.path.join(BUILDER_PACKAGE_DIR, builder.projname)
        proc = await create_subprocess_shell(f'tar -C {folder} -chz {builder.pkgbundle} -O', stdout=PIPE)

        while proc is not None:
            stdout = await proc.stdout.read(8192)
            if stdout == b'':
                break
            self.write(stdout)

        self.finish()

class BuilderWebSocket(WebSocketHandler):
    async def build(self):
        print("BuilderWebSocket.build")
        await self.builder.build(self.write_message)

    def open(self):
        print("BuilderWebSocket.open")
        self.builder = None

    def on_message(self, message):
        print("BuilderWebSocket.on_message", message)
        if not message.replace('_','').isalnum():
            self.close()
            return

        self.builder = Builder.get(message)
        IOLoop.instance().add_callback(self.build)

    def on_close(self):
        print("BuilderWebSocket.on_close")
        if self.builder is None:
            return
        self.builder.destroy()

    def check_origin(self, origin):
        return True

if __name__ == "__main__":
    port = int(os.getenv('MCB_BUILDER_PORT', 8000))
    print (f'Starting using port {port}...')
    app = Application([
        (r'/', BuilderRequest),
        (r'/build', BuilderWebSocket)
    ])
    app.listen(port)
    IOLoop.instance().start()
