#!/usr/bin/python

import os
import sys
import getpass
import paramiko
import policies

def _connect_with_password(ssh, user, host, dport=22) :
    triesLeft = 3
    while triesLeft :
        try :
            passwd = getpass.getpass()
            ssh.connect(host, port=dport, username=user, password=passwd)
        except paramiko.BadAuthenticationType as ex :
            if 'password' in ex.allowed_types or \
               'keyboard-interactive' in ex.allowed_types :
                sys.stderr.write("Wrong password.\n")
                triesLeft -= 1
                continue
            sys.stderr.write("Bad Authentication: allowed types: %s\n" \
                             % (','.join(ex.allowed_types)))
            return False
        return True
    else :
        return False

def get_connection(user, host, dport=22) :
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policies.SSHWarningPolicy())
    known_hosts = os.path.expanduser(os.path.join('~', '.ssh', 'known_hosts'))
    if os.path.exists(known_hosts) :
        ssh.load_host_keys(known_hosts)

    try :
        ssh.connect(host, port=dport, username=user)
    except paramiko.AuthenticationException :
        if not _connect_with_password(ssh, user, host, dport) :
            raise

    return ssh
