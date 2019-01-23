import logging
import time
import json
import re
import asyncio
import subprocess

"""
# https://www.kernel.org/doc/Documentation/filesystems/proc.txt

- user: normal processes executing in user mode
- nice: niced processes executing in user mode
- system: processes executing in kernel mode
- idle: twiddling thumbs
- iowait: In a word, iowait stands for waiting for I/O to complete. But there
are several problems:
1. Cpu will not wait for I/O to complete, iowait is the time that a task is
waiting for I/O to complete. When cpu goes into idle state for
outstanding task io, another task will be scheduled on this CPU.
2. In a multi-core CPU, the task waiting for I/O to complete is not running
on any CPU, so the iowait of each CPU is difficult to calculate.
3. The value of iowait field in /proc/stat will decrease in certain
conditions.
So, the iowait is not reliable by reading from /proc/stat.
- irq: servicing interrupts
- softirq: servicing softirqs
- steal: involuntary wait
- guest: running a normal guest
- guest_nice: running a niced guest


The "intr" line gives counts of interrupts  serviced since boot time, for each of the  possible system interrupts.
The first column  is the  total of  all interrupts serviced  including  unnumbered  architecture specific interrupts;
each  subsequent column is the total for that particular numbered interrupt. Unnumbered interrupts are not shown, only
summed into the total.

The "ctxt" line gives the total number of context switches across all CPUs.

The "btime" line gives  the time at which the  system booted, in seconds since the Unix epoch. The "processes" line
gives the number  of processes and threads created, which includes (but  is not limited  to) those  created by  calls to
the  fork() and clone() system calls.

The "procs_running" line gives the total number of threads that are running or ready to run (i.e., the total number of
runnable threads).

The  "procs_blocked" line gives  the  number of  processes currently blocked, waiting for I/O to complete.

The "softirq" line gives counts of softirqs serviced since boot time, for each of the possible system softirqs. The
first column is the total of all softirqs serviced; each subsequent column is the total for that particular softirq.
cpu  321507 585 279900 6603961 1229 0 88695 0 0 0
cpu0 165558 346 154018 3322043 564 0 12756 0 0 0
cpu1 155949 238 125882 3281917 665 0 75938 0 0 0
intr 23551482 66 10 0 0 1836 0 0 0 0 0 0 0 156 0 0 0 0 0 0 5306481 921344 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
ctxt 38573952
btime 1547958699
processes 948814
procs_running 1
procs_blocked 0
softirq 32318098 0 5263759 10052 16639413 27547 0 74317 4237395 0 6065615

"""
logging.basicConfig(format='%(levelname)s - %(filename)s:L%(lineno)d pid=%(process)d - %(message)s')
logger = logging.getLogger('agent')


RESOLUTION = 1. # Seconds


def get_float(key, default=1.):
    return float(redis_cli.get(key) or default) or default


def _parse_raw_stats(raw_stats):
    return [int(_) for _ in re.split("\s+", raw_stats)[1:]]


def _parse_cpu_stats(cpu_stats):
    user, nice, system, idle, io_wait, irq, soft_irq, steal, guest, guest_nice = cpu_stats
    user = user - guest
    nice = nice - guest_nice
    total_idle = idle + io_wait
    total_system = system + irq + soft_irq
    total_virtual = guest + guest_nice
    total = float(user + nice + total_system + total_idle + steal + total_virtual)
    return {'user': user, 'nice': nice, 'total_idle': total_idle, 'total_system': total_system,
            'total_virtual': total_virtual, 'total': total, 'io_wait': io_wait}


def parse_process_statistics():
    raw_stats = subprocess.check_output('cat /proc/stat', shell=True).decode('utf-8').split("\n")
    for line in raw_stats:
        if line.startswith('cpu '):
            cpu_stats = _parse_raw_stats(line)
        elif line.startswith('intr'):
            hard_interrupts = _parse_raw_stats(line)[0]
        elif line.startswith('softirq'):
            soft_interrupts = _parse_raw_stats(line)[0]
        elif line.startswith('ctxt'):
            context_switches = _parse_raw_stats(line)[0]

        return { 't_ms': time.time() * 1000.,
            'cpu': _parse_cpu_stats(cpu_stats),
            'hard_interrupts': hard_interrupts,
            'soft_interrupts': soft_interrupts,
            'context_switches': context_switches}


def write_process_statistics(stats):
    with open('proc-stat.log', 'a+') as fp:
        fp.write(json.dumps(stats) + "\n")
        fp.flush()


@asyncio.coroutine
def log_host_statistics():
    while True:
        stats = parse_process_statistics()
        write_process_statistics(stats)
        yield from asyncio.sleep(RESOLUTION)


def main():
    loop = asyncio.get_event_loop()
    loop.create_task(log_host_statistics())
    loop.run_forever()


if __name__ == "__main__":
    main()