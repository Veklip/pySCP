#!/usr/bin/python

import os
import sys
import argparse
import parser as psr
import connector as con
import transfer as tfr

def _local_send(ssh, paths, sink_path, rec) :
    command = "pyscp.py -t"
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
            ret = tfr.send_file(stdin, stdout, p)
        elif os.path.isdir(p) :
            ret = tfr.send_dir(stdin, stdout, p)
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
            ret = tfr.send_file(sys.stdout, sys.stdin, p)
        elif os.path.isdir(p) :
            ret = tfr.send_dir(sys.stdout, sys.stdin, p)
        if ret != 0 :
            break
    return ret

def _local_recv(ssh, paths, dir_path, rec) :
    command = "pyscp.py -f"
    if rec :
        command += "r"
    command = ' '.join((command, ' '.join(paths)))
    stdin, stdout, stderr = ssh.exec_command(command)

    stdin.write('\0') # ready to receive
    stdin.flush()

    while True :
        ret = tfr.recv_file_dir_or_end(stdin, stdout, dir_path)
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
        ret = tfr.recv_file_dir_or_end(sys.stdout, sys.stdin, dir_path)
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
        paths = psr.parse_paths(args.paths)
        # only executed by the local
        if len(paths) < 2 :
            parser.print_help()
            exit(1)
        send, user, host, paths = psr.analyse_paths(paths)
        if len(host) == 0 :
            exit(1)

        ssh = con.get_connection(user, host)

        if send :
            # from local to remote
            ret = _local_send(ssh, paths[:-1], paths[-1], args.rec)
        else :
            # from remove to local
            ret = _local_recv(ssh, paths[:-1], paths[-1], args.rec)

        ssh.close()
    exit(ret)
