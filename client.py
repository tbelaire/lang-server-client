#!/usr/bin/env python3
import json
import subprocess
import os
import re

# Local config options
import config

class LangServer:
    def __init__(self):
        self.server = subprocess.Popen(
            [config.cargo_path, "run", "-q"],
            env={ "RUST_BACKTRACE": "1",
                 "SYS_ROOT": config.sys_root,
                 "TMPDIR": config.tmpdir },
            cwd=config.rustls_dir,
            bufsize=0,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True)

        self.header_regex = re.compile("(?P<header>(\w|-)+): (?P<value>\d+)")
        # The first unused id.  Incremented with every request.
        self.next_id = 1


    def read_headers(self):
        """Reads in the headers for a response"""
        result = {}
        while True:
            line = self.server.stdout.readline()
            if line == "\n":
                break
            m = self.header_regex.match(line)
            result[m.group("header")] = m.group("value")
        return result

    def read_response(self):
        headers = self.read_headers()
        size = int(headers["Content-Length"])
        content = self.server.stdout.read(size)
        return json.loads(content)

    def format_request(self, request):
        content = json.dumps(request, indent=2)
        content_length = len(content)

        result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
        return result

    def request(self, method, **params):
        # TODO(tbelaire) more methods.
        assert method in ["initialize"]
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": method,
            "params": params,
        }
        self.next_id += 1
        formatted_req = self.format_request(request)
        # TODO(tbelaire) log
        self.server.stdin.write(formatted_req)
        self.server.stdin.flush()

    def initialize(self):
        self.request("initialize", 
                     processId=os.getpid(),
                     rootPath=config.project_dir,
                     capabilities={})








rls = LangServer()


rls.initialize()

if rls.server.poll() != None:
    print("Exited!")

print("Response:")
response = rls.read_response()
print(json.dumps(response, indent=2))
print("Response:")
response = rls.read_response()
print(json.dumps(response, indent=2))


print("Done")
