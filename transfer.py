import os
import sys
import time
import socket
import error

def _print_progress(p, file_name, sent, size, time_elapsed) :
    # progress line format
    # file name ==========> percentage size speed time
    import math
    # TODO: get real line width. Currently
    # no unified way between unix and windows exists.
    line_width = 80
    size_width = 8 # xxx.xxXB
    speed_width = 10 # xxx.xxXB/s
    time_width = 6 # mmm:ss
    file_width = int(math.floor(line_width / 3.0))
    spaces = 4
    bar_width = line_width - file_width - size_width - \
                speed_width - time_width - spaces

    percent = float(sent) / size if size > 0 else 1.0
    actual_bar_width = int(math.ceil((bar_width - 5) * percent))
    bar = '=' * (actual_bar_width - 1)
    bar += '>' if percent < 1.0 else '='
    bar += ' ' * (bar_width - 5 - len(bar))
    bar += ' {0: >4.0%}'.format(percent)

    size_mark = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    mark_index = 0
    sent_bytes = sent
    while sent_bytes >= 1000.0 :
        if mark_index == (len(size_mark) - 1) :
            break
        sent_bytes /= 1024.0
        mark_index += 1
    sent_str = '{0: >6.2f}{1: >2s}'.format(round(sent_bytes, 2), size_mark[mark_index])

    if time_elapsed > 0.0 :
        min_elapsed = time_elapsed / 60
        sec_elapsed = time_elapsed % 60
        time_str = '{0: >3d}:{1:02d}'.format(int(min_elapsed), int(sec_elapsed))

        mark_index = 0
        speed = sent / time_elapsed
        while speed >= 1000.0 :
            if mark_index == (len(size_mark) - 1) :
                break
            speed /= 1024.0
            mark_index += 1
        speed_str = '{0: >6.2f}{1: >2s}/s'.format(round(speed, 2), size_mark[mark_index])
    else :
        time_str = '---:--'
        speed_str = '---.-- B/s'

    # build line format
    line_format = '{0: <' + str(file_width) + 's} {1:s} {2:s} {3:s} {4:s}'
    line = line_format.format(file_name[:file_width], bar[:bar_width],
                              sent_str[:size_width], speed_str[:speed_width],
                              time_str[:time_width])
    line += '\r' if percent < 1.0 else '\n'
    p.write(line)
    p.flush()

def _send_file_data(i, progress, file_path, size, seek) :
    # data transfer starts right after C command
    fo = open(file_path, 'rb')
    fo.seek(seek)
    start = time.time()
    bytes_to_send = size - seek
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = fo.read(chunk)
        if len(buf) :
            i.write(buf)
            i.flush()
            bytes_to_send -= len(buf)
        if progress is not None :
            _print_progress(progress, os.path.basename(file_path),
                            size - bytes_to_send, size,
                            time.time() - start)
        if bytes_to_send <= 0 :
            break
    fo.close()

def _recv_file_data(o, progress, file_path, size, seek) :
    mode = 'wb' if seek == 0 else 'r+b'
    fo = open(file_path, mode)
    fo.seek(seek)
    start = time.time()
    bytes_to_recv = size - seek
    while True :
        if bytes_to_recv < 4096 :
            chunk = bytes_to_recv
        else :
            chunk = 4096
        buf = o.read(chunk)
        if len(buf) :
            fo.write(buf)
            bytes_to_recv -= len(buf)
        if progress is not None :
            _print_progress(progress, os.path.basename(file_path),
                            size - bytes_to_recv, size,
                            time.time() - start)
        if bytes_to_recv <= 0 :
            fo.flush()
            break
    fo.close()

def _calculate_hash(file_path, size) :
    from hashlib import sha1
    sha = sha1()

    fo = open(file_path, 'rb')
    bytes_to_hash = size
    while bytes_to_hash > 0 :
        if bytes_to_hash < 4096 :
            chunk = bytes_to_hash
        else :
            chunk = 4096
        buf = fo.read(chunk)
        sha.update(buf)
        bytes_to_hash -= len(buf)
    fo.close()
    return sha.hexdigest()

def send_file(i, o, e, progress, file_path, preserve, check_hash) :
    stat = os.stat(file_path)

    # command: touch
    if preserve :
        i.write('T{0:d} 0 {1:d} 0\n'.format(stat.st_mtime, stat.st_atime))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            e.write(o.readline())
            return error.E_UNK

    mode = stat.st_mode & 0x1FF
    # command: sending file
    i.write('C{0:0=4o} {1:d} {2:s}\n'.format(mode, stat.st_size, os.path.basename(file_path)))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        e.write(o.readline())
        return error.E_UNK

    seek = 0
    if check_hash :
        # wait for H command
        # format: H<hash> <size>
        command = o.readline()
        if len(command) == 0 or command[0] != 'H' :
            i.write('\2')
            i.write(error.errstr(error.E_UNK))
            i.flush()
            return error.E_UNK
        hash_str, file_size = command[1:-1].split(' ', 1)
        file_size = int(file_size)
        if len(hash_str) != 40 or file_size < 0 :
            i.write('\2')
            i.write(error.errstr(error.E_FMT))
            i.flush()
            return error.E_FMT
        i.write('\0')
        i.flush()

        if file_size > 0 and file_size <= stat.st_size :
            # part of the file might already be at the destination
            # check if the parts are the same
            local_hash = _calculate_hash(file_path, file_size)
            if hash_str == local_hash :
                seek = file_size

        # command: hash ack
        # return 0 hash and seek value
        i.write('H{0:40s} {1:d}\n'.format('0' * 40, seek))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            e.write(o.readline())
            return error.E_UNK

    _send_file_data(i, progress, file_path, stat.st_size, seek)
    # data transfer end
    i.write('\0')
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        e.write(o.readline())
        return error.E_TFR

    return error.E_OK

def send_dir(i, o, e, progress, dir_path, preserve, check_hash) :
    name = os.path.basename(dir_path)
    stat = os.stat(dir_path)

    # command: touch
    if preserve :
        i.write('T{0:d} 0 {1:d} 0\n'.format(stat.st_mtime, stat.st_atime))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            e.write(o.readline())
            return error.E_UNK

    mode = stat.st_mode & 0x1FF
    # command: sending directory
    i.write('D{0:0=4o} 0 {1:s}\n'.format(mode, name))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        e.write(o.readline())
        return error.E_UNK

    items = os.listdir(dir_path)
    ret = error.E_OK
    for it in items :
        p = os.path.join(dir_path, it)
        if os.path.isdir(p) :
            ret = send_dir(i, o, e, progress, p, preserve, check_hash)
        elif os.path.isfile(p) :
            ret = send_file(i, o, e, progress, p, preserve, check_hash)
        if ret != error.E_OK :
            return ret

    i.write('E\n');
    i.flush();
    ret = o.read(1)
    if ret != '\0' :
        e.write(o.readline())
        return error.E_UNK

    return error.E_OK

def send(i, o, e, progress, paths, preserve, check_hash) :
    try :
        # check if receiving end is ready
        ret = o.read(1)
        if ret != '\0' :
            e.write(o.readline())
            return error.E_RDY

        ret = error.E_OK
        for p in paths :
            if os.path.isfile(p) :
                ret = send_file(i, o, e, progress, p, preserve, check_hash)
            elif os.path.isdir(p) :
                ret = send_dir(i, o, e, progress, p, preserve, check_hash)
            if ret != error.E_OK :
                break
        return ret
    except socket.error as socket_ex :
        # opposite side closed prematurely
        e.write(str(socket_ex) + '\n')
        ret = o.read(1)
        if len(ret) > 0 and ret != '\0' :
            e.write(o.readline())
        e.flush()
        return error.E_TFR
    except Exception as ex :
        i.write('\2')
        i.write(str(ex) + '\n')
        i.flush()
        return error.E_TFR

def recv_file_dir_or_end(i, o, e, progress, target_dir, preserve, check_hash) :
    command = o.readline()
    if len(command) == 0 :
        return error.E_END # end of transfer ?
    if command[0] == 'E' :
        i.write('\0')
        i.flush()
        return error.E_END # end of directory
    times = None
    if preserve :
        if command[0] == 'T' :
            times = command[1:-1].split(' ', 3)
            if len(times) != 4 :
                i.write('\2')
                i.write(error.errstr(error.E_UNK))
                i.flush()
                return error.E_UNK
            # ready tuple for utime (atime, mtime)
            times = (int(times[2]), int(times[0]))
            i.write('\0')
            i.flush()
            command = o.readline()
            if len(command) == 0 : # should never happen
                i.write('\2')
                i.write(error.errstr(error.E_UNK))
                i.flush()
                return error.E_UNK
        else :
            i.write('\2')
            i.write(error.errstr(error.E_UNK))
            i.flush()
            return error.E_UNK
    ret = error.E_UNK
    if command[0] == 'C' :
        i.write('\0')
        i.flush()
        ret = recv_file(i, o, e, progress, target_dir, command,
                        preserve, times, check_hash)
    elif command[0] == 'D' :
        i.write('\0')
        i.flush()
        ret = recv_dir(i, o, e, progress, target_dir, command,
                       preserve, times, check_hash)
    else :
        i.write('\2')
        i.write(error.errstr(ret))
        i.flush()
    return ret

def recv_file(i, o, e, progress, target_dir, command, preserve, times, check_hash) :
    # TODO: add regex check on the command format
    # ignore the '\n' at the end
    mode, size, path = command[1:-1].split(' ', 2)
    size = int(size)
    mode = int(mode, 8)

    if os.path.isdir(target_dir) :
        file_path = os.path.join(target_dir, path)
    else :
        file_path = target_dir

    seek = 0
    if check_hash :
        # command: hash check
        if os.path.exists(file_path) :
            file_size = os.stat(file_path).st_size
            hash_str = _calculate_hash(file_path, file_size)
        else :
            file_size = 0
            hash_str = '0' * 40
        i.write('H{0:40s} {1:d}\n'.format(hash_str, file_size))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            e.write(o.readline())
            return error.E_UNK

        # wait for H command
        command = o.readline()
        if len(command) == 0 or command[0] != 'H' :
            i.write('\2')
            i.write(error.errstr(error.E_UNK))
            i.flush()
            return error.E_UNK
        hash_str, seek = command[1:-1].split(' ', 1)
        seek = int(seek)
        if len(hash_str) != 40 or seek < 0 :
            i.write('\2')
            i.write(error.errstr(error.E_FMT))
            i.flush()
            return error.E_FMT
        i.write('\0')
        i.flush()

    _recv_file_data(o, progress, file_path, size, seek)
    os.chmod(file_path, mode)
    if preserve :
        os.utime(file_path, times)
    ret = o.read(1)
    if ret != '\0' :
        i.write('\2')
        i.write(error.errstr(error.E_TFR))
        i.flush()
        return error.E_TFR
    else :
        i.write('\0')
        i.flush()

    return error.E_OK

def recv_dir(i, o, e, progress, dir_path, command, preserve, times, check_hash) :
    # ignore the '\n' at the end
    mode, size, name = command[1:-1].split(' ', 2)
    mode = int(mode, 8)

    # TODO: check if sending dir is the same
    new_dir_path = os.path.join(dir_path, name)
    if not os.path.exists(new_dir_path) :
        os.mkdir(new_dir_path, mode)
    else :
        os.chmod(new_dir_path, mode)

    while True :
        ret = recv_file_dir_or_end(i, o, e, progress, new_dir_path, preserve, check_hash)
        if ret == error.E_END :
            if preserve :
                os.utime(new_dir_path, times)
            return error.E_OK
        if ret != error.E_OK :
            if preserve :
                os.utime(new_dir_path, times)
            return ret

def recv(i, o, e, progress, dir_path, preserve, check_hash) :
    try :
        if not os.path.exists(os.path.dirname(dir_path)) :
            i.write('\2')
            i.write(error.errstr(error.E_MIS))
            i.flush()
            return error.E_MIS
        else :
            i.write('\0')
            i.flush()

        while True :
            ret = recv_file_dir_or_end(i, o, e, progress, dir_path, preserve, check_hash)
            if ret == error.E_END :
                return error.E_OK
            if ret != error.E_OK :
                return ret
    except socket.error as socket_ex :
        # opposite side closed prematurely
        e.write(str(socket_ex) + '\n')
        ret = o.read(1)
        if len(ret) > 0 and ret != '\0' :
            e.write(o.readline())
        e.flush()
        return error.E_TFR
    except Exception as ex :
        i.write('\2')
        i.write(str(ex) + '\n')
        i.flush()
        return error.E_TFR
