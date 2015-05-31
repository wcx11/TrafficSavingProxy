__author__ = 'wcx'
import sys
import getopt
import urllib2
from bs4 import BeautifulSoup


def get_top_sites(original, num, c):
    output = open('top_global_sites','w')
    for i in range(num):
        httpHandler = urllib2.HTTPHandler(debuglevel=1)
        httpsHandler = urllib2.HTTPSHandler(debuglevel=1)
        opener = urllib2.build_opener(httpHandler, httpsHandler)
        urllib2.install_opener(opener)
        if c != 'global':
            response = urllib2.urlopen(original+";"+str(i)+'/'+c)
        else:
            response = urllib2.urlopen(original+";"+str(i))
        html = response.read()
        html_soup = BeautifulSoup(html)
        sites = html_soup.find_all('p', attrs={'class': 'desc-paragraph'})
        for site in sites:
            output.write("%s\r\n" % (site.a.string,))
    output.close()



def usage():
    usage = '''usage:
%s [-n|--num = numofpages / 25]
''' % (sys.argv[0]) + ' ' * len(sys.argv[0]) + ' [-h|--help]'
    print usage
    sys.exit(0)


if __name__ == '__main__':
    num = 4
    original = ''
    opts, args = getopt.getopt(sys.argv[1:], 'n:h', ['num=', 'help'])
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        if o in ('-n', '--num'):
            num = a
    if len(args) == 1:
        original = "http://www.alexa.com/topsites/countries"
        get_top_sites(original, num, args[0])
    else:
        original = "http://www.alexa.com/topsites/global"
        get_top_sites(original, num, 'global')