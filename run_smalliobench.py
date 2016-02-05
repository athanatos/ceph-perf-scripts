#!/usr/bin/python
"""
smalliobench tester script

Takes a yaml file describing the test to run:

journal:
    size: <size>
smalliobenchfs: <options>
"""
import argparse
import yaml
import subprocess
import sys
import tempfile
import os
import os.path
import json
import numpy as np
import atexit
import time

parser = argparse.ArgumentParser(
    description='Run smalliobench'
)
parser.add_argument(
    '--config',
    type=str,
    required=True,
)
parser.add_argument(
    '--smalliobench-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--filestore-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--journal-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--output-path',
    type=str,
    required=True,
)

args = parser.parse_args()
print args

config = None
try:
    configstr = ""
    for confpath in args.config.split(','):
        with open(confpath) as config_file:
            configstr += config_file.read()
    print configstr
    config = yaml.load(configstr)
except Exception as e:
    print "Error opening config {config}: {error}".format(
        config=args.config,
        error=e)
    sys.exit(1)

bench_config = config.get('smalliobenchfs', {})
ceph_config = config.get('ceph', {})

def write_ceph_conf(config):
    ret = "[global]\n"
    for (key, value) in config.iteritems():
        print "\t{key} = {value}".format(
            key=key,
            value=value)
    return ret

LOG_FILE_NAME = "log_output.log"
log_file = os.path.join(args.output_path, LOG_FILE_NAME)

FIFO_NAME = "ops.fifo"
fifo_file = os.path.join(args.output_path, FIFO_NAME)

OUTPUT_NAME = "output.tsv"
output_file = os.path.join(args.output_path, OUTPUT_NAME)

SUMMARY_NAME = "summary.tsv"
summary_file = os.path.join(args.output_path, SUMMARY_NAME)


def process_log_file(fd):
    with open(output_file, 'a+') as ofd:
        l1 = fd.readline()
        start = json.loads(l1)['start']
        last = start
        recent = []
        ps = []
        for line in fd.xreadlines():
            val = json.loads(line)
            if val['type'] != 'write_applied':
                continue
                t = val['start']
                recent += [val['latency']]
                if t - last > 1:
                    avg = sum(recent)/len(recent)
                npc = np.percentile(recent, 99)
                iops = len(recent) / (t - last)
                print >>ofd, t-start, avg, npc, iops
                ps += [(t, avg, npc, iops)]
                last = t
            current = []
        def project(ind, l):
            return [x[ind] for x in l]
        nn_latencies = np.array(project(2, ps))
        tpt = np.array(project(3, ps))
        return {
            '99_latency_stddev_micro': np.std(nn_latencies) * (10**6),
            '99_latency_avg_micro': np.mean(nn_latencies) * (10**6),
            'avg_latency_micro': np.mean(project(1, ps)) * (10**6),
            'throughput_stddev': np.std(tpt),
            'throughput_avg': np.mean(tpt),
        }
        

try:
    logfd = open(log_file, 'w')
except Exception, e:
    print "Error opening log file: ", e
    sys.exit(1)

proc = None
def on_exit():
    try:
        proc.kill()
    except:
        pass
atexit.register(on_exit)

with tempfile.NamedTemporaryFile() as ceph_conf_file:
    ceph_conf_file.write(write_ceph_conf(ceph_config))
    argl = [args.smalliobench_path]
    argl += ['--filestore-path', args.filestore_path]
    argl += ['--journal-path', args.journal_path]
    argl += ['--op-dump-file', fifo_file]

    for arg, val in bench_config.iteritems():
        argl += ['--' + str(arg), str(val)]

    for arg, val in ceph_config.iteritems():
        argl += ['--' + str(arg), str(val)]

    try:
        os.mkfifo(fifo_file)
        proc = subprocess.Popen(
            argl,
            stdout = open(log_file, 'a+'),
            stderr = open(log_file, 'a+'))

        ret = None
        with open(fifo_file, 'r') as fifo_fd:
            ret = process_log_file(fifo_fd)
        with open(summary_file, 'a+') as sfd:
            json.dump(ret, sfd)
        proc.wait()
    except Exception, e:
        print "Error starting smalliobench: ", e
        sys.exit(1)
