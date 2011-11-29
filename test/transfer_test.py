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

# TODO: error printing is handled locally and outside this function
# TODO: errors should be passed through the error channel. the check in
# the read channel should only be the indication of an error
def _from(i, o, e, source, target) :
    stat = os.stat(source.name)
    bytes_to_send = stat.st_size
    # command: sending file
    # TODO: use mode
    i.write('C0755 %s %s\n' % (bytes_to_send, target))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", o.readline()
        return 1

    # command: beginning data transfer
    i.write('\0')
    i.flush()
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = source.read(chunk)
        if len(buf) :
            i.write(buf)
            i.flush()
            bytes_to_send = bytes_to_send - len(buf)
        if bytes_to_send <= 0 :
            break
    ret = o.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", o.readline()
        return 1
    # command: end of file data transfer
    i.write('E\n')
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", o.readline()
        return 1

    return 0

def _to(i, o, e, target_dir) :
    command = o.readline()
    # TODO: add regex check on the command format
    if command[0] != 'C' :
        i.write('\2')
        i.flush()
        sys.stderr.write('Unknown command %s\n' % command)
        return 1
    else :
        i.write('\0')
        i.flush()

    # ignore the '\n' at the end
    mode, size, path = command[:-1].split(' ', 3)
    size = int(size)

    command = o.read(1)
    if command != '\0' :
        i.write('\2')
        i.flush()
        sys.stderr.write('Unknown protocol command sequence\n')
        return 1

    fo = open(os.path.join(target_dir, path), 'wb')
    while True :
        if size < 4096 :
            chunk = size
        else :
            chunk = 4096
        buf = o.read(chunk)
        if len(buf) :
            fo.write(buf)
            size = size - len(buf)
        if size <= 0 :
            fo.flush()
            break
    fo.close()
    i.write('\0')
    i.flush()

    command = o.readline()
    if command[0] != 'E' :
        i.write('\2')
        i.flush()
        sys.stderr.write('Unknown command %s\n' % command)
        return 1
    else :
        i.write('\0')
        i.flush()

    return 0

def _local_from(ssh, paths_from, path_to) :
    command = "~/transfer_test.py -t %s" % path_to['path']
    stdin, stdout, stderr = ssh.exec_command(command)

    fo = open(paths_from[0]['path'], 'rb')
    _from(stdin, stdout, stderr, fo, os.path.basename(path_to['path']))
    fo.close()

def _remote_from(paths) :
    fo = open(paths[0]['path'], 'rb')
    _from(sys.stdout, sys.stdin, sys.stderr, fo, os.path.basename(paths[0]['path']))
    fo.close()

def _local_to(ssh, paths, dir_path) :
    command = "~/transfer_test.py -f %s" % paths[0]['path']
    stdin, stdout, stderr = ssh.exec_command(command)

    _to(stdin, stdout, stderr, dir_path)

def _remote_to(dir_path) :
    _to(sys.stdout, sys.stdin, sys.stderr, dir_path)

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

def _analyse_paths(paths) :
    user = paths[0]['user']
    host = paths[0]['host']

    for i in range(1, len(paths) - 1) :
        if user != paths[i]['user'] or host != paths[i]['host'] :
            print >> sys.stderr, "Error: all source paths need to be from the same user and host"
            return False, "", ""

    if host == paths[-1]['host'] :
        print >> sys.stderr, "Error: source and sink files need to be with different hosts"
        return False, "", ""

    if host == "local" :
        if paths[-1]['user'] != 'current' :
            return True, paths[-1]['user'], paths[-1]['host']
        else :
            return True, getpass.getuser(), paths[-1]['host']
    else :
        if user != 'current' :
            return False, user, host
        else :
            return False, getpass.getuser(), host

def _check_paths(paths) :
    ok = True
    for path in paths :
        if not os.path.exists(path['path']) :
            ok = False
            print >> sys.stderr, "Error: '%s' doesn't exist" % path['path']

    return ok

if __name__ == "__main__" :
    parser = _build_arg_parser()
    args = parser.parse_args(sys.argv[1:])
    paths = _parse_paths(args.paths)

    # these should only be called by the remote
    if args.from_v :
        _remote_from(paths)
    elif args.to_v :
        _remote_to(paths)
    else :
        # only executed by the local
        if len(paths) < 2 :
            parser.print_help()
            exit(1)
        send, user, host = _analyse_paths(paths)
        if len(host) == 0 :
            exit(1)

        ssh = _connect(user, host)

        if send :
            # from local to remote
            _local_from(ssh, paths[:-1], paths[-1])
        else :
            # from remove to local
            _local_to(ssh, paths, ".")

        ssh.close()
    exit(0)
