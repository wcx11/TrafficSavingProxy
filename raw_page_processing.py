__author__ = 'wcx'
import matplotlib.pyplot
import os

def visit_dir(rootDir):
    file_paths = []
    for lists in os.listdir(rootDir):
        path = os.path.join(rootDir, lists)
        print path
        file_paths.append(path)
    return file_paths


if __name__ == '__main__':
    rootDir = '/Users/wcx/Documents/raw_pages'
    top_50 = []
    file_paths = visit_dir(rootDir)
    for file_path in file_paths:
        f = file(file_path)
        f_content = eval(f.read())
        entries = f_content['entries']
        header_size = 0
        total_size = 0
        js_css_size = 0
        html_size = 0
        pic_size = 0
        for entry in entries:
            header_size += len(str(entry['request']))

