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
import os
import os.path
import json
import numpy as np
import atexit

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

with open(os.path.join(args.output_path, "config.in"), 'a+') as logfd:
    json.dump({
        'config': config,
        'args': vars(args)
    },
    logfd)

bench_config = config.get('smalliobenchfs', {})
ceph_config = config.get('ceph', {})
analysis_config = config.get('analysis', {})

LOG_FILE_NAME = "smalliobench_output.log"
log_file = os.path.join(args.output_path, LOG_FILE_NAME)

FIFO_NAME = "ops.fifo"
fifo_file = os.path.join(args.output_path, FIFO_NAME)

OUTPUT_NAME = "output.tsv"
output_file = os.path.join(args.output_path, OUTPUT_NAME)

SUMMARY_NAME = "summary.json"
summary_file = os.path.join(args.output_path, SUMMARY_NAME)


def process_log_file(fd):
    skip = analysis_config.get('skip_time', 0)
    bsize = analysis_config.get('time_bucket', 1)
    with open(output_file, 'a+') as ofd:
        l1 = fd.readline()
        start = json.loads(l1)['start']
        last = start
        recent_commit = []
        recent_apply = []
        ps = []
        for line in fd.xreadlines():
            val = json.loads(line)
            t = val['start']

            if val['type'] == 'write_applied':
                recent_apply += [val['latency']]
            elif val['type'] == 'write_committed':
                recent_commit += [val['latency']]

            if t - last > bsize and len(recent_apply) > 0 and len(recent_commit) > 0:
                avg_apply = sum(recent_apply)/len(recent_apply)
                npc_apply = np.percentile(recent_apply, 99)
                avg_commit = sum(recent_commit)/len(recent_commit)
                npc_commit = np.percentile(recent_commit, 99)
                iops = float(len(recent_apply)) / (t - last)
                print t - start, avg_apply, npc_apply, avg_commit, npc_commit, iops
                print >>ofd, t - start, avg_apply, npc_apply, avg_commit, npc_commit, iops
                if t - start > skip:
                    ps += [(t-start, avg_apply, npc_apply, avg_commit, npc_commit, iops)]
                last = t
                recent_apply = []
                recent_commit = []
        def project(ind, l):
            return [x[ind] for x in l]
        avg_apply = np.array(project(1, ps))
        nn_apply_latencies = np.array(project(2, ps))
        avg_commit = np.array(project(3, ps))
        nn_commit_latencies = np.array(project(4, ps))
        iops = np.array(project(5, ps))
        return {
            '99_latency_stddev_micro_apply': np.std(nn_apply_latencies) * (10**6),
            '99_latency_avg_micro_apply': np.mean(nn_apply_latencies) * (10**6),
            '99_latency_stddev_micro_commit': np.std(nn_commit_latencies) * (10**6),
            '99_latency_avg_micro_commit': np.mean(nn_commit_latencies) * (10**6),
            'stddev_avg_latency_micro_apply': np.std(avg_apply) * (10**6),
            'stddev_avg_latency_micro_commit': np.std(avg_commit) * (10**6),
            'avg_latency_micro_apply': np.mean(avg_apply) * (10**6),
            'avg_latency_micro_commit': np.mean(avg_commit) * (10**6),
            'throughput_stddev': np.std(iops),
            'throughput_avg': np.mean(iops),
        }
        
proc = None
os.mkfifo(fifo_file)
def on_exit():
    try:
        proc.kill()
    except:
        pass
    try:
        os.unlink(fifo_file)
    except:
        pass
atexit.register(on_exit)

argl = [args.smalliobench_path]
argl += ['--filestore-path', args.filestore_path]
argl += ['--journal-path', args.journal_path]
argl += ['--op-dump-file', fifo_file]

def strify(x):
    if type(x) == float:
        return "%.12f"%(x,)
    else:
        return str(x)

for arg, val in bench_config.iteritems():
    argl += ['--' + str(arg), strify(val)]

for arg, val in ceph_config.iteritems():
    argl += ['--' + str(arg), strify(val)]
        
try:
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
