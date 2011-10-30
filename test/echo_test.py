#!/usr/bin/python

import os
import sys
import argparse
import paramiko
import binascii

class SSHWarningPolicy(paramiko.WarningPolicy) :
    def missing_host_key(self, client, hostname, key) :
        answer = raw_input('The authenticity of host %s cannot be established.'
                           '%s key fingerprint is %s.'
                           'Are you sure you want to continue connecting (yes/no)? ' \
                           % (hostname, key.get_name(), binascii.hexlify(key.get_fingerprint())))
        if answer == 'yes' :
            return True
        else :
            raise paramiko.SSHException('Rejecting host %s' % hostname)

def _exec_from(args) :
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(SSHWarningPolicy())
    known_hosts = os.path.expanduser(os.path.join('~', '.ssh', 'known_hosts'))
    if os.path.exists(known_hosts) :
        ssh.load_host_keys(known_hosts)
    try :
        ssh.connect(args[1], username=args[0])
    except paramiko.AuthenticationException :
        passwd = raw_input("Password: ")
        ssh.connect(args[1], username=args[0], password=passwd)
    stdin, stdout, stderr = ssh.exec_command("~/echo_test.py dummy -t")
    if stdin.channel.closed == False :
        # adding '\n' as a workaround for the moment
        stdin.write(raw_input("Enter something: ") + '\n')
        stdin.flush()
        if stdout.channel.closed == False :
            print "Inverted:", stdout.readline()
    else :
        if stderr.channle.closed == False :
            for line in stderr.readlines() :
                print >> sys.stderr, line
    ssh.close()

def _exec_to() :
    import reverse_echo
    reverse_echo.reverse_echo()

def _build_arg_parser() :
    parser = argparse.ArgumentParser(description="echo test script", prog="echo_test")
    parser.add_argument("host", action="store", default=None, help="[user@]host")
    parser.add_argument("-f", "--from", action="store_true", default=None, help="echo source", dest="from_v")
    parser.add_argument("-t", "--to", action="store_true", default=None, help="echo destination")
    return parser

if __name__ == "__main__" :
    parser = _build_arg_parser()
    args = parser.parse_args(sys.argv[1:])
    host = args.host.split('@')
    if len(host) < 1 or len(host) > 2 :
        print parser.print_help()
        exit(1)
    if len(host) == 1 :
        import getpass
        host = getpass.getuser(), host[0]

    if args.from_v == True :
        _exec_from(host)
        exit(0)
    if args.to == True :
        _exec_to()
        exit(0)
    exit(1)
