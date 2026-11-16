from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        if '/releases/tags/' in path:
            return 'application/json'
        return super().guess_type(path)

HTTPServer(('127.0.0.1', 18765), partial(Handler, directory='/home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/herdr-fixture-5')).serve_forever()
