import os
import sys
import time
import tempfile
import zipfile
import error
import transfer as tfr


def deploy(ssh):
    sys.stdout.write("Deploying pyscp on remote\n")

    stdin, stdout, stderr = ssh.exec_command("uname")
    while (not stdout.channel.exit_status_ready()):
        time.sleep(5. / 60.)  # 5s
    if (stdout.channel.recv_exit_status() != 0):
        sys.stderr.write(stderr.read(-1))
        return False
    # TODO: add MacOS and other Unix systems
    if ("Linux" not in stdout.read(-1)):
        sys.stderr.write("Deployment is supported only on Linux\n")
        return False

    tf = tempfile.NamedTemporaryFile(mode="wb", suffix=".zip", delete=True)
    pzf = zipfile.PyZipFile(tf, mode="w")
    pzf.writepy(os.path.dirname(sys.argv[0]))
    pzf.close()

    stdin, stdout, stderr = ssh.exec_command("scp -t /tmp/pyscp.zip")

    ret = tfr.send(stdin, stdout, sys.stderr, sys.stdout, [tf.name], False, False)
    if ret == error.E_OK or ret == error.E_END:
        return True
    else:
        sys.stderr.write(stderr.readline())
        return False
