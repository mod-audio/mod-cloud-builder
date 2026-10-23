#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023-2024 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import json
import shlex
import tarfile

from asyncio.subprocess import create_subprocess_shell, PIPE, DEVNULL, STDOUT
from io import BytesIO
from tempfile import TemporaryDirectory, TemporaryFile
from tornado.ioloop import IOLoop
from tornado.web import Application, HTTPError, RequestHandler
from tornado.websocket import WebSocketHandler

BUILDER_PACKAGE_DIR = './plugins/package'
TARGET_PLATFORM = os.getenv('MCB_BUILDER_TARGET', 'moddwarf-new')
WORKDIR = os.getenv('WORKDIR', os.path.expanduser('~/mod-workdir'))

os.environ['MPB_SKIP_PLUGIN_COPY'] = '1'

# the downloads of a build that we hand back for the archive of a shared build
MAX_SOURCES_SIZE = 256 * 1024 * 1024

# buildroot variables of a package that say where its sources come from
SOURCE_VARS = ('SITE', 'SITE_METHOD', 'VERSION', 'SOURCE', 'PATCH', 'EXTRA_DOWNLOADS', 'DL_DIR')

async def read_package_vars(projname):
    # ask buildroot itself, so variables built from other variables come out expanded
    # (not with "make printvars", which crashes GNU make 4.3 on buildroot 2016.02)
    pkg = projname.upper().replace('-', '_')
    names = ' '.join([f'{pkg}_{v}' for v in SOURCE_VARS] + ['DL_DIR'])
    rule = 'mcb-vars: ; @:$(foreach v,$(MCB_VARS),$(info $(v)=$($(v))))'
    # same environment as the build script sets up
    script = (f'umask 0022; PLATFORM={shlex.quote(TARGET_PLATFORM)}; source .common >/dev/null; '
              f'export DOWNLOAD_PATH="$DOWNLOAD_DIR" TOOLCHAIN_PATH="$TOOLCHAIN_DIR"; '
              f'cd "$BUILD_DIR/$BUILDROOT_VERSION" && '
              f'$BR2_MAKE -s --no-print-directory --eval={shlex.quote(rule)} '
              f'MCB_VARS={shlex.quote(names)} mcb-vars')
    proc = await create_subprocess_shell(f'bash -c {shlex.quote(script)}', stdout=PIPE, stderr=DEVNULL)
    stdout, _ = await proc.communicate()

    values = {}
    for line in stdout.decode('utf-8', 'replace').splitlines():
        name, sep, value = line.partition('=')
        if not sep:
            continue
        if name == 'DL_DIR':
            values['BR2_DL_DIR'] = value.strip()
        elif name.startswith(pkg + '_'):
            values[name[len(pkg)+1:]] = value.strip()
    return values

def pack_sources(values, fh):
    dldir = os.path.realpath(values.get('BR2_DL_DIR', '') or os.path.join(WORKDIR, 'download'))
    candidates = []
    for word in ' '.join(values.get(v, '') for v in ('SOURCE', 'PATCH', 'EXTRA_DOWNLOADS')).split():
        name = os.path.basename(word.rstrip('/'))
        if name and name not in ('.', '..') and name not in candidates:
            candidates.append(name)

    found = {}
    missing = []
    total = 0
    for name in candidates:
        # buildroot 2016.02 keeps downloads flat in DL_DIR, newer versions in DL_DIR/<package>
        for folder in (values.get('DL_DIR', ''), dldir):
            if not folder:
                continue
            path = os.path.realpath(os.path.join(folder, name))
            if not path.startswith(dldir + os.sep) or not os.path.isfile(path):
                continue
            total += os.path.getsize(path)
            found[name] = path
            break
        else:
            missing.append(name)

    info = {
        'platform': TARGET_PLATFORM,
        'vars': values,
        'files': sorted(found),
        'missing': missing,
        'skipped_too_large': total > MAX_SOURCES_SIZE,
    }

    with tarfile.open(fileobj=fh, mode='w:gz') as tar:
        data = json.dumps(info, indent=2).encode('utf-8')
        member = tarfile.TarInfo('buildroot.json')
        member.size = len(data)
        tar.addfile(member, BytesIO(data))
        if total <= MAX_SOURCES_SIZE:
            for name, path in sorted(found.items()):
                tar.add(path, arcname=f'downloads/{name}', recursive=False)

class Builder(object):
    active = {}

    def __init__(self, pkgbundle):
        self.proc = None
        self.projdir = TemporaryDirectory(dir=BUILDER_PACKAGE_DIR)
        self.projname = os.path.basename(self.projdir.name)
        self.pkgbundle = pkgbundle

    async def build(self, write_message_callback):
        print("Builder.build", write_message_callback)
        self.proc = await create_subprocess_shell(f'./build {TARGET_PLATFORM} {self.projname}',
                                                  stdout=PIPE,
                                                  stderr=STDOUT)
        while self.proc is not None:
            stdout = await self.proc.stdout.readline()
            if self.proc is None:
                break
            if stdout == b'':
                # subprocess closed stdout; wait for it to actually exit so
                # we can report success or failure based on the return code,
                # rather than unconditionally claiming success
                proc = self.proc
                self.proc = None
                returncode = await proc.wait()
                if returncode == 0:
                    write_message_callback(u"Build completed successfully.")
                else:
                    write_message_callback(
                        u"Build failed with exit code %d." % returncode)
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

    def post(self):
        # validate package contents
        package = self.jsonrequest.get('package', None)
        if package is None:
            self.postdone({ 'ok': False, 'error': "Missing package" })
            return

        files = self.jsonrequest.get('files', None)
        if not files:
            self.postdone({ 'ok': False, 'error': "Missing files" })
            return

        # get package name
        pkgname = package.split('_VERSION = ',1)[0].split('\n',1)[-1].rsplit('\n')[-1].split('#',1)[0].strip()
        if not pkgname or not pkgname.replace('_','').isalnum() or pkgname[0].isdigit():
            self.postdone({ 'ok': False, 'error': f"Invalid package version" })
            return

        # get package bundle
        pkgbundle = package.split('_BUNDLES = ',1)[1].split('\n',1)[0].rsplit('\n')[-1].split('#',1)[0].strip()
        if not pkgbundle:
            self.postdone({ 'ok': False, 'error': "Invalid package bundle name" })
            return
        if ' ' in pkgbundle:
            self.postdone({ 'ok': False, 'error': "Multiple bundles per package is not supported" })
            return

        # prepare for build
        builder = Builder.create(pkgbundle)

        # create plugin files
        with open(os.path.join(BUILDER_PACKAGE_DIR, builder.projname, f'{builder.projname}.mk'), 'w') as fh:
            fh.write(package.replace(f'{pkgname}_', f'{builder.projname.upper()}_'))

        for filename, content in files.items():
            if filename.endswith('.mk'):
                continue
            with open(os.path.join(BUILDER_PACKAGE_DIR, builder.projname, filename), 'w') as fh:
                fh.write(content)

        self.postdone({ 'ok': True, 'id': builder.projname })

    def postdone(self, data):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write(json.dumps(data))
        self.finish()

    async def get(self):
        builder = Builder.get(self.jsonrequest['id'])

        if self.jsonrequest.get('what') == 'sources':
            await self.get_sources(builder)
            return

        folders = (
            os.path.join(BUILDER_PACKAGE_DIR, builder.projname),
            f"{WORKDIR}/{TARGET_PLATFORM}/target/usr/lib/lv2",
        )

        for folder in folders:
            if os.path.exists(os.path.join(folder, builder.pkgbundle)):
                break
        else:
            # No bundle found post-build
            self.write('')
            self.finish()
            return

        proc = await create_subprocess_shell(f'tar -C {folder} -chz {builder.pkgbundle} -O', stdout=PIPE)

        while proc is not None:
            stdout = await proc.stdout.read(8192)
            if stdout == b'':
                break
            self.write(stdout)

        self.finish()

    async def get_sources(self, builder):
        # what the build downloaded (tarballs, patches), plus the variables that say where
        # it came from; must be asked for before the build websocket is closed
        values = await read_package_vars(builder.projname)

        with TemporaryFile() as fh:
            await IOLoop.current().run_in_executor(None, pack_sources, values, fh)
            fh.seek(0)
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                self.write(chunk)
                await self.flush()

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
