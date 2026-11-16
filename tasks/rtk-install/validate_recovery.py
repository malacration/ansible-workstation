#!/usr/bin/env python3
"""Exercise full-role recovery only inside the existing guarded fixture HOME."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import shlex
import stat
import threading

import validate_ansible as validation

ROLE = Path(__file__).resolve().parents[2] / 'ai/roles/rtk'
SPEC = importlib.util.spec_from_file_location('installed_state', ROLE / 'files/installed_state.py')
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)
EVIDENCE = []


def verified():
    state = STATE.inspect(validation.BINARY.parents[1], 'x86_64')
    assert state['valid'], state
    return state


@contextmanager
def cached_release_server():
    """Serve retained, digest-verified official artifacts only on localhost.

    This is an isolated download fixture, not a proxy for any agent traffic.
    Recovery tests need no live GitHub API quota or authentication.
    """
    task = Path(__file__).resolve().parent
    release_bytes = (task / 'UPSTREAM_RELEASE.json').read_bytes()
    release = json.loads(release_bytes)
    routes = {'/releases/tags/v1.2.0': release_bytes, '/releases/latest': release_bytes}
    for filename in ['checksums.txt', 'rtk-oss-x86_64-unknown-linux-musl.tar.gz']:
        data = (task / filename).read_bytes()
        asset = next(asset for asset in release['assets'] if asset['name'] == filename)
        assert asset['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
        routes['/download/v1.2.0/' + filename] = data
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            data = routes.get(self.path)
            self.send_response(200 if data is not None else 404)
            self.send_header('Content-Type', 'application/json' if self.path.startswith('/releases/') else 'application/octet-stream')
            self.end_headers()
            if data is not None:
                self.wfile.write(data)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = 'http://127.0.0.1:' + str(server.server_port)
        yield {'rtk_release_api': base + '/releases',
               'rtk_release_download_url': base + '/download'}, requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def main(variables, requests):
    def run(name, **kwargs):
        validation.run(name, variables=variables, **kwargs)

    home = validation.HOME
    assert home == Path(__file__).resolve().parent / 'ansible-home'
    assert home != Path.home()
    run('recovery-bootstrap')
    verified()
    run('recovery-initial-idempotence', unchanged=True)
    binary = validation.BINARY
    receipt = binary.parents[1] / 'release.json'
    marker = home / 'unexpected-round2-execution'
    assert not marker.exists()
    altered = ('#!/bin/sh\nprintf executed > ' + shlex.quote(str(marker))
               + '\nprintf "rtk 1.2.0\\n"\n').encode()
    expected_hash = hashlib.sha256(binary.read_bytes()).hexdigest()

    # An altered executable must neither run nor be replaced during check mode;
    # the ordinary run must replace it from the verified archive before any init.
    binary.write_bytes(altered)
    run('recovery-mismatch-check', options=['--check'])
    assert binary.read_bytes() == altered and not marker.exists()
    EVIDENCE.append({'case': 'mismatch-check', 'marker_written': marker.exists(), 'original_preserved': True})
    run('recovery-mismatch-normal')
    assert verified()['receipt']['binary_sha256'] == expected_hash and not marker.exists()
    EVIDENCE.append({'case': 'mismatch-normal', 'marker_written': marker.exists(), 'verified_replacement': True})

    # A same-version symlink target is never executed or changed. The link itself
    # is renamed out of the publication path without following or reading it.
    target = home / 'previous-round2-binary'
    target.write_bytes(altered)
    target.chmod(0o755)
    binary.unlink()
    binary.symlink_to(target)
    run('recovery-symlink-check', options=['--check'])
    assert binary.is_symlink() and target.read_bytes() == altered and not marker.exists()
    EVIDENCE.append({'case': 'symlink-check', 'marker_written': marker.exists(), 'target_unchanged': True})
    run('recovery-symlink-normal')
    assert verified()['valid'] and not binary.is_symlink() and not marker.exists()
    assert target.read_bytes() == altered
    assert any(p.is_symlink() for p in binary.parent.glob('rtk.rtk-invalid-*'))
    EVIDENCE.append({'case': 'symlink-normal', 'marker_written': marker.exists(),
                     'target_unchanged': True, 'link_preserved': True})

    # Nonregular destinations are preserved as objects rather than recursively
    # removed, read by backup, or used as copy's directory destination.
    binary.unlink()
    binary.mkdir()
    (binary / 'retained.txt').write_text('preserve fixture content')
    run('recovery-directory-check', options=['--check'])
    assert binary.is_dir()
    run('recovery-directory-normal')
    assert stat.S_ISREG(binary.lstat().st_mode) and verified()['valid']
    assert any((p / 'retained.txt').exists() for p in binary.parent.glob('rtk.rtk-invalid-*') if p.is_dir())
    EVIDENCE.append({'case': 'directory-normal', 'verified_replacement': True, 'directory_preserved': True})

    receipt.write_text('not valid JSON')
    run('recovery-malformed-receipt-check', options=['--check'])
    assert receipt.read_text() == 'not valid JSON'
    run('recovery-malformed-receipt-normal')
    assert verified()['valid'] and not marker.exists()
    EVIDENCE.append({'case': 'malformed-receipt-normal', 'verified_replacement': True})
    run('recovery-final-idempotence', unchanged=True)
    run('recovery-final-check', options=['--check'], unchanged=True)
    (validation.TASK / 'RECOVERY_RESULTS.json').write_text(
        json.dumps({'assertions': EVIDENCE, 'ansible': validation.RESULTS,
                    'cached_official_fixture_requests': requests}, indent=2) + '\n')
    print('Full-role recovery checks passed without executing an invalid binary.', flush=True)


if __name__ == '__main__':
    with cached_release_server() as (fixture_variables, fixture_requests):
        main(fixture_variables, fixture_requests)
