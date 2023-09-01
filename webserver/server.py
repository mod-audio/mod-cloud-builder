#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# imports
import os
import sys
import json

from base64 import encodebytes
from flask import Flask, copy_current_request_context, request, render_template, send_from_directory
from flask_socketio import SocketIO, emit, send
from gevent import spawn
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
        'image_url': 'https://faust.grame.fr/img/faustText.svg'
    },
    { 
        'name': 'MAX gen~', 
        'href': '/maxgen',
        'image_url': 'https://modbox.kx.studio/pedalboard/image/thumbnail.png?bundlepath=/home/falktx/.pedalboards/new_stuff-33014.pedalboard'
    },
    {
        'name': 'MAX RNBO', 
        'href': '/rnbo',
        'image_url': 'https://modbox.kx.studio/pedalboard/image/thumbnail.png?bundlepath=/home/falktx/.pedalboards/new_stuff-33014.pedalboard'
    },
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

# setup
app = Flask(__name__)
# Disable caching?
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app)

@socketio.on('connect')
def test_connect(auth):
    print('Client Connected', auth)
    emit('response', {'data': 'Connected'})

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

def read_example_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), 'r') as fh:
        return fh.read()

@socketio.on('my event')
def test_message(msg):
    print('Client message', msg)

    targethost = '127.0.0.1:8003'

    name = "max-gen-demo"
    # | sed -e "s/[^A-Za-z0-9._-]/_/g"

    reqdata = json.dumps({
      'name': '',
      'files': [
          {
              'filename': "gen_exported.cpp",
              'content': read_example_file("examples/gen_exported.cpp"),
          },
          {
              'filename': "gen_exported.h",
              'content': read_example_file("examples/gen_exported.h"),
          }
      ],
      'package': f"""
MAX_GEN_SKELETON_VERSION = 7b93c46d1b689d93b405256d86de31fb380b4966
MAX_GEN_SKELETON_SITE = https://github.com/moddevices/max-gen-skeleton.git
MAX_GEN_SKELETON_SITE_METHOD = git
MAX_GEN_SKELETON_BUNDLES = {name}.lv2

MAX_GEN_SKELETON_TARGET_MAKE = $(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) PREFIX=/usr NOOPT=true -C $(@D)

MAX_GEN_SKELETON_PRE_DOWNLOAD_HOOKS += MOD_PLUGIN_BUILDER_DOWNLOAD_WITH_SUBMODULES

define MAX_GEN_SKELETON_CONFIGURE_CMDS
	cp $($(PKG)_PKGDIR)/gen_exported.cpp $(@D)/plugin/
	cp $($(PKG)_PKGDIR)/gen_exported.h $(@D)/plugin/
	echo {name} | $(@D)/setup.sh
endef

define MAX_GEN_SKELETON_BUILD_CMDS
	$(MAX_GEN_SKELETON_TARGET_MAKE)
endef

define MAX_GEN_SKELETON_INSTALL_TARGET_CMDS
	cp -r $(@D)/bin/*.lv2 $($(PKG)_PKGDIR)/
endef

$(eval $(generic-package))
"""
    }).encode('utf-8')

    reqheaders = {
      'Content-Type': 'application/json; charset=UTF-8',
    }

    req = urlopen(Request(f'http://{targethost}/', data=reqdata, headers=reqheaders))
    resp = json.loads(req.read().decode('utf-8'))
    print(resp)

    if not resp['ok']:
        emit('buildlog', resp['error'])
        emit('status', 'error')
        return

    @copy_current_request_context
    def buildlog(ws, reqid):
        if not ws.connected:
            ws.close()
            emit('status', 'closed')
            return

        recv = ws.recv()
        if recv == '':
            ws.close()
            emit('status', 'finished')
            return

        if recv == '--- END ---':
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
        emit('status', 'error')
        return

    emit('status', 'started')
    spawn(buildlog, ws, resp['id'])

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', builders=builders)

@app.route('/faust', methods=['GET'])
def faust():
    return render_template('faust.html', categories=categories, uri='urn:faust:example')

@app.route('/plugins', methods=['GET'])
def plugins():
    return render_template('plugins.html')

@app.route('/mod-ui/<path:path>', methods=['GET'])
def mod_ui(path):
    return send_from_directory(MOD_UI_HTML_DIR, path)

@app.route('/<path:path>.png', methods=['GET'])
def png(path):
    return send_from_directory(MOD_UI_HTML_DIR, path+'.png')

# plugin store compat
@app.route('/lv2/plugins', methods=['GET'])
def lv2_plugins():
    bin_compat = 'aarch64-a53'
    return [
{
    "author": {
      "email": "",
      "homepage": "http://aidadsp.cc",
      "name": "Aida DSP"
    },
    "bin_compats": [
      "arm-a7",
      "aarch64-a53",
      "aarch64-a35"
    ],
    "binary": "rt-neural-twinclassic.so",
    "brand": "Aida DSP",
    "buildEnvironment": "prod",
    "buildId": 1125,
    "builder_version": "1",
    "bundle_href": "https://api.mod.audio/v2/lv2/bundles/64a061e83162a15f35dc7953/",
    "bundle_id": "64a061e83162a15f35dc7953",
    "bundle_multi_plugins": False,
    "bundle_name": "rt-neural-twinclassic.lv2",
    "bundles": [],
    "category": [
      "Simulator"
    ],
    "comment": "High quality model based on an original with volume and channel control - just like the real amp.\n\nParameterized controls:\n    Volume\n\nDrawing inspiration from the renowned Fender 65 Twin Reverb* amplifier known for being an all-time classic of biting twang and shimmering clean tones, TWIN CLASSIC faithfully captures the essence of what makes this amp truly special.\n\n*Product names and trademarks are the property of their respective holders that do not endorse and are not associated or affiliated with MOD Audio or AIDA DSP; they were used merely to identify the product whose sound was incorporated in the creation of this plugin.\n\nHistory and Usage:\n    See link: http://aida-x.cc/plugins",
    "gui": {
      "screenshot": "modgui/screenshot-rt-neural-twinclassic.png",
      "thumbnail": "modgui/thumbnail-rt-neural-twinclassic.png"
    },
    "href": "https://api.mod.audio/v2/lv2/plugins/64a061e93162a15f35dc797e/",
    "id": "64a061e93162a15f35dc797e",
    "image_required": [
      1,
      0
    ],
    "label": "Twin Classic",
    "license": "http://opensource.org/licenses/isc",
    "microVersion": 9,
    "minorVersion": 0,
    "mod_license": "paid_perpetual",
    "name": "Twin Classic Powered By AIDA-X",
    "ports": {
      "audio": {
        "input": [
          {
            "comment": "",
            "designation": "",
            "index": 0,
            "name": "IN",
            "shortName": "IN",
            "symbol": "IN"
          }
        ],
        "output": [
          {
            "comment": "",
            "designation": "",
            "index": 1,
            "name": "OUT",
            "shortName": "OUT",
            "symbol": "OUT"
          }
        ]
      },
      "control": {
        "input": [
          {
            "index": 2,
            "name": "Model",
            "shortName": "Model",
            "symbol": "model",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 3,
            "name": "ANTIALIASING",
            "shortName": "ANTIALIASING",
            "symbol": "ANTIALIASING",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 4,
            "name": "INPUT",
            "shortName": "INPUT",
            "symbol": "PREGAIN",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 5,
            "name": "NETBYPASS",
            "shortName": "NETBYPASS",
            "symbol": "NETBYPASS",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 6,
            "name": "VOLUME",
            "shortName": "VOLUME",
            "symbol": "PARAM1",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 7,
            "name": "PARAM2",
            "shortName": "PARAM2",
            "symbol": "PARAM2",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 8,
            "name": "EQBYPASS",
            "shortName": "EQBYPASS",
            "symbol": "EQBYPASS",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 9,
            "name": "EQPOS",
            "shortName": "EQPOS",
            "symbol": "EQPOS",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 10,
            "name": "BASS",
            "shortName": "BASS",
            "symbol": "BASS",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 11,
            "name": "BFREQ",
            "shortName": "BFREQ",
            "symbol": "BFREQ",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 12,
            "name": "MID",
            "shortName": "MID",
            "symbol": "MID",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 13,
            "name": "MFREQ",
            "shortName": "MFREQ",
            "symbol": "MFREQ",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 14,
            "name": "MIDQ",
            "shortName": "MIDQ",
            "symbol": "MIDQ",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 15,
            "name": "MTYPE",
            "shortName": "MTYPE",
            "symbol": "MTYPE",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 16,
            "name": "TREBLE",
            "shortName": "TREBLE",
            "symbol": "TREBLE",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 17,
            "name": "TFREQ",
            "shortName": "TFREQ",
            "symbol": "TFREQ",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 18,
            "name": "DEPTH",
            "shortName": "DEPTH",
            "symbol": "DEPTH",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 19,
            "name": "PRESENCE",
            "shortName": "PRESENCE",
            "symbol": "PRESENCE",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          },
          {
            "index": 20,
            "name": "OUTPUT",
            "shortName": "OUTPUT",
            "symbol": "MASTER",
            "ranges": { "default": 0, "maximum": 3, "minimum": 0 },
          }
        ],
        "output": [
          {
            "comment": "",
            "designation": "",
            "index": 21,
            "name": "Model Input Size",
            "shortName": "Model Input Size",
            "symbol": "ModelInSize"
          }
        ]
      },
      "midi": {
        "input": [],
        "output": []
      }
    },
    "presets": [],
    "release_number": 2,
    "screenshot": {
      "height": 359,
      "width": 1032
    },
    "screenshot_available": True,
    "screenshot_href": "https://api.mod.audio/v2/lv2/plugins/64a061e93162a15f35dc797e/screenshot/",
    "stability": "experimental",
    "stable": False,
    "thumbnail_available": True,
    "thumbnail_href": "https://api.mod.audio/v2/lv2/plugins/64a061e93162a15f35dc797e/thumbnail/",
    "uri": "http://aidadsp.cc/plugins/aidadsp-bundle/rt-neural-twinclassic",
    "version": "0.9"
  }
]

@app.route('/lv2/plugins/featured', methods=['GET'])
def lv2_plugins_featured():
    return []

@app.route('/pedalboards/stats', methods=['GET'])
def pedalboards_stats():
    return {}

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=8000)
