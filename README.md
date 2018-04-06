# simple-dns-server

A simple DNS server using [dnspython](https://github.com/rthalley/dnspython)
and [socketserver](https://docs.python.org/3/library/socketserver.html).

This server has been written keeping personal usage in mind, and has features
such as JSON-based configuration and an easy way to blacklist websites. In
addition, the server will send out no responses in case an "uncommon" query
(such as ANY) is found. These query types should not be necessary for personal
use and allows lessening of the impacts of amplification attacks.

## Usage

The server requires Python3 and Redis to run. These instructions are for
Ubuntu, although it can be run on any distribution.

* Install the dependencies:

```
$ sudo apt install virtualenv python3 python3-dev redis-server
```

* Configure Redis to use a file socket. If you don't need Redis for anything
else, you can also disable it from using TCP ports. The command below does
these two things mentioned above:

```
$ sed -ri 's/^bind /#&/;s/^(port ).*$/\\10/;s/^# (unixsocket)/\\1/;s/^(unixsocketperm )[0-9]+/\\1777/' /etc/redis/redis.conf
```

* Clone and enter into the repository directory:

```
$ git clone https://github.com/supriyo-biswas/simple-dns-server
$ cd simple-dns-server
```

* Create a virtualenv for this project, and install the dependencies:

```
$ virtualenv -p python3 venv
$ . venv/bin/activate
$ pip install git+https://github.com/rthalley/dnspython@master
$ pip install redis idna hiredis
```

* Run the server:

```
$ ./server.py
```

## Configuration

You can run the server with a JSON configuration file, as follows:

```
$ ./server.py /path/to/config.json
```

The following settings can be configured. All of these have reasonable
defaults.

```js
{
  // The DNS server to which we should send queries to
  "nameservers": ["1.1.1.1", "1.0.0.1"],
  // Any websites to blacklist. Blocking 'example.com' also blocks
  // 'www.example.com', 'foo.example.com' and so on. You can also block entire
  // TLDs by specifying the TLD name, for example, 'cn'.
  "blacklist": ["example.com", "cn"],
  // A whitelist. Whitelisting 'example.com' also whitelists 'www.example.com'
  "whitelist": ["foo.example.com"],
  // Path to the redis socket file.
  "redis_socket_file": "/tmp/redis.sock",
  // Ratelimits (per second) to place on IPs querying the DNS server.
  "ratelimits": {"limit": 10, "limit_burst": 2}
}
```

## License

Copyright 2018 Supriyo Biswas

Permission is hereby granted, free of charge, to any person obtaining a copy 
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
