// MOD Cloud Builder
// SPDX-FileCopyrightText: 2023-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Browser-side helpers for the connection to a MOD unit plugged in over USB.
//
// The unit is reached at ws://192.168.51.1/rplsocket, a private-network address,
// and browsers restrict how a public web page may talk to such addresses:
//
//  - Chromium-based browsers (Chrome, Edge, Brave, Opera...) apply "Local Network
//    Access" (LNA) rules. From a non-secure http:// page the connection is refused
//    outright (fetch since Chrome 142, WebSockets since Chrome 147). From a secure
//    https:// page it is allowed after the user accepts a one-time permission
//    prompt; plain ws:// is then exempt from mixed content checks because the
//    destination is an IP literal on the local network.
//    https://developer.chrome.com/blog/local-network-access
//
//  - Firefox and Safari have no LNA yet, but they do apply the regular mixed
//    content rule: an https:// page may not open ws:// to a non-loopback address.
//    From an http:// page the connection just works.
//
// So the http:// and https:// versions of this site each work in one browser
// family, and these helpers steer the user to the right one.

var MOD_DEVICE_WS_URL = 'ws://192.168.51.1/rplsocket';
var MOD_MIN_VERSION = '1.13.3';

// first Chromium major that refuses WebSockets to the local network from http:// pages
var MOD_LNA_WEBSOCKET_CHROMIUM = 147;

// Major version of the Chromium engine, 0 for any other browser.
// navigator.userAgentData only exists in secure contexts, so the http:// site (where the
// answer matters most) has to fall back to the user agent string. Every Chromium-based
// browser keeps a "Chrome/<major>" token in it (Edge, Brave, Opera included); Chrome on
// iOS says "CriOS" instead and is really WebKit, so it correctly reads as 0 here.
function modChromiumMajor() {
    try {
        var brands = navigator.userAgentData.brands;
        for (var i = 0; i < brands.length; ++i) {
            if (brands[i].brand === 'Chromium') {
                return parseInt(brands[i].version, 10) || 0;
            }
        }
    } catch (e) {}
    var match = /\bChrome\/(\d+)/.exec(navigator.userAgent);
    if (match) {
        return parseInt(match[1], 10) || 0;
    }
    return 0;
}

function modSiblingUrl(protocol) {
    return protocol + '//' + window.location.host + window.location.pathname + window.location.search;
}

function modLink(protocol) {
    var url = modSiblingUrl(protocol);
    return '<a href="' + url + '">' + url + '</a>';
}

// true when this page cannot reach the unit because of the Chromium LNA rules
function modBlockedByLocalNetworkAccess() {
    return !window.isSecureContext && modChromiumMajor() >= MOD_LNA_WEBSOCKET_CHROMIUM;
}

// true when this page will trigger the Chromium local network permission prompt
function modNeedsLocalNetworkPermission() {
    return window.isSecureContext && modChromiumMajor() > 0;
}

// true when this is an https:// page in a browser that blocks ws:// from it (mixed
// content: Firefox throws on construction, Safari fails the connection asynchronously)
function modNeedsInsecureSite() {
    return window.location.protocol === 'https:' && modChromiumMajor() === 0;
}

// true for Safari on macOS, which also has a per-app "Local Network" switch since macOS 15
function modIsMacSafari() {
    var ua = navigator.userAgent;
    return /Macintosh/.test(ua) && /Safari\//.test(ua) && !/Chrome\//.test(ua) && !/Firefox\//.test(ua);
}

// Call first thing. Sends each browser family to the site it can use:
//  - Chromium on http:// -> https://, when the server says it exists
//  - everything else on https:// -> http:// (Safari and Chrome may auto-upgrade a typed
//    address to https, so this is the common way for Safari users to land here)
// Returns true when navigating away.
function modRedirectToSecureIfNeeded(httpsAvailable) {
    if (httpsAvailable && window.location.protocol === 'http:' && modBlockedByLocalNetworkAccess()) {
        window.location.replace(modSiblingUrl('https:'));
        return true;
    }
    if (modNeedsInsecureSite()) {
        // guard against a browser that upgrades the http:// URL straight back to https://
        var key = 'mod-insecure-redirect';
        var already = false;
        try { already = sessionStorage.getItem(key) === '1'; } catch (e) {}
        if (!already) {
            try { sessionStorage.setItem(key, '1'); } catch (e) {}
            window.location.replace(modSiblingUrl('http:'));
            return true;
        }
    }
    return false;
}

// Opens the unit websocket. Returns null when the browser refuses it up front,
// which is what Firefox and Safari do from an https:// page (mixed content).
function modOpenDeviceSocket() {
    try {
        return new WebSocket(MOD_DEVICE_WS_URL);
    } catch (e) {
        return null;
    }
}

// Explanation to show when the unit could not be reached.
// `refused` is true when modOpenDeviceSocket() returned null.
function modConnectFailureHint(refused) {
    if (refused || modNeedsInsecureSite()) {
        return 'Your browser does not let this https page talk to a MOD unit over USB. ' +
               'Use the http version of this page instead: ' + modLink('http:');
    }
    if (modBlockedByLocalNetworkAccess()) {
        return 'Chrome ' + MOD_LNA_WEBSOCKET_CHROMIUM + ' and newer block connections from http pages ' +
               'to devices on your local network, including MOD units over USB. ' +
               'Use the https version of this page instead: ' + modLink('https:');
    }
    var hint = 'Unable to connect to MOD unit, not plugged in to USB or running < ' + MOD_MIN_VERSION + '?';
    if (modNeedsLocalNetworkPermission()) {
        hint += '<br>If your browser asked for permission to access devices on your local network, allow it and press "Connect".';
    }
    if (modIsMacSafari()) {
        hint += '<br>On macOS 15 or newer, also check that Safari is allowed under ' +
                'System Settings &gt; Privacy &amp; Security &gt; Local Network, then press "Connect".';
    }
    return hint;
}

// Status text to show while the socket is still connecting after a short while,
// which on a secure page in Chromium means the permission prompt is up.
function modPendingStatus() {
    if (modNeedsLocalNetworkPermission()) {
        return 'Status: waiting for local network permission...';
    }
    return 'Status: connecting...';
}
