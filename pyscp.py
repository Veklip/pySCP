import warnings as w
w.filterwarnings('ignore', '.*RandomPool.*', DeprecationWarning, '.*randpool', 0)

import sys
import time
import argparse
import logging
import parser as psr
import connector as con
import error
import transfer as tfr
import deployment as dep

def _exec_command(ssh, command, paths, f, rec, preserve, check_hash) :
    command += " -f" if f else " -t"
    if rec :
        command += " -r"
    if preserve :
        command += " -p"
    if not check_hash :
        command += " --disable-hash-check"
    command = ' '.join((command, paths))
    return ssh.exec_command(command)

def _open_channels(ssh, paths, f, rec, preserve, check_hash) :
    # Check if pyscp is available on remote
    stdin, stdout, stderr = ssh.exec_command("pyscp -h")
    while (not stdout.channel.exit_status_ready()) :
        time.sleep(5./60.) # 5s
    if (stdout.channel.recv_exit_status() == 0) :
        stdin, stdout, stderr = _exec_command(ssh, "pyscp", paths,
                                              f, rec, preserve, check_hash)
    else :
        if (not dep.deploy(ssh)) :
            raise Exception("Deployment failed")

        stdin, stdout, stderr = _exec_command(ssh, "python2 /tmp/pyscp.zip", paths,
                                              f, rec, preserve, check_hash)

    return stdin, stdout, stderr

def _local_send(ssh, paths, sink_path, rec, preserve, check_hash) :
    try :
        stdin, stdout, stderr = _open_channels(ssh, sink_path,
                                               False, rec, preserve, check_hash)
    except Exception as ex :
        sys.stderr.write(str(ex) + '\n')
        return 1

    ret = tfr.send(stdin, stdout, sys.stderr, sys.stdout, paths, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END :
        return 0
    else :
        sys.stderr.write(stderr.readline())
        return 1

def _remote_send(paths, rec, preserve, check_hash) :
    ret = tfr.send(sys.stdout, sys.stdin, sys.stderr, None, paths, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END :
        return 0
    else :
        return 1

def _local_recv(ssh, paths, dir_path, rec, preserve, check_hash) :
    try :
        stdin, stdout, stderr = _open_channels(ssh, ' '.join(paths),
                                               True, rec, preserve, check_hash)
    except Exception as ex :
        sys.stderr.write(str(ex) + '\n')
        return 1

    ret = tfr.recv(stdin, stdout, sys.stderr, sys.stdout, dir_path, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END :
        return 0
    else :
        sys.stderr.write(stderr.readline())
        return 1

def _remote_recv(dir_path, rec, preserve, check_hash) :
    ret = tfr.recv(sys.stdout, sys.stdin, sys.stderr, None, dir_path, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END :
        return 0
    else :
        return 1

def _build_arg_parser() :
    parser = argparse.ArgumentParser(description="Python secure copy over ssh", prog="pyscp")
    parser.add_argument("paths", action="store", nargs="+", default=[], help="[[user@]host1:]file1 ... [[user@]host2:]file2")
    parser.add_argument("-f", action="store_true", default=None, help="source", dest="from_v")
    parser.add_argument("-t", action="store_true", default=None, help="destination", dest="to_v")
    parser.add_argument("-r", action="store_true", default=None, help="recursively copy directories", dest="rec")
    parser.add_argument("-p", action="store_true", default=None, help="preserve access and modification times", dest="preserve")
    parser.add_argument("-q", action="store_true", default=None, help="do not print any output", dest="quiet")
    parser.add_argument("--disable-hash-check", action="store_false", default=True, help="disable SHA1 comparison between source and destination files", dest="check_hash")
    parser.add_argument("-P", action="store", default=22, type=int, help="port on remote host to connect to", dest="port")
    parser.add_argument("-i", action="append", default=[], help="private key for public key authentication", metavar="identity_file", dest="pkeys")
    parser.add_argument("-v", action="append_const", const=None, default=[], help="verbose mode", dest="verbose")
    return parser

def main() :
    import os
    os.stat_float_times(False)

    parser = _build_arg_parser()
    args = parser.parse_args(sys.argv[1:])

    verbose_level = min(len(args.verbose), 3)
    if (verbose_level == 0) :
        logging.basicConfig(level=logging.WARNING)
    if (verbose_level == 1) :
        logging.basicConfig(level=logging.INFO)
    if (verbose_level == 2) :
        logging.basicConfig(level=logging.DEBUG)
    if (verbose_level == 3) :
        logging.basicConfig(level=logging.NOTSET)

    # these should only be called by the remote
    ret = 1
    if args.from_v :
        ret = _remote_send(args.paths, args.rec, args.preserve,
                           args.check_hash)
    elif args.to_v :
        ret = _remote_recv(args.paths[0], args.rec, args.preserve,
                           args.check_hash)
    else :
        paths = psr.parse_paths(args.paths)
        # only executed by the local
        if len(paths) < 2 :
            parser.print_help()
            return 1
        send, user, host, paths = psr.analyse_paths(paths)
        if len(host) == 0 :
            return 1

        if not psr.check_pkeys(args.pkeys) :
            return 1

        try :
            ssh = con.get_connection(user, host, args.port, args.pkeys)
        except Exception as ex :
            sys.stderr.write(str(ex) + '\n')
            return 1

        if args.quiet :
            null = open(os.devnull, 'r+')
            local_out = sys.stdout
            local_err = sys.stderr
            sys.stdout = null
            sys.stderr = null

        if send :
            # from local to remote
            ret = _local_send(ssh, paths[:-1], paths[-1],
                              args.rec, args.preserve, args.check_hash)
        else :
            # from remove to local
            ret = _local_recv(ssh, paths[:-1], paths[-1],
                              args.rec, args.preserve, args.check_hash)

        if args.quiet :
            sys.stderr = local_err
            sys.stdout = local_out
            null.close()
        ssh.close()
    return ret

if __name__ == "__main__" :
    exit(main())
