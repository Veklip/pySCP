#!/usr/bin/python

import os
import getpass
import paramiko
import policies

def get_connection(user, host, dport=22) :
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policies.SSHWarningPolicy())
    known_hosts = os.path.expanduser(os.path.join('~', '.ssh', 'known_hosts'))
    if os.path.exists(known_hosts) :
        ssh.load_host_keys(known_hosts)
    try :
        ssh.connect(host, port=dport, username=user)
    except paramiko.AuthenticationException :
        passwd = getpass.getpass()
        ssh.connect(host, port=dport, username=user, password=passwd)
    return ssh
