from paramiko import WarningPolicy, SSHException
from binascii import hexlify

class SSHWarningPolicy(WarningPolicy) :
    def missing_host_key(self, client, hostname, key) :
        answer = raw_input('The authenticity of host {0} cannot be established. '
                           '{1} key fingerprint is {2}.\n'
                           'Are you sure you want to continue connecting (yes/no)? ' \
                           .format(hostname, key.get_name(), hexlify(key.get_fingerprint())))
        if answer == 'yes' :
            return True
        else :
            raise SSHException('Rejecting host ' + hostname)
