#!/usr/bin/env python
# -*- coding: utf8 -*-

from resources import FileResource
from processors import *
from process import Process
from tuttle.resources import HTTPResource


class WorkflowBuilder():
    """A helper class to build Process classes from the name of processors and resources"""
    
    def __init__(self):
        self._resources_definition = {}
        self._processors = {}
        self.init_resources_and_processors()

    def init_resources_and_processors(self):
        self._resources_definition['file'] = FileResource
        self._resources_definition['http'] = HTTPResource
        self._processors['shell'] = ShellProcessor()
        self._processors['bat'] = BatProcessor()
        self._processors['download'] = DownloadProcessor()
        self._processors['default'] = self._processors['bat']

    def extract_scheme(self, url):
        """Extract the scheme from an url
        url is supposed to be stripped from spaces
        """
        separator_pos = url.find('://')
        if separator_pos == -1:
            return False
        url_scheme = url[:separator_pos]
        return url_scheme

    def build_resource(self, url):
        scheme = self.extract_scheme(url)
        if scheme is False or scheme not in self._resources_definition:
            return None
        ResDefClass = self._resources_definition[scheme]
        return ResDefClass(url)
    
    def build_process(self, line_num, processor="default"):
        if processor in self._processors:
            return Process(self._processors[processor], line_num)
        else:
            return False

    def get_or_build_resource(self, url, resources):
        if url not in resources:
            resource = self.build_resource(url)
            resources[url] = resource
        else:
            resource = resources[url]
        return resource
