import logging
import json
import sys
import re
import asyncio
import subprocess
import threading

import redis


logging.basicConfig(format='%(levelname)s - %(filename)s:L%(lineno)d pid=%(process)d - %(message)s')
logger = logging.getLogger('agent')
lock = threading.Lock()
redis_cli = redis.StrictRedis('192.168.50.5', 6379)


RESOLUTION = .5 # Seconds


def get_float(key, default=1.):
    return float(redis_cli.get(key) or default) or default


def _parse_raw_generic_int_line(raw_stats):
    return [int(_) for _ in re.split("\s+", raw_stats)[1:]]


def _parse_raw_generic_str_line(raw_stats):
    return re.split("\s+", raw_stats)


def _parse_raw_meminfo_line(raw_line):
    row = re.split("\s+", raw_line.strip())
    if not row:
        return None, None, None
    label = row[0]
    value = int(row[1])
    unit = None
    if len(row) == 3:
        unit = row[2]
    return label, value, unit


def _parse_raw_network_line(raw_line, raw_labels):
    labels = _parse_raw_generic_str_line(raw_labels[1:])
    line = _parse_raw_generic_str_line(raw_line)
    values = [int(i) for i in line[1:-1]]
    interface_label = line[0]
    return {interface_label: {
        label: value for label, value in zip(labels[1:-1], values)}
    }


def _parse_cpu_stats(cpu_stats):
    user, nice, system, idle, io_wait, irq, soft_irq, steal, guest, guest_nice = cpu_stats
    user = user - guest
    nice = nice - guest_nice
    total_idle = idle + io_wait
    total_system = system + irq + soft_irq
    total_virtual = guest + guest_nice + steal
    total = float(user + nice + total_system + total_idle + total_virtual)
    return {'user': user, 'nice': nice, 'idle': total_idle, 'system': total_system,
            'virtual': total_virtual, 'total': total, 'io_wait': io_wait, 'nice': nice}


def parse_memory_statistics():
    """
    MemTotal:        1015812 kB
    MemFree:          302680 kB
    MemAvailable:     710420 kB
    Buffers:           51028 kB
    Cached:           468704 kB
    SwapCached:            0 kB
    Active:           422264 kB
    Inactive:         208204 kB
    Active(anon):     113856 kB
    Inactive(anon):     2488 kB
    Active(file):     308408 kB
    Inactive(file):   205716 kB
    Unevictable:        3652 kB
    Mlocked:            3652 kB
    SwapTotal:             0 kB
    SwapFree:              0 kB
    Dirty:                 0 kB
    Writeback:             0 kB
    AnonPages:        114456 kB
    Mapped:            40100 kB
    Shmem:              3184 kB
    Slab:              57308 kB
    SReclaimable:      42668 kB
    SUnreclaim:        14640 kB
    KernelStack:        2336 kB
    PageTables:         5588 kB
    NFS_Unstable:          0 kB
    Bounce:                0 kB
    WritebackTmp:          0 kB
    CommitLimit:      507904 kB
    Committed_AS:     446268 kB
    VmallocTotal:   34359738367 kB
    VmallocUsed:           0 kB
    VmallocChunk:          0 kB
    HardwareCorrupted:     0 kB
    AnonHugePages:         0 kB
    CmaTotal:              0 kB
    CmaFree:               0 kB
    HugePages_Total:       0
    HugePages_Free:        0
    HugePages_Rsvd:        0
    HugePages_Surp:        0
    Hugepagesize:       2048 kB
    DirectMap4k:       47040 kB
    DirectMap2M:     1001472 kB
    """
    meminfo = {}
    raw_stats = subprocess.check_output('cat /proc/meminfo', shell=True).decode('utf-8').strip().split("\n")
    for line in raw_stats:
        label, value, unit = _parse_raw_meminfo_line(line)
        meminfo[label] = {'value': value, 'unit': unit}
    return meminfo


def parse_process_statistics():
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
    intr 23551482 66 10 0 0 1836 0 0 0 0 0 0 0 156 0 0 0 0 0 0 5306481 921344 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
    ctxt 38573952
    btime 1547958699
    processes 948814
    procs_running 1
    procs_blocked 0
    softirq 32318098 0 5263759 10052 16639413 27547 0 74317 4237395 0 6065615
    """
    raw_stats = subprocess.check_output('cat /proc/stat', shell=True).decode('utf-8').split("\n")
    for line in raw_stats:
        if line.startswith('cpu '):
            cpu_stats = _parse_raw_generic_int_line(line)
        elif line.startswith('intr'):
            hard_interrupts = _parse_raw_generic_int_line(line)[0]
        elif line.startswith('softirq'):
            soft_interrupts = _parse_raw_generic_int_line(line)[0]
        elif line.startswith('ctxt'):
            context_switches = _parse_raw_generic_int_line(line)[0]

    return {'cpu': _parse_cpu_stats(cpu_stats),
            'hard_interrupts': hard_interrupts,
            'soft_interrupts': soft_interrupts,
            'context_switches': context_switches}


def parse_network_statistics():
    """
    Iface   MTU Met   RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP TX-OVR Flg
    enp0s3     1500 0   1010273      0      0 0        641797      0      0      0 BMRU
    enp0s8     1500 0  11738051      0      0 0       3444984      0      0      0 BMRU
    lo        65536 0   1455864      0      0 0       1455864      0      0      0 LRU
    """
    raw_stats = subprocess.check_output('ifconfig -s', shell=True).decode('utf-8').split("\n")
    labels = raw_stats[0]
    ifconfig = {}
    for raw_network_line in raw_stats[1:]:
        ifconfig.update(_parse_raw_network_line(raw_network_line, labels))
    return ifconfig


async def daemonize():
    while True:
        process_stats = parse_process_statistics()
        network_stats = parse_network_statistics()
        memory_stats = parse_memory_statistics()
        with redis_cli.lock('statlock', timeout=0.5, blocking_timeout=10):
            redis_cli.set('host', json.dumps({
                'process': process_stats,
                'network': network_stats,
                'memory': memory_stats
            }, sort_keys=True, indent=2))
        sys.stdout.write('.')
        sys.stdout.flush()
        await asyncio.sleep(RESOLUTION)


def main():
    print('starting event loop')

    def stop_on_exception(loop, context):
        loop.default_exception_handler(context)
        loop.stop()

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(stop_on_exception)
    loop.create_task(daemonize())
    loop.run_forever()


if __name__ == "__main__":
    main()
