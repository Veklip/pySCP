#!/usr/bin/python

from paramiko import WarningPolicy, SSHException
from binascii import hexlify

class SSHWarningPolicy(WarningPolicy) :
    def missing_host_key(self, client, hostname, key) :
        answer = raw_input('The authenticity of host %s cannot be established. '
                           '%s key fingerprint is %s.\n'
                           'Are you sure you want to continue connecting (yes/no)? ' \
                           % (hostname, key.get_name(), hexlify(key.get_fingerprint())))
        if answer == 'yes' :
            return True
        else :
            raise SSHException('Rejecting host %s' % hostname)
