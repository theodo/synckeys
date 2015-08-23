#!/usr/bin/env python

from ansible import utils
import ansible.runner
import os
import getpass
import sys
import logging
import argparse
import datetime
import time

logger = logging.getLogger(__name__)

# Parser for command-line arguments.
parser = argparse.ArgumentParser(
    description     = __doc__,
    formatter_class = argparse.RawDescriptionHelpFormatter
)

parser.add_argument(
    '--key-name',
    default     = getpass.getuser(),
    help        = 'The name of your key in the file containing all keys'
)

parser.add_argument(
    '--project',
    default     = None,
    help        = 'Sync a particular project'
)
parser.add_argument(
    '--acl',
    default     = os.path.join(os.getcwd(), 'acl.yml'),
    help        = 'Name of the file containing all access informations'
)

parser.add_argument(
    '--keys',
    default = os.path.join(os.getcwd(), 'keys.yml'),
    help    = 'Name of the file containing all keys'
)

parser.add_argument(
    '--logging-level',
    default = 'INFO'
)


# The unix user (e.g. www-data, operator)
# not the Theodoer user !
class User:
    def __init__(self, name, acl):
        self.name = name
        self.acl  = acl

    def is_sudoer(self):
        if 'sudoer' in self.acl:
            return self.acl['sudoer']
        else:
            return False

    def is_authorized(self, keyname):
        return keyname in self.acl['authorized_keys']


class Project:
    def __init__(self, project_yaml):
        self.name    = project_yaml['name']
        self.servers = project_yaml['servers']
        self.users   = []
        for username, useracl in project_yaml['users'].items():
            self.users.append(User(username, useracl))

    def get_sudoer_account(self, keyname):
        for user in self.users:
            if user.is_sudoer() and user.is_authorized(keyname):
                return user
        return None


def sync_project(project, keys, keyname, master_key_names):

    sudoer_account = project.get_sudoer_account(keyname)

    logger.info('Syncing "' + project.name + '" using key "' + keyname + '"')

    for user in project.users:
        if user.is_authorized(keyname) or keyname in master_key_names:
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

        remote_pass = user.acl['password'] if 'password' in user.acl else None

        # if we are authorized, let us update this user's keys
        # build the authorized_key_names, including the master keys (unique values)
        authorized_key_names = list(set(user.acl['authorized_keys'] + master_key_names))
        logger.info(' - ' + user.name + ' authorized for ' + ", ".join(authorized_key_names) + ' synced through ' + remote_user)

        authorized_keys = []
        expired_keys = []
        for authorized_key_name in authorized_key_names:
            if not keys[authorized_key_name]['expires'] or keys[authorized_key_name]['expires'] > datetime.datetime.now().date():
                authorized_keys.append(keys[authorized_key_name]['key'] + ' ' + authorized_key_name)
            else:
                expired_keys.append(keys[authorized_key_name]['key'])

        push_keys(
            host_list=project.servers,
            remote_user=remote_user,
            remote_pass=remote_pass,
            use_sudo=use_sudo,
            username=user.name,
            keys=expired_keys,
            delete=True
        )

        push_keys(
            host_list=project.servers,
            remote_user=remote_user,
            remote_pass=remote_pass,
            use_sudo=use_sudo,
            username=user.name,
            keys=authorized_keys
        )

        logger.info(' - ' + user.name + ' authorized for ' + ", ".join(authorized_key_names) + ' synced through ' + remote_user)


def push_keys(host_list, remote_user, remote_pass, use_sudo, username, keys, delete=False):
    if delete:
        state = "absent"
    else:
        state = "present"

    ret = ansible.runner.Runner(
       module_name      = 'authorized_key',
       module_args      = {
                            'user': username,
                            'state': state,
                            'key': "\n".join(keys)
                          },
       host_list        = host_list,
       remote_user      = remote_user,
       remote_pass      = remote_pass,
       become           = use_sudo
    ).run()
    logger.debug(ret)
    if ret['dark'] != {}:
        logger.error(ret['dark'])


def get_master_key_names(keys):
    master_key_names = []
    for name in keys:
        if 'master' in keys[name] and keys[name]['master'] == True:
            master_key_names.append(name)

    return master_key_names;


def sync_acl(acl, keys, keyname, project_name=None):
    master_key_names = get_master_key_names(keys)

    if (keyname in master_key_names):
        logger.warning("*** WARNING: You are using the '%s' master key, you will access every server ***" % keyname)
        time.sleep(3)

    for project_yaml in acl:
        project = Project(project_yaml)
        if project_name and project.name != project_name:
            continue
        sync_project(project, keys, keyname, master_key_names)


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

    # load data
    acl = utils.parse_yaml_from_file(flags.acl)['acl']
    keys = utils.parse_yaml_from_file(flags.keys)['keys']

    sync_acl(acl, keys, flags.key_name, flags.project)


if __name__ == '__main__':
    main(sys.argv)
