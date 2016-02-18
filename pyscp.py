import os
import sys
import time
import argparse
import logging
import socket
import scppath as scpp
import connector as con
import error
import transfer as tfr
import deployment as dep


def _exec_command(ssh, command, paths, f, rec, preserve, check_hash):
    command += " -f" if f else " -t"
    if rec:
        command += " -r"
    if preserve:
        command += " -p"
    if not check_hash:
        command += " --disable-hash-check"
    command = ' '.join((command, paths))
    return ssh.exec_command(command)


def _open_channels(ssh, paths, f, rec, preserve, check_hash):
    # Check if pyscp is available on remote
    stdin, stdout, stderr = ssh.exec_command("pyscp -h")
    while (not stdout.channel.exit_status_ready()):
        time.sleep(5. / 60.)  # 5s
    if (stdout.channel.recv_exit_status() == 0):
        stdin, stdout, stderr = _exec_command(ssh, "pyscp", paths,
                                              f, rec, preserve, check_hash)
    else:
        remote_tempfile = dep.deploy(ssh)
        if (not remote_tempfile):
            raise Exception("Deployment failed")

        stdin, stdout, stderr = \
            _exec_command(ssh, "python2 '{}'".format(remote_tempfile), paths,
                          f, rec, preserve, check_hash)

    return stdin, stdout, stderr


def _local_send(ssh, paths, sink_path, rec, preserve, check_hash):
    try:
        stdin, stdout, stderr = _open_channels(ssh, sink_path,
                                               False, rec, preserve, check_hash)
    except Exception as ex:
        sys.stderr.write(str(ex) + '\n')
        return 1

    ret = tfr.send(stdin, stdout, sys.stderr, sys.stdout, paths, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END:
        return 0
    else:
        sys.stderr.write(stderr.readline())
        return 1


def _remote_send(paths, rec, preserve, check_hash):
    ret = tfr.send(sys.stdout, sys.stdin, sys.stderr, None, paths, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END:
        return 0
    else:
        return 1


def _local_recv(ssh, paths, dir_path, rec, preserve, check_hash):
    try:
        stdin, stdout, stderr = _open_channels(ssh, ' '.join(paths),
                                               True, rec, preserve, check_hash)
    except Exception as ex:
        sys.stderr.write(str(ex) + '\n')
        return 1

    ret = tfr.recv(stdin, stdout, sys.stderr, sys.stdout, dir_path, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END:
        return 0
    else:
        sys.stderr.write(stderr.readline())
        return 1


def _remote_recv(dir_path, rec, preserve, check_hash):
    ret = tfr.recv(sys.stdout, sys.stdin, sys.stderr, None, dir_path, preserve, check_hash)
    if ret == error.E_OK or ret == error.E_END:
        return 0
    else:
        return 1


def _build_arg_parser():
    parser = argparse.ArgumentParser(description="Python secure copy over ssh", prog="pyscp")
    parser.add_argument("paths", action="store", nargs="+", default=[], type=scpp.parse_scp_path, help="[[user@]host1:]file1 ... [[user@]host2:]file2")
    parser.add_argument("-f", action="store_true", default=None, help="source", dest="from_")
    parser.add_argument("-t", action="store_true", default=None, help="destination", dest="to_")
    parser.add_argument("-r", action="store_true", default=None, help="recursively copy directories", dest="rec")
    parser.add_argument("-p", action="store_true", default=None, help="preserve access and modification times", dest="preserve")
    parser.add_argument("-q", action="store_true", default=None, help="do not print any output", dest="quiet")
    parser.add_argument("--disable-hash-check", action="store_false", default=True, help="disable SHA1 comparison between source and destination files", dest="check_hash")
    parser.add_argument("-P", action="store", default=22, type=int, help="port on remote host to connect to", dest="port")
    parser.add_argument("-i", action="append", default=[], help="private key for public key authentication", metavar="identity_file", dest="pkeys")
    parser.add_argument("-v", action="count", help="verbose mode", dest="verbose")
    return parser


def main():
    os.stat_float_times(False)

    parser = _build_arg_parser()
    args = parser.parse_args(sys.argv[1:])

    if (args.verbose >= 3):
        logging.basicConfig(level=logging.NOTSET)
    elif (args.verbose == 2):
        logging.basicConfig(level=logging.DEBUG)
    elif (args.verbose == 1):
        logging.basicConfig(level=logging.INFO)
    elif (args.verbose == 0):
        logging.basicConfig(level=logging.WARNING)

    ret = 1
    if (args.from_ or args.to_):
        # only executed by the remote
        paths = [path.path for path in args.paths]
        paths = scpp.normalise_paths(paths)
        paths = scpp.unique_paths(paths)

        if (args.from_):
            ret = _remote_send(paths, args.rec, args.preserve,
                               args.check_hash)
        elif (args.to_):
            ret = _remote_recv(paths[0], args.rec, args.preserve,
                               args.check_hash)
    else:
        # only executed by the local
        localhost = socket.getfqdn()
        paths = []
        for path in scpp.group_scp_paths(args.paths):
            if (path.host == localhost):
                path.path = scpp.unique_paths(scpp.normalise_paths(path.path))
            paths.append(path)

        sources = paths[:-1]
        sink = paths[-1]

        if (not sources):
            parser.print_usage()
            return 1

        pkeys = scpp.unique_paths(scpp.normalise_paths(args.pkeys))

        if (args.quiet):
            null = open(os.devnull, 'r+')
            local_out = sys.stdout
            local_err = sys.stderr
            sys.stdout = null
            sys.stderr = null

        send = not sink.host == localhost
        for src in sources:
            if (send):
                ssh = con.get_connection(sink.user, sink.host, args.port, pkeys)
                # from local to remote
                ret = _local_send(ssh, src.path, sink.path[0],
                                  args.rec, args.preserve, args.check_hash)
                ssh.close()
            else:
                # from remote to local
                ssh = con.get_connection(src.user, src.host, args.port, pkeys)
                ret = _local_recv(ssh, src.path, sink.path[0],
                                  args.rec, args.preserve, args.check_hash)
                ssh.close()

        if (args.quiet):
            sys.stderr = local_err
            sys.stdout = local_out
            null.close()
    return ret

if (__name__ == "__main__"):
    try:
        exit(main())
    except Exception as ex:
        sys.stderr.write(str(ex) + '\n')
        exit(1)
