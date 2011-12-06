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

# TODO: add T command
def _send_file(i, o, e, file_path) :
    stat = os.stat(file_path)
    bytes_to_send = stat.st_size
    mode = oct(stat.st_mode & 0x1FF)
    # command: sending file
    i.write('C%s %ld %s\n' % (mode, bytes_to_send, os.path.basename(file_path)))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 1

    # data transfer starts right after C command
    fo = open(file_path, 'rb')
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = fo.read(chunk)
        if len(buf) :
            i.write(buf)
            i.flush()
            bytes_to_send = bytes_to_send - len(buf)
        if bytes_to_send <= 0 :
            break
    fo.close()
    # data transfer end
    i.write('\0')
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 2

    return 0

def _send_dir(i, o, e, dir_path) :
    name = os.path.basename(dir_path)
    stat = os.stat(dir_path)
    mode = oct(stat.st_mode & 0x1FF)
    # command: sending directory
    i.write('D%s 0 %s\n' % (mode, name))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 1

    items = os.listdir(dir_path)
    ret = 0
    for it in items :
        p = os.path.join(dir_path, it)
        if os.path.isdir(p) :
            ret = _send_dir(i, o, e, p)
        elif os.path.isfile(p) :
            ret = _send_file(i, o, e, p)
        if ret != 0 :
            return ret

    i.write('E\n');
    i.flush();
    ret = o.read(1)
    if ret != '\0' :
        return 2

    return 0

def _recv_file_dir_or_end(i, o, e, target_dir) :
    # TODO: handle the return codes of the _recv_* functions
    command = o.readline()
    if len(command) == 0 :
        return -1 # end of transfer ?
    ret = 65535 # big enough number
    if command[0] == 'C' :
        i.write('\0')
        i.flush()
        ret = _recv_file(i, o, e, target_dir, command)
    elif command[0] == 'D' :
        i.write('\0')
        i.flush()
        ret = _recv_dir(i, o, e, target_dir, command)
    elif command[0] == 'E' :
        i.write('\0')
        i.flush()
        ret = -1 # end of directory
    else :
        i.write('\2')
        i.flush()
    return ret

def _recv_file(i, o, e, target_dir, command) :
    # TODO: add regex check on the command format
    # ignore the '\n' at the end
    mode, size, path = command[1:-1].split(' ', 3)
    size = int(size)
    mode = int(mode, 8)

    if os.path.isdir(target_dir) :
        file_path = os.path.join(target_dir, path)
    else :
        file_path = target_dir
    fo = open(file_path, 'wb')
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
    os.chmod(file_path, mode)
    ret = o.read(1)
    if ret != '\0' :
        i.write('\2')
        i.flush()
        return 2
    else :
        i.write('\0')
        i.flush()

    return 0

def _recv_dir(i, o, e, dir_path, command) :
    # ignore the '\n' at the end
    mode, size, name = command[1:-1].split(' ', 3)
    mode = int(mode, 8)

    # TODO: check if sending dir is the same
    new_dir_path = os.path.join(dir_path, name)
    if not os.path.exists(new_dir_path) :
        os.mkdir(new_dir_path, mode)
    else :
        os.chmod(new_dir_path, mode)

    while True :
        ret = _recv_file_dir_or_end(i, o, e, new_dir_path)
        if ret == -1 :
            return 0 # E command
        if ret == 65535 :
            return 1 # wrong command
        if ret != 0 :
            return 2 # error in transfer

def _local_send(ssh, paths, sink_path, rec) :
    command = "~/transfer_test.py -t"
    if rec :
        command += "r"
    command = ' '.join((command, sink_path))
    stdin, stdout, stderr = ssh.exec_command(command)

    # check if receiving end is ready
    ret = stdout.read(1)
    if ret != '\0' :
        return 1

    ret = 0
    for p in paths :
        if os.path.isfile(p) :
            ret = _send_file(stdin, stdout, stderr, p)
        elif os.path.isdir(p) :
            ret = _send_dir(stdin, stdout, stderr, p)
        if ret != 0 :
            break
    return ret

def _remote_send(paths, rec) :
    # check if receiving end is ready
    ret = sys.stdin.read(1)
    if ret != '\0' :
        return 1

    ret = 0
    for p in paths :
        if os.path.isfile(p) :
            ret = _send_file(sys.stdout, sys.stdin, sys.stderr, p)
        elif os.path.isdir(p) :
            ret = _send_dir(sys.stdout, sys.stdin, sys.stderr, p)
        if ret != 0 :
            break
    return ret

def _local_recv(ssh, paths, dir_path, rec) :
    command = "~/transfer_test.py -f"
    if rec :
        command += "r"
    command = ' '.join((command, ' '.join(paths)))
    stdin, stdout, stderr = ssh.exec_command(command)

    stdin.write('\0') # ready to receive
    stdin.flush()

    while True :
        ret = _recv_file_dir_or_end(stdin, stdout, stderr, dir_path)
        if ret == -1 :
            return 0 # E command
        if ret == 65535 :
            return 1 # wrong command
        if ret != 0 :
            return 2 # error in transfer

def _remote_recv(dir_path, rec) :
    sys.stdout.write('\0') # ready to receive
    sys.stdout.flush()

    while True :
        ret = _recv_file_dir_or_end(sys.stdout, sys.stdin, sys.stderr, dir_path)
        if ret == -1 :
            return 0 # E command
        if ret == 65535 :
            return 1 # wrong command
        if ret != 0 :
            return 2 # error in transfer

def _build_arg_parser() :
    parser = argparse.ArgumentParser(description="file transfer test script", prog="transfer_test")
    parser.add_argument("paths", action="store", nargs="+", default=None, help="[[user@]host1:]file1 ... [[user@]host2:]file2")
    parser.add_argument("-f", action="store_true", default=None, help="source", dest="from_v")
    parser.add_argument("-t", action="store_true", default=None, help="destination", dest="to_v")
    parser.add_argument("-r", action="store_true", default=None, help="recursively copy directories", dest="rec")
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
    stripped = [paths[0]['path']]

    for i in range(1, len(paths) - 1) :
        if user != paths[i]['user'] or host != paths[i]['host'] :
            print >> sys.stderr, "Error: all source paths need to be from the same user and host"
            return False, "", "", []
        stripped.append(paths[i]['path'])

    if host == paths[-1]['host'] :
        print >> sys.stderr, "Error: source and sink files need to be with different hosts"
        return False, "", "", []
    stripped.append(paths[-1]['path'])

    if host == "local" :
        if paths[-1]['user'] != 'current' :
            return True, paths[-1]['user'], paths[-1]['host'], stripped
        else :
            return True, getpass.getuser(), paths[-1]['host'], stripped
    else :
        if user != 'current' :
            return False, user, host, stripped
        else :
            return False, getpass.getuser(), host, stripped

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

    # these should only be called by the remote
    ret = 0
    if args.from_v :
        ret = _remote_send(args.paths, args.rec)
    elif args.to_v :
        ret = _remote_recv(args.paths[0], args.rec)
    else :
        paths = _parse_paths(args.paths)
        # only executed by the local
        if len(paths) < 2 :
            parser.print_help()
            exit(1)
        send, user, host, paths = _analyse_paths(paths)
        if len(host) == 0 :
            exit(1)

        ssh = _connect(user, host)

        if send :
            # from local to remote
            ret = _local_send(ssh, paths[:-1], paths[-1], args.rec)
        else :
            # from remove to local
            ret = _local_recv(ssh, paths[:-1], paths[-1], args.rec)

        ssh.close()
    exit(ret)
