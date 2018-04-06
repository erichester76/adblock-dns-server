#!/usr/bin/env python3

import sys
import time
import json
import redis
import pickle
import struct
import socket
import threading
import dns.rcode
import dns.flags
import dns.message
import dns.resolver
import socketserver
import dns.rdatatype
import dns.exception

allowed_rdtypes = [
  dns.rdatatype.A,
  dns.rdatatype.AAAA,
  dns.rdatatype.MX,
  dns.rdatatype.NS,
  dns.rdatatype.SOA,
  dns.rdatatype.SRV,
  dns.rdatatype.CNAME
]

def setup_nameservers():
  if 'nameservers' in config:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = config['nameservers']

def get_config(conf=None):
  if conf is None:
    config = {}
  else:
    with open(conf) as f:
      config = json.load(f)

  config['_policies'] = {}

  for entry in ['blacklist', 'whitelist']:
    if entry not in config:
      config[entry] = set()
    else:
      config[entry] = {i + '.' for i in config[entry]}

  if 'redis_socket_file' not in config:
    config['redis_socket_file'] = '/var/run/redis/redis.sock'

  if 'ratelimits' not in config:
    config['ratelimits'] = {}

  for entry, default in [('limit', 10), ('limit_burst', 2)]:
    if entry not in config['ratelimits']:
      config['ratelimits'][entry] = default

  return config

def is_blacklisted_host(host):
  while host:
    if host in config['blacklist']:
      return True

    if host in config['whitelist']:
      return False

    index = host.find('.')
    host = host[index + 1:]

  return False

def ratelimited(ip):
  if '.' in ip[-4:]: # IPv4
    ip = ip[ip.rfind(':') + 1:]
  else: # IPv6 /112 subnet
    ip = socket.inet_pton(socket.AF_INET6, ip)[:-2]

  limit = config['ratelimits']['limit']
  limit_burst = config['ratelimits']['limit_burst']
  ratio = limit/limit_burst

  key = 'dns:r:%s' % ip
  rl_params = redis_conn.get(key)
  current_time = time.time()

  if rl_params:
    access_time, tokens = pickle.loads(rl_params)
    tokens = min(limit, tokens + limit_burst * int(current_time - access_time))
  else:
    access_time, tokens = current_time, limit

  redis_conn.set(key, pickle.dumps((current_time, max(0, tokens - 1))))
  redis_conn.expire(key, int(ratio) + 1)
  return tokens < 1

def dns_query(name, rdtype):
  if not name.endswith('.'):
    return (dns.rcode.NXDOMAIN, [], [], [])

  try:
    key = 'dns:q:%s:%i' % (name, rdtype)
    cached_result = redis_conn.get(key)
    if cached_result is not None:
      return pickle.loads(cached_result)

    if is_blacklisted_host(name):
      raise dns.resolver.NXDOMAIN

    result = dns.resolver.query(name, rdtype, raise_on_no_answer=False)
    response = result.response
    rv = (response.rcode(), response.answer, response.authority, response.additional)
    expiration = max(300, int((time.time() - result.expiration)/3))
  except dns.exception.DNSException as e:
    expiration = 300
    if isinstance(e, dns.resolver.NXDOMAIN):
      rcode = dns.rcode.NXDOMAIN
    elif isinstance(e, dns.resolver.NoMetaqueries):
      rcode = dns.rcode.REFUSED
    else:
      rcode = dns.rcode.SERVFAIL
    rv = (rcode, [], [], [])

  redis_conn.set(key, pickle.dumps(rv))
  redis_conn.expire(key, expiration)
  return rv

def make_response(query):
  response = dns.message.Message(query.id)
  response.flags = dns.flags.QR | dns.flags.RA | (query.flags & dns.flags.RD)
  response.set_opcode(query.opcode())
  response.question = list(query.question)
  return response

def handle_query(raw_data, client_ip):
  try:
    query = dns.message.from_wire(raw_data)
  except dns.exception.DNSException:
    return

  if len(query.question) != 1:
    return

  rdtype = query.question[0].rdtype
  if rdtype not in allowed_rdtypes:
    return

  if ratelimited(client_ip):
    return

  name = str(query.question[0].name)
  result = dns_query(name, rdtype)
  response = make_response(query)
  response.set_rcode(result[0])
  response.answer = result[1]
  response.authority = result[2]
  response.additional = result[3]

  return response

class UDPHandler(socketserver.BaseRequestHandler):
  def handle(self):
    raw_data, socket = self.request
    response = handle_query(raw_data, self.client_address[0])

    if response is None:
      return

    raw_response = response.to_wire()
    if len(raw_response) > 512:
      response.flags |= dns.flags.TC

    socket.sendto(response.to_wire()[:512], self.client_address)

class TCPHandler(socketserver.BaseRequestHandler):
  def handle(self):
    socket = self.request

    try:
      query_length_bytes = socket.recv(2)
      query_length = struct.unpack('!H', query_length_bytes)
      raw_data = socket.recv(query_length[0])
      response = handle_query(raw_data, self.client_address[0])

      if response is not None:
        raw_response = response.to_wire()
        response_length_bytes = struct.pack('!H', len(raw_response))
        socket.send(response_length_bytes + raw_response)
    except (struct.error, OSError):
      pass
    finally:
      socket.close()

class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
  pass

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
  pass

def run_server():
  for server_class in [ThreadedUDPServer, ThreadedTCPServer]:
    server_class.allow_reuse_address = True
    server_class.address_family = socket.AF_INET6

  udp_server = ThreadedUDPServer(('', 5454), UDPHandler)
  tcp_server = ThreadedTCPServer(('', 5454), TCPHandler)
  udp_server_thread = threading.Thread(target=udp_server.serve_forever)
  tcp_server_thread = threading.Thread(target=tcp_server.serve_forever)
  try:
    for thread in [udp_server_thread, tcp_server_thread]:
      thread.start()

    for thread in [udp_server_thread, tcp_server_thread]:
      thread.join()
  except (KeyboardInterrupt, SystemExit):
    pass
  finally:
    for server in [udp_server, tcp_server]:
      server.shutdown()
      server.server_close()

if __name__ == '__main__':
  if len(sys.argv) < 2:
    config = get_config()
  else:
    config = get_config(sys.argv[1])

  redis_conn = redis.StrictRedis(unix_socket_path=config['redis_socket_file'])
  setup_nameservers()
  run_server()
