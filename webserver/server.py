#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# imports
import os
import sys
import json

from base64 import encodebytes
from flask import Flask, Response, copy_current_request_context, redirect, request, render_template, send_from_directory
from flask_socketio import SocketIO, emit, send
from gevent import spawn
from re import sub as re_sub
from unicodedata import normalize
from urllib.request import Request, urlopen
from websocket import create_connection

# configuration
MOD_UI_HTML_DIR = os.getenv('MOD_UI_HTML_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mod-ui', 'html')))

print(MOD_UI_HTML_DIR)
if not os.path.exists(MOD_UI_HTML_DIR):
    print('mod-ui html dir is not accessible, cannot continue!')
    sys.exit(2)

builders = [
    {
        'name': 'FAUST',
        'href': '/faust',
        'image_url': '/static/faust-text.svg'
    },
    { 
        'name': 'MAX gen~',
        'href': '/maxgen',
        'image_url': '/static/max-8-logo.png'
    },
    {
        'name': 'Pure Data (hvcc)',
        'href': '/hvcc',
        'image_url': '/static/hvcc-logo.png'
    },
    #{
        #'name': 'MAX RNBO',
        #'href': '/rnbo',
        #'image_url': '/static/max-8-logo.png'
    #},
]

categories = [
    '(none)',
    'Delay',
    'Distortion',
    'Dynamics',
    'Filter',
    'Generator',
    'MIDI',
    'Modulator',
    'Reverb',
    'Simulator',
    'Spatial',
    'Spectral',
    'Utility',
]

targets = {
    'duo': 'modduo-builder:8001',
    'duox': 'modduox-builder:8002',
    'dwarf': 'moddwarf-builder:8003',
}

# setup
app = Flask(__name__)
# Disable caching?
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app, cors_allowed_origins="*")

def sanitize(name):
    if not name:
        return None
    name = normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii', 'ignore')
    name = name.replace('\r', '')
    name = name.replace('\n', '')
    name = name.replace('\t', ' ')
    name = name.replace('"', '')
    name = name.replace('$', '')
    name = name.replace('`', '')
    name = name.replace('\\', '')
    if not name:
        return None
    if name[0].isalpha():
        name = '_' + name
    return name

def symbolify(name):
    if len(name) == 0:
        return '_'
    name = re_sub('[^_a-zA-Z0-9]+', '_', name)
    if name[0].isdigit():
        name = '_' + name
    return name

@socketio.on('build')
def build(msg):
    print('build started')

    buildtype = msg.get('type', None)
    if buildtype is None or buildtype not in ('faust', 'hvcc', 'maxgen'):
        emit('buildlog', 'Invalid build target, cannot continue')
        emit('status', 'error')
        return

    device = msg.get('device', None)
    if device is None or device not in targets:
        emit('buildlog', 'Invalid device target, cannot continue')
        emit('status', 'error')
        return

    name = msg.get('name', None)
    if not name:
        emit('buildlog', 'Name is empty, cannot continue')
        emit('status', 'error')
        return

    name = sanitize(name)
    if not name:
        emit('buildlog', 'Invalid name, cannot continue')
        emit('status', 'error')
        return

    symbol = msg.get('symbol', None)
    if not symbol:
        emit('buildlog', 'Symbol is empty, cannot continue')
        emit('status', 'error')
        return

    files = msg.get('files', None)
    if not files:
        emit('buildlog', 'No files provided, cannot continue')
        emit('status', 'error')
        return

    brand = msg.get('brand', None)
    if brand is None:
        emit('buildlog', 'Symbol is empty, cannot continue')
        emit('status', 'error')
        return

    brand = sanitize(brand)

    category = msg.get('category', None)
    if category is None or category not in categories:
        emit('buildlog', 'Invalid category, cannot continue')
        emit('status', 'error')
        return

    symbol = symbolify(symbol)

    if category == '(none)':
        category = 'lv2:Plugin'
    else:
        category = f"lv2:{category}Plugin"

    if buildtype == 'faust':
        if len(files.keys()) != 1:
            emit('buildlog', 'More than 1 file uploaded, this is not allowed, please upload a single file')
            emit('status', 'error')
            return

        if not brand:
            brand = 'FAUST'

        bundle = f"faust-{symbol}"
        package = f"""
FAUST_SKELETON_VERSION = febaa50e4b1fcb0ec5ecfac1810c397ba70cf841
FAUST_SKELETON_SITE = https://github.com/moddevices/faust-skeleton.git
FAUST_SKELETON_SITE_METHOD = git
FAUST_SKELETON_BUNDLES = {bundle}.lv2

FAUST_SKELETON_TARGET_MAKE = $(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) PREFIX=/usr NOOPT=true -C $(@D)

define FAUST_SKELETON_CONFIGURE_CMDS
	rmdir $(@D)/source/dpf
	ln -s /root/dpf $(@D)/source/dpf
	cp $($(PKG)_PKGDIR)/*.dsp $(@D)/plugin/
	env FAUST_AUTOMATED=1 \
		FAUST_NAME="{name}" \
		FAUST_BRAND="{brand}" \
		FAUST_SYMBOL="{symbol}" \
		FAUST_DESCRIPTION="FAUST based plugin, automatically generated via mod-cloud-builder" \
		FAUST_LV2_CATEGORY="{category}" \
		$(@D)/setup.sh
endef

define FAUST_SKELETON_BUILD_CMDS
	$(FAUST_SKELETON_TARGET_MAKE)
endef

define FAUST_SKELETON_INSTALL_TARGET_CMDS
	mv $(@D)/bin/*.lv2 $($(PKG)_PKGDIR)/{bundle}.lv2
endef

$(eval $(generic-package))
"""

    elif buildtype == 'maxgen':
        if 'gen_exported.cpp' not in files:
            emit('buildlog', 'The file gen_exported.cpp is missing, cannot continue')
            emit('status', 'error')
            return

        if 'gen_exported.h' not in files:
            emit('buildlog', 'The file gen_exported.h is missing, cannot continue')
            emit('status', 'error')
            return

        if not brand:
            brand = 'MAX gen~'

        bundle = f"max-gen-{symbol}"
        package = f"""
MAX_GEN_SKELETON_VERSION = b236792fa2bd4c3173c7182afe3e358a77e58df1
MAX_GEN_SKELETON_SITE = https://github.com/moddevices/max-gen-skeleton.git
MAX_GEN_SKELETON_SITE_METHOD = git
MAX_GEN_SKELETON_BUNDLES = {bundle}.lv2

MAX_GEN_SKELETON_TARGET_MAKE = $(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) PREFIX=/usr NOOPT=true -C $(@D)

define MAX_GEN_SKELETON_CONFIGURE_CMDS
	rmdir $(@D)/source/dpf
	ln -s /root/dpf $(@D)/source/dpf
	cp $($(PKG)_PKGDIR)/gen_exported.cpp $(@D)/plugin/
	cp $($(PKG)_PKGDIR)/gen_exported.h $(@D)/plugin/
	env MAX_GEN_AUTOMATED=1 \
		MAX_GEN_NAME="{name}" \
		MAX_GEN_BRAND="{brand}" \
		MAX_GEN_SYMBOL="{symbol}" \
		MAX_GEN_DESCRIPTION="MAX gen~ based plugin, automatically generated via mod-cloud-builder" \
		MAX_GEN_LV2_CATEGORY="{category}" \
		$(@D)/setup.sh
endef

define MAX_GEN_SKELETON_BUILD_CMDS
	$(MAX_GEN_SKELETON_TARGET_MAKE)
endef

define MAX_GEN_SKELETON_INSTALL_TARGET_CMDS
	mv $(@D)/bin/*.lv2 $($(PKG)_PKGDIR)/{bundle}.lv2
endef

$(eval $(generic-package))
"""

    elif buildtype == 'hvcc':
        if len(files.keys()) != 1:
            emit('buildlog', 'More than 1 file uploaded, this is not allowed, please upload a single file')
            emit('status', 'error')
            return

        if not brand:
            brand = 'Pure Data'

        bundle = f"hvcc-{symbol}"
        package = f"""
PURE_DATA_SKELETON_VERSION = 4fbaa17f0e54f92ec3502b3e0033676469dde390
PURE_DATA_SKELETON_SITE = https://github.com/Wasted-Audio/hvcc.git
PURE_DATA_SKELETON_SITE_METHOD = git
PURE_DATA_SKELETON_BUNDLES = {bundle}.lv2

PURE_DATA_SKELETON_TARGET_MAKE = $(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) PREFIX=/usr NOOPT=true -C $(@D)

define PURE_DATA_SKELETON_CONFIGURE_CMDS
	# install hvcc
	pip3 install -e $(@D) --break-system-packages
	# place symlink to dpf (known working version)
	ln -s /root/dpf $(@D)/dpf
	# create plugin files
	mkdir $(@D)/plugin
	cp $($(PKG)_PKGDIR)/*.pd $(@D)/plugin/plugin.pd
	echo '{{\
    "name": "{name}",\
    "dpf": {{\
        "description": "Pure Data (hvcc) based plugin, automatically generated via mod-cloud-builder",\
        "homepage": "https://github.com/Wasted-Audio/hvcc",\
        "license": "ISC",\
        "lv2_info": "{category}",\
        "maker": "{brand}",\
        "midi_input": 0,\
        "midi_output": 0,\
        "plugin_uri": "urn:hvcc:{symbol}",\
        "plugin_formats ":["lv2_sep"],\
        "version": "0, 0, 0"\
    }}\
}}' > $(@D)/plugin/plugin.json
	hvcc $(@D)/plugin/plugin.pd -m $(@D)/plugin/plugin.json -n "{name}" -g dpf -o $(@D)
endef

define PURE_DATA_SKELETON_BUILD_CMDS
	$(PURE_DATA_SKELETON_TARGET_MAKE)
endef

define PURE_DATA_SKELETON_INSTALL_TARGET_CMDS
	mv $(@D)/bin/*.lv2 $($(PKG)_PKGDIR)/{bundle}.lv2
endef

$(eval $(generic-package))
"""

    else:
        emit('buildlog', 'Requested build target is not yet implemented, cannot continue')
        emit('status', 'error')
        return

    reqdata = json.dumps({
      'name': name,
      'files': files,
      'package': package,
    }).encode('utf-8')

    reqheaders = {
      'Content-Type': 'application/json; charset=UTF-8',
    }

    targethost = targets[device]

    req = urlopen(Request(f'http://{targethost}/', data=reqdata, headers=reqheaders))
    resp = json.loads(req.read().decode('utf-8'))

    if not resp['ok']:
        emit('buildlog', resp['error'])
        emit('status', 'error')
        return

    @copy_current_request_context
    def buildlog(ws, reqid):
        if not ws.connected:
            emit('buildlog', 'server-side build job closed unexpectedly')
            emit('status', 'error')
            ws.close()
            return

        recv = ws.recv()
        if not recv or not ws.connected:
            emit('buildlog', 'server-side build job closed unexpectedly')
            emit('status', 'error')
            ws.close()
            return

        elif recv == '--- END ---':
            reqdata = json.dumps({
                'id': reqid
            }).encode('utf-8')
            req = urlopen(Request(f'http://{targethost}/', data=reqdata, headers=reqheaders, method='GET'))
            resp = req.read()
            emit('buildfile', encodebytes(resp).decode('utf-8'))
            ws.close()
            return

        print(recv, end='')
        emit('buildlog', recv)
        spawn(buildlog, ws, reqid)

    ws = create_connection(f'ws://{targethost}/build')
    ws.send(resp['id'])

    if not ws.connected:
        emit('buildlog', 'failed to start server-side build job')
        emit('status', 'error')
        ws.close()
        return

    emit('status', 'building')
    spawn(buildlog, ws, resp['id'])

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', builders=builders)

@app.route('/faust', methods=['GET'])
def faust():
    return render_template('builder.html',
                           categories=categories,
                           buildername='FAUST',
                           buildertype='faust',
                           name='',
                           brand='',
                           symbol='',
                           category='(none)',
                           fileexts='.dsp',
                           filenames='faust dsp')

@app.route('/faust', methods=['POST'])
def faust_post():
    return Response(status=204)

@app.route('/maxgen', methods=['GET'])
def maxgen():
    return render_template('builder.html',
                           categories=categories,
                           buildername='MAX gen~',
                           buildertype='maxgen',
                           name='',
                           brand='',
                           symbol='',
                           category='(none)',
                           fileexts='.h, .cpp',
                           filenames='gen_exported.cpp and gen_exported.h')

@app.route('/maxgen', methods=['POST'])
def maxgen_post():
    return Response(status=204)

@app.route('/hvcc', methods=['GET'])
def hvcc():
    return render_template('builder.html',
                           categories=categories,
                           buildername='Pure Data / hvcc',
                           buildertype='hvcc',
                           name='',
                           brand='',
                           symbol='',
                           category='(none)',
                           fileexts='.pd',
                           filenames='puredata patch')

@app.route('/hvcc', methods=['POST'])
def hvcc_post():
    return Response(status=204)

@app.route('/puredata', methods=['GET'])
def puredata():
    return redirect('/hvcc', code=302)

@app.route('/plugins', methods=['GET'])
def plugins():
    return render_template('plugins.html')

@app.route('/static/<path:path>', methods=['GET'])
def png(path):
    return send_from_directory('static', path)

@app.route('/mod-ui/<path:path>', methods=['GET'])
def mod_ui(path):
    return send_from_directory(MOD_UI_HTML_DIR, path)

#@app.route('/<path:path>.png', methods=['GET'])
#def png(path):
    #return send_from_directory(MOD_UI_HTML_DIR, path+'.png')

# plugin store compat
@app.route('/lv2/plugins', methods=['GET'])
def lv2_plugins():
    return []

@app.route('/lv2/plugins/featured', methods=['GET'])
def lv2_plugins_featured():
    return []

@app.route('/pedalboards/stats', methods=['GET'])
def pedalboards_stats():
    return {}

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=8000)
