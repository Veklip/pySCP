import os
import os.path
import sys
import socket
import getpass
import argparse


class SCPPath(object):
    def __init__(self, user, host, path):
        self.user = user
        self.host = host
        self.path = path

    def __eq__(self, obj):
        return self.user == obj.user and self.host == obj.host

    def __repr__(self):
        return "{}({}, {}, {})".format(type(self).__name__,
                                       self.user, self.host, self.path)


def parse_scp_path(arg):
    userhost_path = arg.split(':', 1)
    user = getpass.getuser()
    host = socket.getfqdn()
    path = userhost_path[-1]
    if (len(userhost_path) == 2):
        user_host = userhost_path[0].split('@', 1)
        host = socket.getfqdn(user_host[-1])
        if (len(user_host) == 2):
            user = user_host[0]
    return SCPPath(user, host, path)


def group_scp_paths(paths):
    groups = []
    for path in paths:
        try:
            idx = groups.index(path)
            groups[idx].path.append(path.path)
        except ValueError:
            groups.append(SCPPath(path.user, path.host, [path.path]))
    return groups


def normalise_paths(paths):
    npaths = []
    for path in paths:
        path = os.path.abspath(path)
        if (not os.path.exists(path)):
            raise argparse.ArgumentError(None, '"{}" does not exist.'.format(path))
        npaths.append(path)
    return npaths


def unique_paths(paths):
    unq_paths = []
    for path in paths:
        if (path not in unq_paths):
            unq_paths.append(path)
        else:
            sys.stdout.write('pyscp: warning: skipping duplicate: "{}".\n'.format(path))
    return unq_paths


def check_pkeys(pkey_files) :
    if pkey_files is None :
        return True

    for key in pkey_files :
        if not os.path.exists(key) :
            sys.stderr.write("Key file '{0}' doesn't exist\n".format(key))
            return False
    return True
