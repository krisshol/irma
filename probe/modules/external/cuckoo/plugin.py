#
# Copyright (c) 2013-2018 Quarkslab. This file is part of IRMA project.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License in the top-level directory
# of this distribution and at:
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# No part of the project, including this file, may be copied,
# modified, propagated, or distributed except according to the
# terms contained in the LICENSE file.

import os
import requests
import json
import time

from configparser import ConfigParser
from datetime import datetime

from irma.common.utils.utils import timestamp
from irma.common.plugins import PluginBase
from irma.common.plugins import FileDependency
from irma.common.plugins import ModuleDependency
from irma.common.plugin_result import PluginResult
from irma.common.base.utils import IrmaProbeType
from irma.common.plugins.exceptions import PluginLoadError


class CuckooPlugin(PluginBase):
    web_url = None
    api_url = None
    external_url = None
    HEADERS = None

    class Cuckoo:
        ERROR = -1
        FOUND = 1
        NOT_FOUND = 0

    # =================
    #  plugin metadata
    # =================
    _plugin_name_ = "Cuckoo"
    _plugin_display_name_ = "Cuckoo Sandbox"
    _plugin_author_ = "knaku"
    _plugin_version_ = "1.0.0"
    _plugin_category_ = "IrmaProbeType.external"
    _plugin_description_ = "Plugin to query Cuckoo Sandbox"
    _plugin_dependencies_ = [
        ModuleDependency(
            'requests',
            help='See requirements.txt for needed dependencies'
        ),
        FileDependency(
            os.path.join(os.path.dirname(__file__), 'config.ini'),
            help='Make sure to rename/copy and configure the config file to your IP:PORT'
        )
    ]

    # =============
    #  constructor
    # =============

    def __init__(self):

        # load default configuration file
        config = ConfigParser()
        config.read(os.path.join(os.path.dirname(__file__), 'config.ini'))

        # override default values if specified
        if self.web_url is None:
            self.web_url = config.get('Cuckoo', 'web_url')

        if self.api_url is None:
            self.api_url = config.get('Cuckoo', 'api_url')

        if self.external_url is None:
            self.external_url = config.get('Cuckoo', 'external_url')

        if self.HEADERS is None:
            self.HEADERS = config.get('Cuckoo', 'headers')

    # =============
    #  processor
    # =============

    def get_file_report(self, filename):
        # set API links
        unknown = False                                                     # signaling an unknown status
        task_running = True

        submit_task = self.api_url.strip("/") + '/tasks/create/file'
        get_report = self.api_url.strip("/") + '/tasks/report/'
        view_status = self.api_url.strip("/") + '/tasks/view/'

        HEADERS = {"Authorization": "Bearer S4MPL3"}                        # request Headers
        files = {"file": open(filename, 'rb')}                              # read passed file
        request = requests.post(submit_task, headers=HEADERS, files=files)  # submit a file for scanning
        task_id = request.json()["task_id"]
        web_report_url =
            '{external_url}/analysis/{task_id}/summary/'
        ).format(external_url=self.external_url.strip("/"), task_id=task_id)

        # Wait for tasks to finish
        while task_running:
            status = requests.get(view_status + str(task_id)).json()        # get status

            if status['task']['status'] == 'reported':
                task_running = False
                break
            elif status['task']['status'] not in ['pending', 'processing', 'finished', 'completed', 'running']:
                unknown = True
                task_running = False
                break

            if status['task']['status'] != 'reported':
                time.sleep(15)

        report = (requests.get(get_report + str(task_id) + "/json", headers=HEADERS))

        # if unknown status, set bogus response code
        if unknown == True:
            report = 999

        return report, web_report_url


    # ==================
    #  probe interfaces
    # ==================

    def run(self, paths):
        results = PluginResult(name=type(self).plugin_display_name,
                               type=type(self).plugin_category,
                               version=None)
        try:
            # get report and URL to Cuckoo
            started = timestamp(datetime.utcnow())
            response, url = self.get_file_report(paths)
            stopped = timestamp(datetime.utcnow())
            # check for if errors
                # Could not get response (JSON) to play along, score is stored in ['info']['score']
                # Implement logic for found/not found when able to retrive score?
            #if response == 200:
            #     results.status = self.Cuckoo.NOT_FOUND
            #elif 400 in response:
            #    results.status = self.Cuckoo.ERROR
            #    results.error = "Invalid report format"
            #elif 404 in response:
            #    results.status = self.Cuckoo.ERROR
            #    results.error = "Report not found"
            #elif 405 in response:
            #    results.status = self.Cuckoo.ERROR
            #    results.error = "Your not supposed to POST that"
            #elif 999 in response:
            #    results.status = self.Cuckoo.ERROR
            #    results.error = "That should not have happend, an unkown status was resturned"
            results.status = self.Cuckoo.FOUND      # Until better logic is implemented
            results.duration = stopped - started
            results.results = url
        except Exception as e:
            results.error = "An error occurred, Cuckoo might be unavailable"
            results.status = self.Cuckoo.ERROR
            results.results = str(e)
        return results
