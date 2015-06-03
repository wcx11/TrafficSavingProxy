#coding:utf-8
__author__ = 'wcx'

import BaseHTTPServer
import SimpleHTTPServer
import select
import socket
import SocketServer
import urlparse
import httplib
import StringIO
import sys
import os
import urllib2
from bs4 import BeautifulSoup
from bs4 import UnicodeDammit
import re
from cookielib import CookieJar
from PIL import Image
import StringIO
import cStringIO
import gzip


class ThreadingHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass


class ProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    __base = BaseHTTPServer.BaseHTTPRequestHandler
    __base_handle = __base.handle
    server_version = "HTTPProxy"

    # handle() is be calling in a new thread when a client is connected.
    def handle(self):
        print 'handle()'
        self.__base_handle()
        return

    def do_CONNECT(self):
        print 'do_CONNECT()'
        # HTTP Protocol CONNECT command
        self.log_request(200)
        self.wfile.write(self.protocol_version + " 200 Connection established\r\n")
        self.wfile.write("Proxy-agent: %s\r\n" % self.version_string())
        self.wfile.write("\r\n")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host, port = self.path.split(':')
        port = int(port)
        s.connect((host, port))
        self.turn_to(s, 900)
        s.close()
        self.connection.close()
        print 'a client is disconnected'

    # the most process in do_GET function
    def do_GET(self):
        print 'do_GET()'
        #netloc is a url like 'www.codepongo.com:80'
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
        if not netloc:
            netloc = self.headers.get('Host', "")
        if scheme != 'http' or not netloc or fragment:
            self.send_error(400, "bad url %s" % self.path)
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if -1 != netloc.find(':'):
            host, port = netloc.split(':')
            port = int(port)
        else:
            host = netloc
            port = 80
        print host, port
        self.headers['Connection'] = 'close'
        del self.headers['Proxy-Connection']
        #self.headers['User-Agent']='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.65 Safari/537.36'
        if self.headers.has_key('Accept-Encoding'):
            del self.headers['Accept-Encoding']

        req = urllib2.Request(url=self.path, headers=self.headers.dict)
        req.get_method = lambda: self.command
        #response = None
        try:
            response = urllib2.urlopen(req)
            self.send_GET_response(response, host, port, path)
        except urllib2.HTTPError, e:
            print e.code
            print e.msg
            print e.headers
            #response = e
            self.send_GET_response(e, host, port, path)
        except httplib.BadStatusLine, e:
            pass
        finally:
            self.connection.close()
            print 'a client is disconnected'

    def client_GET(self, url, headers):
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(url, 'http')
        if -1 != netloc.find(':'):
            host, port = netloc.split(':')
            port = int(port)
        else:
            host = netloc
            port = 80
        headers['Host'] = host

        req = urllib2.Request(url=url, headers=headers)
        req.get_method = lambda: self.command
        try:
            response = urllib2.urlopen(req, timeout=30)
            return response
        except urllib2.HTTPError, e:
            print e.code
            print e.msg
            print e.headers
            return e.fp

    def send_GET_response(self, response, host, port, path):
        print("send_GET_response()")
        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, response.code, response.msg))
        f = response.read()
        for header in response.info().headers:
            if re.search(r'chunked|length|Length|encoding', header):
                continue
            self.connection.send(header)
        if response.code != 200:
            self.connection.send('\r\n')
            self.connection.send(f)
            return

        if re.search(r'text', response.info().type):

            html_soup = BeautifulSoup(UnicodeDammit(f, ["utf-8", "windows-1252", "latin-1", "iso-8859-1"]).unicode_markup)
            #deal with javascript file
            scripts = html_soup.find_all('script', attrs={'src': re.compile(".*")})
            for script in scripts:
                script_url = self.get_absolute_url(script['src'], host, port, path)
                script_response = self.client_GET(script_url, self.headers.dict)
                print script_response.getcode()
                if script_response.getcode() != 200:
                    continue
                script_content = script_response.read()
                del script['src']
                #print script_content
                script.append(UnicodeDammit(script_content, ["utf-8", "windows-1252", "latin-1", "iso-8859-1"]).unicode_markup)
            #deal with css

            stylesheets = html_soup.find_all('link', attrs={'rel': 'stylesheet'})
            for stylesheet in stylesheets:
                stylesheet_url = self.get_absolute_url(stylesheet['href'], host, port, path)
                stylesheet_response = self.client_GET(stylesheet_url, self.headers.dict)
                if stylesheet_response.getcode() != 200:
                    continue
                stylesheet_content = stylesheet_response.read()
                new_tag = html_soup.new_tag('style')
                new_tag.append(UnicodeDammit(stylesheet_content, ["utf-8", "windows-1252", "latin-1", "iso-8859-1"]).unicode_markup)
                stylesheet.replace_with(new_tag)

            #print str(html_soup)
            f_in = str(html_soup)
            f_out = f_in
            buf = cStringIO.StringIO()
            try:
                gzipf = gzip.GzipFile(fileobj=buf, mode='wt', compresslevel=9)
                gzipf.write(f_in)
                gzipf.close()
                f_out = buf.getvalue()
                buf.close()
                print f_in
                print "compressed"
                print f_out
                self.connection.send('Content-Encoding: gzip\r\n')
            except Exception, e:
                print e
                pass
            finally:

                self.connection.send('\r\n')
                self.connection.send(f_out)

        #deal with image, convert into webp
        elif re.search(r'png|jpeg', response.info().type):
            try:
                image = Image.open(StringIO.StringIO(f)).convert('RGB')
                output = StringIO.StringIO()
                image.save(output, format="WEBP")
                contents = output.getvalue()
                print response.info().type
                self.connection.send('\r\n')
                self.connection.send(contents)
                output.close()
            except:
                self.connection.send('\r\n')
                self.connection.send(f)
        else:
            print response.info().type
            self.connection.send('\r\n')
            self.connection.send(f)


    def get_absolute_url(self, url, host, port, path):
        absolute_url = url
        pattern = re.compile(r'http://| https://')
        if re.match(pattern, url):
            pass
        elif re.match(r'//', url):
            absolute_url = "http:%s" % (url,)
        elif re.match(r'/', url):
            absolute_url = "http://%s:%d%s" % (host, port, url)
        else:
            paths = path.split('/')[1:-1]
            urls = url.split('/')[1:]
            absolute_url = "http://%s:%d" % (host, port)
            for p in paths:
                absolute_url += "/%s" % (p,)
            for u in urls:
                absolute_url += "/%s" % (u,)
        return absolute_url

    def do_POST(self):
        print 'do_POST()'
        #netloc is a url like 'www.codepongo.com:80'
        (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
        if not netloc:
            netloc = self.headers.get('Host', "")
        if scheme != 'http' or not netloc or fragment:
            self.send_error(400, "bad url %s" % self.path)
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if -1 != netloc.find(':'):
            host, port = netloc.split(':')
            port = int(port)
        else:
            host = netloc
            port = 80
        print host, port

        s.connect((host, port))
        self.log_request()
        # send HTTP Request HEADER
        s.send("%s %s %s\r\n" % (self.command, urlparse.urlunparse(('', '', path, params, query, '')), self.request_version))
        self.headers['Connection'] = 'close'
        del self.headers['Proxy-Connection']

        for key_val in self.headers.items():
            print key_val
            s.send("%s: %s\r\n" % key_val)
        s.send("\r\n")
        self.turn_to(s)
        s.close()
        self.connection.close()
        print 'a client is disconnected'


    do_HEAD = do_POST
    do_PUT  = do_POST
    do_DELETE=do_POST

    def turn_to(self, s, timeout = 60):
        #  client <-self.connection-> proxy <-s-> server
        # s 客户端与代理服务器的连接
        # self.connection 代理服务器与外部服务器之间的连接
        print("turn_to()")
        iw = [self.connection, s]
        ow = []
        time = 0
        while time < timeout:
            time += 1
            (ins, _, exs) = select.select(iw, ow, iw, 1)
            if exs: #exception
                for e in exs:
                    print "%s is exception" % (s.getpeername())
                break
            elif ins: #input readable
                for i in ins:
                    if i is s:
                        o = self.connection
                    elif i is self.connection:
                        o = s
                    else:
                        pass
                    data = i.recv(8192)
                    if data:
                        print 'recv length is', len(data)
                        print data
                        o.send(data)
                        time = 0
                    else:
                        pass
            else: # output readable
                pass


def serving(port=8000, protocol="HTTP/1.0", debug=False):
    httpHandler = urllib2.HTTPHandler(debuglevel=1)
    httpsHandler = urllib2.HTTPSHandler(debuglevel=1)
    cj = CookieJar()
    opener = urllib2.build_opener(httpHandler, httpsHandler, urllib2.HTTPCookieProcessor(cj))
    urllib2.install_opener(opener)

    host_port = ('', port)
    ThreadingHTTPServer.protocol_version = protocol
    httpd = ThreadingHTTPServer(host_port, ProxyHandler)
    print httpd.socket.getsockname()
    if not debug:
        buff = StringIO.StringIO()
        sys.stdout = buff
        sys.stderr = buff
    httpd.serve_forever()

if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding('utf8')
    serving(port=8000, debug=True)