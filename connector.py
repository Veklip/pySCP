#!/usr/bin/python

import os
import sys
import getpass
import paramiko
import policies

def _load_pkey(key_file) :
    fo = open(key_file, 'r')
    line = fo.readline()
    fo.close()

    try :
        pkey = None
        if "RSA" in line :
            try :
                pkey = paramiko.RSAKey.from_private_key_file(key_file)
            except paramiko.PasswordRequiredException :
                sys.stderr.write("RSA key file '%s' requires a passphrase.\n" % key_file)
                passwd = getpass.getpass()
                pkey = paramiko.RSAKey.from_private_key_file(key_file, passwd)
        elif "DSA" in line :
            try :
                pkey = paramiko.DSSKey.from_private_key_file(key_file)
            except paramiko.PasswordRequiredException :
                sys.stderr.write("DSA key file '%s' requires a passphrase.\n" % key_file)
                passwd = getpass.getpass()
                pkey = paramiko.DSSKey.from_private_key_file(key_file, passwd)
        return pkey
    except paramiko.SSHException as sshex :
        sys.stderr.write("Key file '%s' is invalid: %s\n" \
                         % (key_file, ' '.join(sshex.args)))
        return None

def _connect_with_password(ssh, user, host, dport=22) :
    triesLeft = 3
    while triesLeft :
        try :
            passwd = getpass.getpass()
            ssh.connect(host, port=dport, username=user, password=passwd)
            return True
        except paramiko.BadAuthenticationType as ex :
            if 'password' in ex.allowed_types or \
               'keyboard-interactive' in ex.allowed_types :
                sys.stderr.write("Wrong password.\n")
                triesLeft -= 1
                continue
            sys.stderr.write("Bad Authentication: allowed types: %s\n" \
                             % (','.join(ex.allowed_types)))
            return False
    else :
        return False

def get_connection(user, host, dport=22, pkeys=None) :
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(policies.SSHWarningPolicy())
    known_hosts = os.path.expanduser(os.path.join('~', '.ssh', 'known_hosts'))
    if os.path.exists(known_hosts) :
        ssh.load_host_keys(known_hosts)

    _pkeys = pkeys if pkeys is not None else ()

    for key in _pkeys :
        try :
            lkey = _load_pkey(key)
            ssh.connect(host, port=dport, username=user, pkey=lkey)
            break
        except paramiko.AuthenticationException :
            pass
    else :
        try :
            ssh.connect(host, port=dport, username=user, password='')
        except paramiko.BadAuthenticationType as ex :
            if 'password' in ex.allowed_types or \
               'keyboard-interactive' in ex.allowed_types :
                if not _connect_with_password(ssh, user, host, dport) :
                    raise Exception("Cannot connect")
            else :
                sys.stderr.write("Bad Authentication: allowed types: %s\n" \
                                 % (','.join(ex.allowed_types)))
                raise
        except paramiko.AuthenticationException :
            raise Exception("Cannot connect")

    return ssh
