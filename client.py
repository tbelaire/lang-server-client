#!/usr/bin/env python3
import json
import os
import re
import subprocess
import threading
import time

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

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
            close_fds=True,  # Possibly only useful on Posix
            universal_newlines=True)

        self.response_queue = Queue()
        self.notification_queue = Queue()
        self.io_thread = threading.Thread(
            target=self.response_handler)

        self.io_thread.daemon = True # thread dies with the program
        self.io_thread.start()

        self.header_regex = re.compile("(?P<header>(\w|-)+): (?P<value>\d+)")
        # The first unused id.  Incremented with every request.
        self.next_id = 1

        self.in_flight_ids = set()

    def response_handler(self):
        while True:
            response = self.read_response()
            if response == None:
                break
            elif response.get("id") != None:
                assert response["id"] in self.in_flight_ids
                # We know this is a response to a request we sent
                self.in_flight_ids.remove(response["id"])
                self.response_queue.put(response)
            else:
                # It's a notification
                self.notification_queue.put(response)

    def read_headers(self):
        """Reads in the headers for a response"""
        result = {}
        while True:
            line = self.server.stdout.readline()
            if line == "\n":
                break
            m = self.header_regex.match(line)
            if m:
                result[m.group("header")] = m.group("value")
            else:
                break
        return result

    def read_response(self):
        headers = self.read_headers()
        if "Content-Length" not in headers:
            return None
        size = int(headers["Content-Length"])
        content = self.server.stdout.read(size)
        return json.loads(content)

    def _format_request(self, request):
        """Converts the request into json and adds the Content-Length header"""
        content = json.dumps(request, indent=2)
        content_length = len(content)

        result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
        return result

    def request(self, method, **params):
        # TODO(tbelaire) more methods.
        assert method in ["initialize", "shutdown", "exit"]
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": method,
            "params": params,
        }
        self.in_flight_ids.add(self.next_id)
        self.next_id += 1
        formatted_req = self._format_request(request)
        # TODO(tbelaire) log
        self.server.stdin.write(formatted_req)
        self.server.stdin.flush()

    def initialize(self):
        self.request("initialize",
                     processId=os.getpid(),
                     rootPath=config.project_dir,
                     capabilities={})
        response = self.response_queue.get(True)
        return response

    def shutdown(self):
        self.request("shutdown")
        response = self.response_queue.get(True)
        self.request("exit")
        self.server.wait()
        assert self.server.returncode == 0
        return response










rls = LangServer()


print("Response:")
response = rls.initialize()
print(json.dumps(response, indent=2))

print("Notification:")
response = rls.notification_queue.get(True)
print(json.dumps(response, indent=2))

time.sleep(1)
rls.shutdown()
time.sleep(1)
while True:
    any_non_empty = False
    try:
        response = rls.response_queue.get_nowait()
        print("Response:")
        print(json.dumps(response, indent=2))
        any_non_empty = True
    except Empty:
        pass

    try:
        notification = rls.notification_queue.get_nowait()
        print("Notification:")
        print(json.dumps(notification, indent=2))
        any_non_empty = True
    except Empty:
        pass

    if not any_non_empty:
        break



print("Done")
