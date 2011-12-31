#!/usr/bin/python

E_OK  = 0           # everything is ok
E_END = 1           # end of transfer
E_RDY = 2           # missing start signal
E_UNK = 3           # unknown command
E_TFR = 4           # transfer error
E_FMT = 5           # command format error

err_str = {E_OK :'No errors\n',
           E_END:'End of transfer/directory\n',
           E_RDY:'Receiving end not ready yet\n',
           E_UNK:'Protocol error\n',
           E_TFR:'Transfer error\n',
           E_FMT:'Wrong command format\n'}

def errstr(errno) :
    return err_str[errno]
