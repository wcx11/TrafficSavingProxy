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
from slimit import minify
from PIL import Image
import StringIO
import cStringIO
import gzip
import cgi
from urlparse import parse_qs

class ThreadingHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    pass

#class NoRedirection(urllib2.HTTPErrorProcessor):
#    def http_response(self, request, response):
#        return response
#    https_response = http_response

class ProxyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    __base = BaseHTTPServer.BaseHTTPRequestHandler
    __base_handle = __base.handle
    server_version = "HTTPProxy"

    # handle() is be calling in a new thread when a client is connected.
    def handle(self):
        print 'handle()'
        self.__base_handle()
        return
    def _connect_to(self, netloc, soc):
        i = netloc.find(':')
        if i >= 0:
            host_port = netloc[:i], int(netloc[i+1:])
        else:
            host_port = netloc, 80
        print "\t" "connect to %s:%d" % host_port
        try: soc.connect(host_port)
        except socket.error, arg:
            try: msg = arg[1]
            except: msg = arg
            self.send_error(404, msg)
            return 0
        return 1

    def do_CONNECT(self):
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(self.path, soc):
                print 'connect done'
                self.log_request(200)
                self.wfile.write(self.protocol_version +
                                 " 200 Connection established\r\n")
                self.wfile.write("Proxy-agent: %s\r\n" % self.version_string())
                self.wfile.write("\r\n")
                #self._read_write(soc, 300)
                self.turn_to(soc)
        except Exception, e:
            print e
        finally:
            print "\t" "bye"
            soc.close()
            self.connection.close()


    '''def do_CONNECT(self):
        print 'do_CONNECT()'
        # HTTP Protocol CONNECT command
        self.log_request(200)
        self.wfile.write(self.protocol_version + " 200 Connection established\r\n")
        #self.wfile.write("Proxy-agent: %s\r\n" % "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36")
        self.wfile.write("\r\n")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host, port = self.path.split(':')
        port = int(port)
        s.connect((host, port))
        print 'connectdone'
        self.turn_to(s, 900)
        s.close()
        self.connection.close()
        print 'a client is disconnected'
    '''
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
            response = urllib2.urlopen(req, timeout=10)
            self.send_GET_response(response, host, port, path)
        except urllib2.HTTPError, e:
            print e.code
            print e.msg
            print e.headers
            #response = e
            self.send_GET_response(e, host, port, path)
        except httplib.BadStatusLine, e:
            pass
        except Exception, e:
            print e
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
        headers['host'] = host

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

        if re.search(r'text/html', response.info().type):

            html_soup = BeautifulSoup(UnicodeDammit(f, ["utf-8", "windows-1252", "latin-1", "iso-8859-1"]).unicode_markup)
            #deal with javascript file
            scripts = html_soup.find_all('script', attrs={'src': re.compile(".*")})
            stylesheets = html_soup.find_all('link', attrs={'rel': 'stylesheet', 'href': re.compile(".*")})
            for script in scripts:
                script_url = self.get_absolute_url(script['src'], host, port, path)
                script_response = self.client_GET(script_url, self.headers.dict)
                print script_response.getcode()
                if script_response.getcode() != 200:
                    continue
                script_content = script_response.read()
                '''try:
                    script_content = minify(script_content, mangle=True, mangle_toplevel=True)
                except:
                    continue
                '''
                del script['src']
                #print script_content
                script.insert(0, '\r\n   ')
                script.append(UnicodeDammit(script_content, ["utf-8", "windows-1252", "GB18030","latin-1", "iso-8859-1"]).unicode_markup)
                script.append('\r\n')

            #deal with css
            for stylesheet in stylesheets:
                stylesheet_url = self.get_absolute_url(stylesheet['href'], host, port, path)
                stylesheet_response = self.client_GET(stylesheet_url, self.headers.dict)
                if stylesheet_response.getcode() != 200:
                    continue
                stylesheet_content = stylesheet_response.read()
                #self.stylesheet_url = stylesheet_url
                (s_scheme, s_netloc, s_path, s_params, s_query, s_fragment) = urlparse.urlparse(stylesheet_url, 'http')
                if -1 != s_netloc.find(':'):
                    s_host, s_port = s_netloc.split(':')
                    s_port = int(port)
                else:
                    s_host = s_netloc
                    s_port = 80
                stylesheet_content = re.sub(r'url\(.*?\)', lambda m: self.change_style_url(m, s_host, s_port, s_path), stylesheet_content, flags=re.IGNORECASE)

                new_tag = html_soup.new_tag('style')
                new_tag.append(UnicodeDammit(stylesheet_content, ["utf-8", "windows-1252", "GB18030","latin-1", "iso-8859-1"]).unicode_markup)
                #stylesheet.insert(0, new_tag)
                html_soup.head.append(new_tag)
                del stylesheet['href']
                #stylesheet.replace_with(stylesheet.contents)

            #print str(html_soup)
            f_in = str(html_soup)
            #f_in = html_soup.prettify()
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
                print(f_out)

        #deal with image, convert into webp
        elif re.search(r'png|jpeg|gif', response.info().type):
            try:
                if re.search(r'jpeg', response.info().type):
                    image = Image.open(StringIO.StringIO(f)).convert('RGB')
                else:
                    image = Image.open(StringIO.StringIO(f)).convert('RGB')
                output = StringIO.StringIO()
                image.save(output, format="WEBP")
                contents = output.getvalue()
                print response.info().type
                self.connection.send('\r\n')
                self.connection.send(contents)
                output.close()
            except Exception, e:
                self.connection.send('\r\n')
                self.connection.send(f)
        elif re.search(r'text|javascript|stylesheet|html', response.info().type):
            f_in = f
            #f_in = html_soup.prettify()
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
                print(f_out)
        else:
            print response.info().type
            self.connection.send('\r\n')
            self.connection.send(f)
    def change_style_url(self, m, host, port, path):
        if re.match(r'url\(\s*(\'|\"|)data', m.group(), re.IGNORECASE):
            return m.group()
        else:
            url = re.search(r'url\((\'|\"|)(.*?)(\'|\"|)\)', m.group()).group(2)
            return 'url('+self.get_absolute_url(url, host, port, path)+')'

    def get_absolute_url(self, url, host, port, path):
        absolute_url = url
        pattern = re.compile(r'http://|https://')
        if re.match(pattern, url):
            pass
        elif re.match(r'//', url):
            absolute_url = "http:%s" % (url,)
        elif re.match(r'/', url):
            absolute_url = "http://%s:%d%s" % (host, port, url)
        else:
            paths = path.split('/')[1:-1]
            urls = url.split('/')[0:]
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
        '''form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })'''
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
        ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
        if ctype == 'multipart/form-data':
            postvars = cgi.parse_multipart(self.rfile, pdict)
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers.getheader('content-length'))
            post_body = self.rfile.read(length)
            s.send(post_body)
            postvars = cgi.parse_qs(post_body, keep_blank_values=1)
        else:
            postvars = {}
        self.turn_to(s)
        s.close()
        self.connection.close()
        print 'a client is disconnected'


    do_HEAD = do_POST
    do_PUT  = do_POST
    do_DELETE=do_POST

    def turn_to(self, s, timeout = 160):
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
    #opener = urllib2.build_opener(NoRedirection, urllib2.HTTPCookieProcessor(cj))
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