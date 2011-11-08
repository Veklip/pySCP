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

def _local_from(ssh, paths_from, path_to) :
    command = "~/transfer_test.py -t %s" % path_to['path']
    stdin, stdout, stderr = ssh.exec_command(command)

    path = paths_from[0]['path']
    fo = open(path, 'rb')
    stat = os.stat(path)
    bytes_to_send = stat.st_size
    # command: sending file
    # TODO: use mode
    stdin.write('C0755 %s %s\n' % (bytes_to_send, os.path.basename(path_to['path'])))
    stdin.flush()
    ret = stdout.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", stdout.readline()
        return

    # command: beginning data transfer
    stdin.write('\0')
    stdin.flush()
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = fo.read(chunk)
        if len(buf) :
            stdin.write(buf)
            stdin.flush()
            bytes_to_send = bytes_to_send - len(buf)
        if bytes_to_send <= 0 :
            break
    fo.close()
    ret = stdout.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", stdout.readline()
        return
    # command: end of file data transfer
    stdin.write('E\n')
    stdin.flush()
    ret = stdout.read(1)
    if ret != '\0' :
        print >> sys.stderr, "Error:", stdout.readline()
        return

def _remote_from(paths) :
    path = paths[0]['path']
    fo = open(path, 'rb')
    stat = os.stat(path)
    bytes_to_send = stat.st_size
    # command: sending file
    # TODO: use mode
    sys.stdout.write('C0755 %s %s\n' % (bytes_to_send, os.path.basename(path)))
    sys.stdout.flush()
    ret = sys.stdin.read(1)
    if ret != '\0' :
        exit(ord(ret))

    # command: beginning data transfer
    sys.stdout.write('\0')
    sys.stdout.flush()
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = fo.read(chunk)
        if len(buf) :
            sys.stdout.write(buf)
            sys.stdout.flush()
            bytes_to_send = bytes_to_send - len(buf)
        if bytes_to_send <= 0 :
            break
    fo.close()
    ret = sys.stdin.read(1)
    if ret != '\0' :
        exit(ord(ret))
    # command: end of file data transfer
    sys.stdout.write('E\n')
    sys.stdout.flush()
    ret = sys.stdin.read(1)
    if ret != '\0' :
        exit(ord(ret))

def _local_to(ssh, paths) :
    command = "~/transfer_test.py -f %s" % paths[0]['path']
    stdin, stdout, stderr = ssh.exec_command(command)

    command = stdout.readline()
    # TODO: add regex check on the command format
    if command[0] != 'C' :
        stdin.write('\2')
        stdin.flush()
        sys.stderr.write('Unknown command %s\n' % command)
        return
    else :
        stdin.write('\0')
        stdin.flush()

    # ignore the '\n' at the end
    mode, size, path = command[:-1].split(' ', 3)
    size = int(size)

    command = stdout.read(1)
    if command != '\0' :
        stdin.write('\2')
        stdin.flush()
        sys.stderr.write('Unknown protocol command sequence\n')
        return

    fo = open(path, 'wb')
    while True :
        if size < 4096 :
            chunk = size
        else :
            chunk = 4096
        buf = stdout.read(chunk)
        if len(buf) :
            fo.write(buf)
            size = size - len(buf)
        if size <= 0 :
            fo.flush()
            break
    fo.close()
    stdin.write('\0')
    stdin.flush()

    command = stdout.readline()
    if command[0] != 'E' :
        stdin.write('\2')
        stdin.flush()
        sys.stderr.write('Unknown command %s\n' % command)
        return
    else :
        stdin.write('\0')
        stdin.flush()

def _remote_to(paths) :
    command = sys.stdin.readline()
    # TODO: add regex check on the command format
    if command[0] != 'C' :
        sys.stdout.write('\2')
        sys.stdout.write('Unknown command %s\n' % command)
        sys.stdout.flush()
        return
    else :
        sys.stdout.write('\0')
        sys.stdout.flush()

    # ignore the '\n' at the end
    mode, size, path = command[:-1].split(' ', 3)
    size = int(size)

    command = sys.stdin.read(1)
    if command != '\0' :
        sys.stdout.write('\2')
        sys.stdout.write('Unknown protocol command sequence\n')
        sys.stdout.flush()
        return

    fo = open(path, 'wb')
    while True :
        if size < 4096 :
            chunk = size
        else :
            chunk = 4096
        buf = sys.stdin.read(chunk)
        if len(buf) :
            fo.write(buf)
            size = size - len(buf)
        if size <= 0 :
            fo.flush()
            break
    fo.close()
    sys.stdout.write('\0')
    sys.stdout.flush()

    command = sys.stdin.readline()
    if command[0] != 'E' :
        sys.stdout.write('\2')
        sys.stdout.write('Unknown command %s\n' % command)
        sys.stdout.flush()
        return
    else :
        sys.stdout.write('\0')
        sys.stdout.flush()

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
        send = False
        path = paths[0]
    elif paths[-1]['host'] != 'local' :
        send = True
        path = paths[-1]
    else :
        print >> sys.stderr, "Error: no remote host"
        exit(1)

    if path['user'] != 'current' :
        return send, path['user'], path['host']
    else :
        return send, getpass.getuser(), path['host']

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
        try :
            _remote_to(paths)
        except Exception as ex :
            print >> sys.stderr, "exception", ex.args
    else :
        # only executed by the local
        if len(paths) < 2 :
            parser.print_help()
            exit(1)
        send, user, host = _analyse_paths(paths)

        ssh = _connect(user, host)

        if send :
            # from local to remote
            _local_from(ssh, paths[:-1], paths[-1])
        else :
            # from remove to local
            _local_to(ssh, paths)

        ssh.close()
    exit(0)
