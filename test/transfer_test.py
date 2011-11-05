#!/usr/bin/python

import os
import sys
import getpass
import argparse
import paramiko

class SSHWarningPolicy(paramiko.WarningPolicy) :
    def missing_host_key(self, client, hostname, key) :
        import binascii
        answer = raw_input('The authenticity of host %s cannot be established.'
                           '%s key fingerprint is %s.'
                           'Are you sure you want to continue connecting (yes/no)? ' \
                           % (hostname, key.get_name(), binascii.hexlify(key.get_fingerprint())))
        if answer == 'yes' :
            return True
        else :
            raise paramiko.SSHException('Rejecting host %s' % hostname)

def _connect(user, host) :
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(SSHWarningPolicy())
    known_hosts = os.path.expanduser(os.path.join('~', '.ssh', 'known_hosts'))
    if os.path.exists(known_hosts) :
        ssh.load_host_keys(known_hosts)
    try :
        ssh.connect(host, username=user)
    except paramiko.AuthenticationException :
        passwd = getpass.getpass()
        ssh.connect(host, username=user, password=passwd)
    return ssh

def _build_arg_parser() :
    parser = argparse.ArgumentParser(description="file transfer test script", prog="transfer_test")
    parser.add_argument("paths", action="store", nargs="+", default=None, help="([[user@]host:]/path/to/file){2,}")
    parser.add_argument("-f", "--from", action="store_true", default=None, help="source", dest="from_v")
    parser.add_argument("-t", "--to", action="store_true", default=None, help="destination", dest="to_v")
    return parser

def _parse_paths(paths) :
    parsed_paths = []
    for path in paths :
        host_path = path.split(':', 1)
        if len(host_path) == 1 :
            # local path
            parsed_paths.append({'user':'current', 'host':'local', 'path':host_path[0]})
        else :
            # remote path
            usr_host = host_path[0].split('@', 1)
            if len(usr_host) == 1 :
                parsed_paths.append({'user':'current', 'host':usr_host[0], 'path':host_path[1]})
            else :
                parsed_paths.append({'user':usr_host[0], 'host':usr_host[1], 'path':host_path[1]})
    return parsed_paths

# TODO: check if all input and output files are from the same hosts
def _analyse_paths(paths) :
    if paths[0]['host'] != 'local' :
        path = paths[0]
    elif paths[-1]['host'] != 'local' :
        path = paths[-1]
    else :
        print >> sys.stderr, "Error: no remote host"
        exit(1)

    if path['user'] != 'current' :
        return path['user'], path['host']
    else :
        return getpass.getuser(), path['host']

if __name__ == "__main__" :
    parser = _build_arg_parser()
    args = parser.parse_args(sys.argv[1:])
    if len(args.paths) < 2 :
        parser.print_help()
        exit(1)
    paths = _parse_paths(args.paths)
    user, host = _analyse_paths(paths)
    ssh = _connect(user, host)
    ssh.close()
    exit(0)
