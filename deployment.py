import os
import sys
import time
import tempfile
import zipfile
import error
import transfer as tfr


def _prepare_remote_dep_file(ssh):
    stdin, stdout, stderr = ssh.exec_command("mktemp --tmpdir 'pyscpXXXXXX.zip'")
    while (not stdout.channel.exit_status_ready()):
        time.sleep(.1)  # 100ms
    if (stdout.channel.recv_exit_status() != 0):
        sys.stderr.write(stderr.read(-1))
        return None
    tempfile = stdout.readline().strip()
    ssh.exec_command("chmod 0666 '{}'".format(tempfile))
    return tempfile


def deploy(ssh):
    sys.stdout.write("Deploying pyscp on remote\n")

    stdin, stdout, stderr = ssh.exec_command("uname")
    while (not stdout.channel.exit_status_ready()):
        time.sleep(5. / 60.)  # 5s
    if (stdout.channel.recv_exit_status() != 0):
        sys.stderr.write(stderr.read(-1))
        return None
    # TODO: add MacOS and other Unix systems
    if ("Linux" not in stdout.read(-1)):
        sys.stderr.write("Deployment is supported only on Linux\n")
        return None

    tf = tempfile.NamedTemporaryFile(mode="wb", suffix=".zip", delete=True)
    pzf = zipfile.PyZipFile(tf, mode="w")
    pzf.writepy(os.path.dirname(sys.argv[0]))
    pzf.close()

    remote_tempfile = _prepare_remote_dep_file(ssh)
    if (not remote_tempfile):
        return None

    stdin, stdout, stderr = \
        ssh.exec_command("scp -t '{}'".format(remote_tempfile))

    ret = tfr.send(stdin, stdout, sys.stderr, sys.stdout, [tf.name], False, False)
    if ret == error.E_OK or ret == error.E_END:
        return remote_tempfile
    else:
        sys.stderr.write(stderr.readline())
        return None
