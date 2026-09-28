#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023-2025 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# Reads the name, brand, author and category of the plugin(s) inside a built LV2 bundle.
# Needed for buildroot builds, where these are defined by the plugin itself and not by the
# builder page. Follows the same rules as mod-ui (utils/utils_lilv.cpp).

import tarfile

from urllib.parse import quote, unquote

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS

DOAP = Namespace('http://usefulinc.com/ns/doap#')
FOAF = Namespace('http://xmlns.com/foaf/0.1/')
LV2 = Namespace('http://lv2plug.in/ns/lv2core#')
MOD = Namespace('http://moddevices.com/ns/mod#')

BASE_URI = 'file:///'

# limits for what we are willing to read out of a build
MAX_TTL_FILES = 256
MAX_TTL_SIZE = 4 * 1024 * 1024
MAX_VALUE_LENGTH = 128

# plugin class -> top-level category, as shown by mod-ui
LV2_CATEGORIES = {
    'DelayPlugin': 'Delay',
    'DistortionPlugin': 'Distortion',
    'WaveshaperPlugin': 'Distortion',
    'DynamicsPlugin': 'Dynamics',
    'AmplifierPlugin': 'Dynamics',
    'CompressorPlugin': 'Dynamics',
    'ExpanderPlugin': 'Dynamics',
    'GatePlugin': 'Dynamics',
    'LimiterPlugin': 'Dynamics',
    'FilterPlugin': 'Filter',
    'AllpassPlugin': 'Filter',
    'BandpassPlugin': 'Filter',
    'CombPlugin': 'Filter',
    'EQPlugin': 'Filter',
    'MultiEQPlugin': 'Filter',
    'ParaEQPlugin': 'Filter',
    'HighpassPlugin': 'Filter',
    'LowpassPlugin': 'Filter',
    'GeneratorPlugin': 'Generator',
    'ConstantPlugin': 'Generator',
    'InstrumentPlugin': 'Generator',
    'OscillatorPlugin': 'Generator',
    'ModulatorPlugin': 'Modulator',
    'ChorusPlugin': 'Modulator',
    'FlangerPlugin': 'Modulator',
    'PhaserPlugin': 'Modulator',
    'ReverbPlugin': 'Reverb',
    'SimulatorPlugin': 'Simulator',
    'SpatialPlugin': 'Spatial',
    'SpectralPlugin': 'Spectral',
    'PitchPlugin': 'Spectral',
    'UtilityPlugin': 'Utility',
    'AnalyserPlugin': 'Utility',
    'ConverterPlugin': 'Utility',
    'FunctionPlugin': 'Utility',
    'MixerPlugin': 'Utility',
    'MIDIPlugin': 'MIDI',
}

MOD_CATEGORIES = {
    'DelayPlugin': 'Delay',
    'DistortionPlugin': 'Distortion',
    'DynamicsPlugin': 'Dynamics',
    'FilterPlugin': 'Filter',
    'GeneratorPlugin': 'Generator',
    'ModulatorPlugin': 'Modulator',
    'ReverbPlugin': 'Reverb',
    'SimulatorPlugin': 'Simulator',
    'SpatialPlugin': 'Spatial',
    'SpectralPlugin': 'Spectral',
    'UtilityPlugin': 'Utility',
    'MIDIPlugin': 'MIDI',
    'MaxGenPlugin': 'MaxGen',
    'CamomilePlugin': 'Camomile',
    'ControlVoltagePlugin': 'ControlVoltage',
}

def _read_ttl_files(filename):
    # only the turtle files at the top-level of the bundle, which is where the manifest
    # and the plugin definitions are
    ttls = {}
    with tarfile.open(filename, 'r:gz') as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith('.ttl'):
                continue
            if member.name.count('/') != 1 or member.size > MAX_TTL_SIZE:
                continue
            ttls[member.name] = tar.extractfile(member).read()
            if len(ttls) >= MAX_TTL_FILES:
                break
    return ttls

def _parse(graph, ttls, name):
    try:
        graph.parse(data=ttls[name], format='turtle', publicID=BASE_URI + quote(name))
    except Exception as e:
        print(f'bundleinfo: failed to parse {name}: {e}')
        return False
    return True

def _text(value):
    if value is None:
        return ''
    return ' '.join(str(value).split())[:MAX_VALUE_LENGTH]

def _author(graph, plugin):
    # same lookup as lilv_plugin_get_author_name
    for subject in (plugin, graph.value(plugin, LV2.project)):
        if subject is None:
            continue
        for maintainer in graph.objects(subject, DOAP.maintainer):
            name = _text(graph.value(maintainer, FOAF.name))
            if name:
                return name
    return ''

def _category(graph, plugin):
    types = sorted(str(t) for t in graph.objects(plugin, RDF.type))

    # a MOD category takes precedence over the LV2 ones
    for namespace, categories in ((MOD, MOD_CATEGORIES), (LV2, LV2_CATEGORIES)):
        for t in types:
            if t.startswith(str(namespace)) and t[len(str(namespace)):] in categories:
                return categories[t[len(str(namespace)):]]

    return '(none)'

def read_bundle_info(filename):
    """
    Get the details of the plugin(s) in a bundle, as a dict with
    'name', 'brand', 'author' and 'category' keys.
    `filename` is the .tar.gz of the bundle, as stored after a build.
    Returns an empty dict if there is nothing we can read in there.
    """
    try:
        ttls = _read_ttl_files(filename)
    except (OSError, EOFError, tarfile.TarError) as e:
        print(f'bundleinfo: failed to read {filename}: {e}')
        return {}

    names = []
    info = {}

    for manifest in sorted(name for name in ttls if name.endswith('/manifest.ttl')):
        graph = Graph()
        if not _parse(graph, ttls, manifest):
            continue

        plugins = sorted(set(graph.subjects(RDF.type, LV2.Plugin)))

        # load the files where the plugins are fully defined
        seealso = set()
        for plugin in plugins:
            for ref in graph.objects(plugin, RDFS.seeAlso):
                ref = unquote(str(ref))
                if ref.startswith(BASE_URI) and ref[len(BASE_URI):] in ttls:
                    seealso.add(ref[len(BASE_URI):])

        for name in sorted(seealso):
            _parse(graph, ttls, name)

        for plugin in plugins:
            name = _text(graph.value(plugin, DOAP.name))
            if not name:
                continue

            author = _author(graph, plugin)
            brand = _text(graph.value(plugin, MOD.brand)) or author

            names.append(name)
            if not info:
                info = {
                    'brand': brand,
                    'author': author,
                    'category': _category(graph, plugin),
                }

    if not names:
        return {}

    info['name'] = ', '.join(names)[:MAX_VALUE_LENGTH]
    return info

if __name__ == "__main__":
    import sys
    import json
    for arg in sys.argv[1:]:
        print(arg, json.dumps(read_bundle_info(arg)))
