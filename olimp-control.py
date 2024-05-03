#!/usr/bin/env python3

import argparse
import hashlib
import hmac
import json
import requests
import requests.adapters
import signal
import subprocess
import threading
import time

class LmioCtrlApi:
    _AUTH_HEADER = 'X-lmio-auth'
    _FAILED_AUTH = 'Response failed authentication validation'
    _NO_TICKETS = 'No tickets available'

    def __init__(self, url, key, mid, timeout):
        self._url = url
        self._key = key.encode('utf-8')
        self._mid = mid
        self._timeout = timeout if timeout > 0.0 else None

    def _get_body_hmac(self, body):
        return hmac.HMAC(self._key, body, 'sha1').hexdigest()

    def _get_basic_payload(self):
        return {
            'timestamp': int(time.time()*1000),
            'mid': self._mid
        }

    def _get_auth_headers(self, body):
        return {
           self._AUTH_HEADER: self._get_body_hmac(body.encode('utf-8'))
        }

    def _validate_response(self, body, timestamp, headers):
        try:
            signature = self._get_body_hmac(body)
            if signature != headers[self._AUTH_HEADER]:
                return False

            body_json = json.loads(body.decode('utf-8'))
            if body_json['timestamp'] != timestamp:
                return False

            return True
        except Exception as e:
            return False

    def get_session(self):
        session = requests.Session()
        retry = requests.adapters.Retry(connect=5, backoff_factor=0.5)
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def do_ping(self, session):
        payload = self._get_basic_payload()
        payload['uptime'] = subprocess.check_output(["uptime"]).decode('utf-8').strip()
        payload['hasRoot'] = 0
        post_data = json.dumps(payload)
        headers = self._get_auth_headers(post_data)

        try:
            r = session.post(self._url + '/ping', data=post_data, headers=headers, timeout=self._timeout)
            if self._validate_response(r.content, payload['timestamp'], r.headers):
                response = r.json()
                print(response['status'], response['message'])
            else:
                print(self._FAILED_AUTH)
                print(r.content)
        except Exception as e:
            print(e)

    def do_get_ticket(self, session):
        payload = self._get_basic_payload()
        get_data = json.dumps(payload)
        headers = self._get_auth_headers(get_data)

        try:
            r = session.get(self._url + '/ticket', data=get_data, headers=headers, timeout=self._timeout)
            if self._validate_response(r.content, payload['timestamp'], r.headers):
                if r.status_code != 404:
                    response = r.json()
                    print(response['status'], response['message'])
                    if r.status_code == 200:
                        return {
                            'tid': response['tid'],
                            'cmd': response['cmd'],
                            'runAs': response['runAs']
                        }
                else:
                    print(self._NO_TICKETS)
            else:
                print(self._FAILED_AUTH)
                print(r.content)
        except Exception as e:
            print(e)

        return {}

    def do_post_ticket_results(self, session, results):
        payload = self._get_basic_payload()
        payload['tid'] = results['tid']
        payload['exectime'] = results['exectime']
        payload['stdout'] = results['stdout'].decode('utf-8')
        payload['stderr'] = results['stderr'].decode('utf-8')
        payload['exitcode'] = results['exitcode']
        post_data = json.dumps(payload)
        headers = self._get_auth_headers(post_data)

        try:
            r = session.post(self._url + '/ticket', data=post_data, headers=headers, timeout=self._timeout)
            if self._validate_response(r.content, payload['timestamp'], r.headers):
                response = r.json()
                print(response['status'], response['message'])
            else:
                print(self._FAILED_AUTH)
                print(r.content)
        except Exception as e:
            print(e)


def execute_ticket(ticket):
    start_stamp = time.time()
    p = subprocess.Popen(['/bin/su', ticket['runAs'], '-c', '/bin/bash'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_data, stderr_data = p.communicate(input=ticket['cmd'].encode('utf-8'))
    exectime = time.time() - start_stamp
    return {
        'tid': ticket['tid'],
        'exectime': exectime,
        'stdout': stdout_data,
        'stderr': stderr_data,
        'exitcode': p.returncode
    }

def get_key(key_file):
    return open(key_file).read().strip()

def get_machine_id():
    all_macs = subprocess.check_output("cat /sys/class/net/*/address | sort", shell=True)
    return hashlib.sha1(all_macs).hexdigest()

def main_loop(url, key, mid, poll_frequency, timeout, exit_event):
    api = LmioCtrlApi(url, key, mid, timeout)
    while True:
        session = api.get_session()
        api.do_ping(session)
        ticket = api.do_get_ticket(session)
        if ticket:
            ticket_results = execute_ticket(ticket)
            api.do_post_ticket_results(session, ticket_results)

        wait_result = exit_event.wait(poll_frequency)
        if wait_result:
            break

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='olimp-control client')
    parser.add_argument('-f', '--poll-frequency', default=60.0, type=float,
        help='frequency of server check-in, in seconds')
    parser.add_argument('-k', '--key-file', default='/etc/olimp-control/key', help='path to key file')
    parser.add_argument('-t', '--timeout', default=20.0, type=float, help='timeout for API operations, in seconds')
    parser.add_argument('url', nargs='?', default='https://ctrl.lmio.lt/olimp/api',
        help='url of control api base')

    args = parser.parse_args()
    if args.url[-1] == '/':
        args.url = args.url[:-1]

    shutdown_event = threading.Event()
    sigterm_handler = lambda sig, stack: shutdown_event.set()

    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    main_loop(args.url, get_key(args.key_file), get_machine_id(), args.poll_frequency, args.timeout, shutdown_event)
