#!/usr/bin/env python

from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.parsing.ajson import AnsibleJSONDecoder
from collections import namedtuple
import os
import getpass
import sys
import logging
import argparse
import datetime
import jinja2
from tempfile import NamedTemporaryFile
from ansible.plugins.callback import CallbackBase
import json

logger = logging.getLogger(__name__)

# Parser for command-line arguments.
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter
)

parser.add_argument(
    '--key-name',
    default=getpass.getuser(),
    help='The name of your key in the file containing all keys'
)

parser.add_argument(
    '--project',
    default=None,
    help='Sync a particular project'
)
parser.add_argument(
    '--acl',
    default=os.path.join(os.getcwd(), 'acl.yml'),
    help='Name of the file containing all access informations'
)

parser.add_argument(
    '--keys',
    default=os.path.join(os.getcwd(), 'keys.yml'),
    help='Name of the file containing all keys'
)

parser.add_argument(
    '--logging-level',
    default='INFO'
)

parser.add_argument(
    '--dry-run',
    dest='dry_run',
    action="store_true",
    default=False
)

parser.add_argument(
    '--private-key',
    dest='private_key'
)

parser.add_argument(
    '--list-keys',
    dest='list_keys',
    action='store_true',
    default=False
)


# The unix user (e.g. www-data, operator)
# not the Theodoer user !
class User:
    def __init__(self, name, acl):
        self.name = name
        self.acl = acl

    def is_sudoer(self):
        if 'sudoer' in self.acl:
            return self.acl['sudoer']
        else:
            return False

    def is_authorized(self, keyname):
        return keyname in self.acl['authorized_keys']


class Project:
    def __init__(self, project_yaml):
        self.name = project_yaml['name']
        self.servers = project_yaml['servers']
        self.users = []
        for username, useracl in project_yaml['users'].items():
            self.users.append(User(username, useracl))

    def get_sudoer_account(self, keyname):
        for user in self.users:
            if user.is_sudoer() and user.is_authorized(keyname):
                return user
        return None


def get_project_play(project, keys, keyname, dry_run):
    sudoer_account = project.get_sudoer_account(keyname)

    logger.info('Syncing "' + project.name + '" using key "' + keyname + '"')
    plays = []

    for user in project.users:
        if user.is_authorized(keyname):
            # we have direct access to this user, no need to use sudo
            remote_user = user.name
            use_sudo = False
        elif sudoer_account:
            logger.info('sudoer "' + sudoer_account.name + '"')
            # we are allowed to update this user through the sudo user
            remote_user = sudoer_account.name
            use_sudo = True
        else:
            # we skip since we are not authorized to update this user
            continue

        # if we are authorized, let us update this user's keys
        authorized_key_names = []
        expired_key_names = []
        for key_name in user.acl['authorized_keys']:
            if key_name not in keys:
                logger.error(key_name + ' missing from keys file')
                expired_key_names.append(key_name)
                continue

            if not keys[key_name]['expires'] or keys[key_name]['expires'] > datetime.datetime.now().date():
                authorized_key_names.append(key_name)
            else:
                expired_key_names.append(key_name)

        play = dict(
            name="Key setting for " + user.name + " on " + project.name,
            hosts=project.name,
            gather_facts='no',
            tasks=[],
            remote_user=remote_user,
        )
        if use_sudo:
            play["become"] = True
        if len(expired_key_names) > 0:
            expired_keys = [keys[key_name]['key'] + ' ' + key_name for key_name in expired_key_names]
            if dry_run:
                play['tasks'].append(
                    dict(
                        action=dict(
                            module='command',
                            args="echo 'Running authorized_key with args user " + user.name + "," +
                                 " keys " + ",".join(expired_key_names) + "," +
                                 " and state absent'",
                        ),
                        register='shell_out'
                    )
                )
                play['tasks'].append(
                    dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}'))))
            else:
                play['tasks'].append(
                    dict(
                        action=dict(
                            module='authorized_key',
                            args=dict(
                                user=user.name,
                                key="\n".join(expired_keys),
                                state="absent"
                            )
                        )
                    )
                )
            logger.info(' - ' + user.name + ' expired for ' +
                        ", ".join(expired_key_names) + ' synced through ' + remote_user)

        if len(authorized_key_names) > 0:
            authorized_keys = [keys[key_name]['key'] + ' ' + key_name for key_name in authorized_key_names]
            if dry_run:
                play['tasks'].append(
                    dict(
                        action=dict(
                            module='command',
                            args="echo 'Running authorized_key with args user " + user.name + "," +
                                 " keys " + ",".join(authorized_key_names) + "," +
                                 " and state present'",
                        ),
                        register='shell_out'
                    )
                )
                play['tasks'].append(
                    dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}'))))
            else:
                play['tasks'].append(
                    dict(
                        action=dict(
                            module='authorized_key',
                            args=dict(
                                user=user.name,
                                key="\n".join(authorized_keys),
                                state="present"
                            )
                        )
                    )
                )
            logger.info(' - ' + user.name + ' authorized for ' +
                        ", ".join(authorized_key_names) + ' synced through ' + remote_user)
        plays.append(play)
    return plays


def get_project_list_keys_play(project, keyname):
    sudoer_account = project.get_sudoer_account(keyname)

    logger.info('Listing authorized keys in project "' + project.name + '" using key "' + keyname + '"')
    plays = []

    for user in project.users:
        if user.is_authorized(keyname):
            # we have direct access to this user, no need to use sudo
            remote_user = user.name
            use_sudo = False
        elif sudoer_account:
            logger.info('sudoer "' + sudoer_account.name + '"')
            # we are allowed to update this user through the sudo user
            remote_user = sudoer_account.name
            use_sudo = True
        else:
            # we skip since we are not authorized to update this user
            continue

        play = dict(
            name="List authorized keys for " + user.name + " on " + project.name,
            hosts=project.name,
            gather_facts='no',
            tasks=[
                dict(
                    action=dict(
                        module='command',
                        args=dict(
                            chdir="/home/" + user.name,
                            cmd="cat .ssh/authorized_keys"
                        )
                    )
                )
            ],
            remote_user=remote_user,
            become=use_sudo
        )
        plays.append(play)
    return plays


class ResultCallback(CallbackBase):
    failures = 0

    def v2_runner_on_ok(self, result, **kwargs):
        logger.debug("SUCCESS for " + result._host.get_name() + " : " + self._dump_results(result._result, indent=2))

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.failures += 1
        logger.error("FAILURE for " + result._host.get_name() + " : " + self._dump_results(result._result, indent=2))
        logger.error("Command was " + json.dumps(result._task._ds["action"], indent=2))

    def v2_runner_on_unreachable(self, result):
        self.failures += 1
        logger.error(
            "UNREACHABLE for " + result._host.get_name() + " : " + self._dump_results(result._result, indent=2))


class ListKeysResultCallback(ResultCallback):

    def v2_runner_on_ok(self, result, **kwargs):
        keys_string = json.loads(self._dump_results(result._result, indent=2), cls=AnsibleJSONDecoder)["stdout"]
        key_names = [key.split(" ")[-1] for key in keys_string.split("\n")]
        logger.info(
            "\n"
            + "#################################################################################################\n\n"
            + "Server " + result._host.get_name() + "\n\n"
            + "\n".join(key_names)
        )


def sync_acl(dl, acl, keys, keyname, project_name, dry_run, private_key):
    ansible_plays = []

    # First, collect all tasks to perform
    for project_yaml in acl:
        project = Project(project_yaml)
        if project_name and project.name != project_name:
            continue
        ansible_plays.extend(get_project_play(project, keys, keyname, dry_run))
    run_plays(dl, acl, private_key, ansible_plays, ResultCallback())


def list_keys(dl, acl, keyname, project_name, private_key):
    ansible_plays = []

    # First, collect all tasks to perform
    for project_yaml in acl:
        project = Project(project_yaml)
        if project_name and project.name != project_name:
            continue
        ansible_plays.extend(get_project_list_keys_play(project, keyname))
    run_plays(dl, acl, private_key, ansible_plays, ListKeysResultCallback())


def run_plays(dl, acl, private_key, ansible_plays, results_callback):
    logger.debug('Collected ' + str(len(ansible_plays)) + ' Ansible plays. Now running...')

    # Second, configure everything for Ansible
    # We must use a file for the inventory. It will be deleted at the end.

    inventory_template = """
    {% for project in projects %}
    [{{project.name}}]
    {% for server in project.servers %}{{ server }} {% if private_key %} ansible_ssh_private_key_file={{ private_key }} {% endif %}
    {% endfor %}
    {% endfor %}
        """
    inventory_file = NamedTemporaryFile(delete=False, mode="w")
    inventory_file.write(jinja2.Template(inventory_template).render({
        'projects': acl,
        'private_key': private_key
    })
    )
    inventory_file.close()
    inventory = InventoryManager(loader=dl, sources=[inventory_file.name])

    variable_manager = VariableManager(loader=dl, inventory=inventory)

    Options = namedtuple('Options', ['connection', 'module_path', 'forks', 'become', 'become_method', 'become_user',
                                     'check', 'diff'])
    options = Options(forks=100, connection="ssh", module_path="", become=None, become_method="sudo",
                      become_user="root", check=False, diff=False)

    tqm = None
    try:
        tqm = TaskQueueManager(
            inventory=inventory,
            variable_manager=variable_manager,
            loader=dl,
            options=options,
            passwords=None,
            stdout_callback=results_callback,  # Use our custom callback
            # instead of the ``default`` callback plugin
        )
        for play in ansible_plays:
            tqm.run(Play().load(
                play, variable_manager=variable_manager, loader=dl))
    finally:
        if tqm is not None:
            os.unlink(inventory_file.name)
            tqm.cleanup()
            if results_callback.failures > 0:
                exit(1)


def main(argv=None):
    if not argv:
        argv = sys.argv

    # Parse the command-line flags.
    flags = parser.parse_args(argv[1:])

    # set logging level
    logger.setLevel(logging.DEBUG)
    h1 = logging.StreamHandler(sys.stdout)
    h1.setLevel(getattr(logging, flags.logging_level))
    logger.addHandler(h1)

    dl = DataLoader()
    # load data
    acl = dl.load_from_file(flags.acl)['acl']
    keys = dl.load_from_file(flags.keys)['keys']

    if flags.list_keys:
        list_keys(dl, acl, flags.key_name, flags.project, flags.private_key)
        return

    sync_acl(dl, acl, keys, flags.key_name, flags.project, flags.dry_run, flags.private_key)


if __name__ == '__main__':
    main(sys.argv)
