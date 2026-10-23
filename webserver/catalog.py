#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# Internal catalog of the shared builds kept in the builder storage.
# Read-only on the storage; not served by the site.
#
#   catalog.py <storage dir> <output dir> [--base-url https://builder.mod.audio]
#
# writes catalog.json (one entry per build), catalog.csv and catalog.md (one row per plugin,
# newest build first, plus the failed and incomplete builds).

import csv
import json
import os
import sys
import tarfile

from datetime import datetime, timezone
from urllib.parse import unquote

from rdflib import Graph
from rdflib.namespace import RDF, RDFS

from bundleinfo import BASE_URI, DOAP, LV2, _parse, _read_ttl_files, _text, read_bundle_info

TARGETS = ('duo', 'duox', 'dwarf', 'anagram')
GENERATED = (('faust-', 'faust'), ('max-gen-', 'maxgen'), ('hvcc-', 'hvcc'))

def load_json(filename):
    try:
        with open(filename) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None

def mtime(path):
    return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def bundle_details(filename):
    # bundle folder name, plugin URIs and licences, which the share page does not need
    details = {'bundle': None, 'uris': [], 'license': ''}
    try:
        with tarfile.open(filename, 'r:gz') as tar:
            for member in tar:
                details['bundle'] = member.name.split('/', 1)[0]
                break
        ttls = _read_ttl_files(filename)
    except (OSError, EOFError, tarfile.TarError):
        return details

    licenses = set()
    for manifest in sorted(name for name in ttls if name.endswith('/manifest.ttl')):
        graph = Graph()
        if not _parse(graph, ttls, manifest):
            continue
        plugins = sorted(set(graph.subjects(RDF.type, LV2.Plugin)))
        for plugin in plugins:
            for ref in graph.objects(plugin, RDFS.seeAlso):
                ref = unquote(str(ref))
                if ref.startswith(BASE_URI) and ref[len(BASE_URI):] in ttls:
                    _parse(graph, ttls, ref[len(BASE_URI):])
        for plugin in plugins:
            details['uris'].append(str(plugin))
            for subject in (plugin, graph.value(plugin, LV2.project)):
                if subject is not None:
                    for value in graph.objects(subject, DOAP.license):
                        licenses.add(_text(value))
    details['license'] = ', '.join(sorted(licenses))
    return details

def scan(storage, base_url):
    entries = []
    for build_id in sorted(os.listdir(storage)):
        path = os.path.join(storage, build_id)
        if not os.path.isdir(path):
            continue

        config = load_json(os.path.join(path, 'config.json')) or {}
        record = load_json(os.path.join(path, 'build.json')) or {}

        targets = {}
        for target in TARGETS:
            filename = os.path.join(path, target + '.tar.gz')
            if os.path.exists(filename):
                targets[target] = os.path.getsize(filename)
        built = [t for t, size in targets.items() if size > 0]

        info = {}
        details = {'bundle': None, 'uris': [], 'license': ''}
        for target in built:
            filename = os.path.join(path, target + '.tar.gz')
            info = read_bundle_info(filename)
            details = bundle_details(filename)
            if info or details['bundle']:
                break

        buildtype = record.get('type')
        if not buildtype:
            bundle = details['bundle'] or ''
            buildtype = next((t for prefix, t in GENERATED if bundle.startswith(prefix)), 'buildroot' if bundle else '')

        if not config:
            status = 'incomplete'
        elif not built:
            status = 'failed'
        elif len(built) < len(targets):
            status = 'partial'
        else:
            status = 'ok'

        sources = record.get('sources') or {}
        srcvars = sources.get('vars') or {}
        srcdir = os.path.join(path, 'source')

        entries.append({
            'id': build_id,
            'url': f'{base_url}/install/{build_id}',
            'date': record.get('created') or mtime(path),
            'status': status,
            'type': buildtype,
            'name': config.get('name') or info.get('name', ''),
            'brand': config.get('brand') or info.get('brand', ''),
            'author': config.get('author') or info.get('author', ''),
            'category': config.get('category') or info.get('category', ''),
            'license': details['license'],
            'bundle': details['bundle'],
            'uris': details['uris'],
            'targets_built': built,
            'targets_failed': [t for t in targets if t not in built],
            'archived_inputs': sorted(os.listdir(srcdir)) if os.path.isdir(srcdir) else [],
            'source_site': srcvars.get('SITE', ''),
            'source_version': srcvars.get('VERSION', ''),
            'source_files': sources.get('files', []),
        })
    return entries

def plugin_key(entry):
    return ' '.join(entry['uris']) or entry['bundle'] or entry['name'] or entry['id']

def latest_per_plugin(entries):
    plugins = {}
    for entry in sorted(entries, key=lambda e: e['date']):
        if entry['status'] not in ('ok', 'partial'):
            continue
        key = plugin_key(entry)
        builds = plugins.get(key, {}).get('builds', 0) + 1
        plugins[key] = dict(entry, builds=builds)
    return sorted(plugins.values(), key=lambda e: (e['name'].lower(), e['date']))

def md_cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')

def write_outputs(entries, outdir):
    os.makedirs(outdir, exist_ok=True)
    plugins = latest_per_plugin(entries)
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    with open(os.path.join(outdir, 'catalog.json'), 'w') as fh:
        json.dump({'generated': generated, 'builds': entries}, fh, indent=2)

    columns = ('name', 'brand', 'author', 'category', 'license', 'type', 'date', 'builds',
               'targets_built', 'source_site', 'source_version', 'url', 'id', 'bundle', 'uris')
    with open(os.path.join(outdir, 'catalog.csv'), 'w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for p in plugins:
            writer.writerow([' '.join(p[c]) if isinstance(p[c], list) else p[c] for c in columns])

    counts = {}
    for entry in entries:
        counts[entry['status']] = counts.get(entry['status'], 0) + 1
    with_sources = sum(1 for e in entries if e['archived_inputs'])

    lines = [
        '# Cloud Builder catalog (internal)',
        '',
        f'Generated {generated} from the builder storage. Internal only: these are user builds, '
        'not tested or endorsed by MOD, and many state no licence.',
        '',
        f'- Shared builds: {len(entries)} '
        f'({", ".join(f"{k} {v}" for k, v in sorted(counts.items()))})',
        f'- Distinct plugins with a working build: {len(plugins)}',
        f'- Builds with archived inputs (.mk / sources): {with_sources}',
        '',
        '## Plugins (newest build of each)',
        '',
        '| Plugin | Brand | Category | Licence | Type | Devices | Date | Builds | Source | Link |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for p in plugins:
        source = p['source_site'] + (f" @ {p['source_version']}" if p['source_version'] else '')
        lines.append('| ' + ' | '.join(md_cell(v) for v in (
            p['name'] or '(no name)', p['brand'], p['category'], p['license'] or '-', p['type'],
            ', '.join(p['targets_built']), p['date'][:10], p['builds'], source or '-',
            f"[{p['id']}]({p['url']})")) + ' |')

    lines += ['', '## Failed and incomplete builds', '',
              '| Id | Date | Status | Name | Inputs archived |', '| --- | --- | --- | --- | --- |']
    for e in sorted(entries, key=lambda e: e['date']):
        if e['status'] in ('failed', 'incomplete'):
            lines.append(f"| {e['id']} | {e['date'][:10]} | {e['status']} | {md_cell(e['name'] or '-')} | "
                         f"{'yes' if e['archived_inputs'] else 'no'} |")

    with open(os.path.join(outdir, 'catalog.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')

    return len(entries), len(plugins)

if __name__ == '__main__':
    args = sys.argv[1:]
    base_url = 'https://builder.mod.audio'
    if '--base-url' in args:
        i = args.index('--base-url')
        base_url = args[i + 1].rstrip('/')
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__ or 'usage: catalog.py <storage dir> <output dir> [--base-url URL]')
        sys.exit(1)
    builds, plugins = write_outputs(scan(args[0], base_url), args[1])
    print(f'{builds} builds, {plugins} plugins -> {args[1]}')
