#!/usr/bin/env python

import os
import json
from datetime import datetime
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase

class ResultCallback(CallbackBase):
    '''
    Custom callback module.
    '''
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'default'

    def __init__(self):
        super(ResultCallback, self).__init__()
        self.state = None
        self.start_time = datetime.now()

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.state = 'failed'
        self._display.display('failed', color='red')

    def v2_runner_on_ok(self, result):
        self.state = 'ok'
        self._display.display('ok', color='green')

    def v2_runner_on_skipped(self, result):
        self.state = 'skipped'

    def v2_runner_on_no_hosts(self, task):
        self._display.display('skipping: no hosts matched', color='blue')

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._display.display("TASK [%s]" % task.get_name().strip())

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        if not name:
            msg = "PLAY:"
        else:
            msg = "PLAY [{}]".format(name)
        self._display.display(msg)

#    def days_hours_minutes_seconds(self, runtime):
#        minutes = (runtime.seconds // 60) % 60
#        r_seconds = runtime.seconds - (minutes * 60)
#        return runtime.days, runtime.seconds // 3600, minutes, r_seconds
#
#    def playbook_on_stats(self, stats):
#        self.v2_playbook_on_stats(stats)
#
#    def v2_playbook_on_stats(self, stats):
#        end_time = datetime.now()
#        runtime = end_time - self.start_time
#        self._display.display("Playbook run took %s days, %s hours, %s minutes, %s seconds" % (self.days_hours_minutes_seconds(runtime)))


class Runner(object):
    
    def __init__(self, pb_file, sources=['inventory/hosts'], **kwargs):
        self.pb_file = pb_file
        self.sources = sources
        Options = namedtuple('Options', ['connection',
                                         'module_path',
                                         'forks',
                                         'become',
                                         'become_method',
                                         'become_user',
                                         'check',
                                         'diff'])
        # initialize needed objects
        self.Options = Options(connection='smart',
                               module_path=None,
                               forks=100,
                               become=True,
                               become_method='sudo',
                               become_user='root',
                               check=False,
                               diff=False)
        self.loader = DataLoader()
        passwords = dict(vault_pass='secret')

        # Instantiate our ResultCallback for handling results as they come in
        self.results_callback = ResultCallback()

        # create inventory and pass to var manager
        #self.inventory = InventoryManager(loader=loader, sources=['/home/alvin/git/ansible/ansible-playbook/inventory/hosts'])
        self.inventory = self._gen_inventory()
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)
        self.variable_manager.extra_vars = kwargs

        self.tqm = TaskQueueManager(
            inventory=self.inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.Options,
            passwords=passwords,
            stdout_callback=self.results_callback,
        )

    def _gen_inventory(self):
        if isinstance(self.sources, str):
            assert os.path.isfile(self.sources), "Inventory file ['{}'] not exist".format(self.sources)
            return InventoryManager(loader=self.loader, sources=self.sources)
        elif isinstance(self.sources, list):
            for source in self.sources:
                assert os.path.isfile(source), "One or more inventory file not exist in {}".format(self.sources)
            return InventoryManager(loader=self.loader, sources=self.sources)

    def _load_play_source(self):
        for source in self.loader.load_from_file(self.pb_file):
            self.play_source.update(source)

    def run(self):
        self.play_source = {}
        self._load_play_source()

        self.play = Play().load(self.play_source, variable_manager=self.variable_manager, loader=self.loader)

        try:
            ret = self.tqm.run(self.play)
            return ret
        finally:
            if self.tqm is not None:
                self.tqm.cleanup()
