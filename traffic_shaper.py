import sys
import psutil
import time
import datetime
import subprocess
import socket
from subprocess import Popen, PIPE
import signal
import numpy as np

# wondershaper path
WONDERSHAPER = "/cm/shared/package/utils/bin/wondershaper"

# bandwidth distributions for the old gigabit configuration
BW_DISTRIBUTION = {
    'A': [60.344, 149.999, 263.793, 384.482, 653.448],
    'B': [308.620, 503.448, 646.551, 789.655, 991.379],
    'C': [555.172, 841.379, 901.724, 934.482, 946.551],
    'D': [112.068, 137.931, 170.689, 199.999, 298.275],
    'E': [774.137, 824.137, 851.724, 855.172, 858.620],
    'F': [268.965, 729.310, 777.586, 820.689, 925.862],
    'G': [334.482, 529.310, 537.931, 600.000, 624.137],
    'H': [136.206, 425.862, 525.862, 660.344, 998.275],
    '1gbps': [1050.0, 1050.0, 1050.0, 1050.0, 1050.0],
    '10gbps': [10500.0, 10500.0, 10500.0, 10500.0, 10500.0]
}
# the interval at which bandwidth changes for the A-H Ballani usecases, measured in seconds
VARIABILITY_INTERVAL = 5

# defines the maximum allowed bandwidth, measured in Mbps
MAX_BW = 10500 # default 10 Gbit/s
#defines the min bw allowed
MIN_BW = 1400 # default 1Gbit/s
#defines the monitoring interval, measured in seconds
MONITORING_INTERVAL = 1
# the budget, measured in GBit
BUDGET = 10000
# replenishing rate, measured in Gbit per second
REPL_RATE = 0.99

def get_GBit_sent(t1, t2):
    return 8 * (t2 - t1) / (1000 * 1000 * 1000.0)

def limit_bw(bw_limit):
    # call wondershaper: first to reset, then to enforce
    Popen("sudo " + WONDERSHAPER + " -c -a ib0", shell=True).communicate() 
    command = "sudo {} -u {} -d {} -a ib0".format(WONDERSHAPER, int(bw_limit * 1000), int(MAX_BW * 1000))
    Popen(command, shell=True).communicate()
    print("bw has been limited to {} Mbps".format(bw_limit))    
    
# determine in how much time we spend the budget
# given our current performance (bw)    
def project_bw(sent_data, time, crnt_bw):
    crnt_effective_bw = sent_data / time
    time_left = TIME_WINDOW - time
    data_left = MAX_TRAFFIC - sent_data
    
    # data is in MBytes, so we need to transform to Mbits
    affordable_bw = (data_left / time_left) * (8)

    print("effective_bw = {}, affordable_bw = {}".format(crnt_effective_bw, affordable_bw))
    
    if crnt_effective_bw > affordable_bw:
        return affordable_bw
    else:
        return crnt_bw

def write_info(log_file, traffic, budget, bw):
    message = "{},{},{}\n".format(traffic, budget, bw)
    log_file.write(message)
    log_file.flush()
    print("crnt traffic = {}, crnt budget = {}, crnt bw = {}".format(traffic, budget, bw))

# enforce the traffic as in AWS
def emulate_aws(initial_budget):
    crnt_budget = initial_budget
    # get the initial values
    initial_traffic = psutil.net_io_counters(pernic=True)["ib0"]
    # continuously compute the shaping logic
    crnt_bw = MAX_BW
    prev_bw = crnt_bw
    # init the output file
    date_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H%M%S')
    hostname = socket.gethostname()
    log_file = open(hostname + "-" + date_time + ".csv", "w")
 
    while True:
        time.sleep(MONITORING_INTERVAL)        
        # add tokens to the budget
        crnt_budget = min(BUDGET, crnt_budget + REPL_RATE)
        if (crnt_bw == MIN_BW) and (crnt_budget > 2):
            limit_bw(MAX_BW)
            crnt_bw = MAX_BW
        # measure what happened in the network
        crnt_traffic = psutil.net_io_counters(pernic=True)["ib0"]
        # check the current traffic
        recent_traffic = get_GBit_sent(initial_traffic.bytes_sent, crnt_traffic.bytes_sent)
        #update
        crnt_budget = max(0, crnt_budget - recent_traffic)
        initial_traffic = crnt_traffic
        #check whether we should limit
        if (crnt_bw == MAX_BW) and (crnt_budget == 0):
            limit_bw(MIN_BW)
            crnt_bw = MIN_BW
        #write data 
        write_info(log_file, recent_traffic, crnt_budget, crnt_bw)

# generate a number in the given distribution 
def get_bw_value(distribution):
    # this generates a number between 1 and 4, which represents the current quartile
    # r_bound is the upper bound of the quartile
    r_bound = np.random.randint(1, 5)
    # l_bound is the lower bound of the quartile
    l_bound = r_bound - 1
    # get the actual values from the distribution
    low = distribution[l_bound]
    high = distribution[r_bound]
    # get a value within the quartile
    return int(np.random.uniform(low, high + 1.0))

# emulate the old A-H gigabit distributions from Ballani
def emulate_gbit(scenario):
    # set the initial bw values
    distribution = BW_DISTRIBUTION[scenario]
    crnt_bw = get_bw_value(distribution)   
    #set the bw
    limit_bw(crnt_bw) 
    # get the initial traffic values
    initial_traffic = psutil.net_io_counters(pernic=True)["ib0"]
    # init the output file
    date_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H%M%S')
    hostname = socket.gethostname()
    log_file = open(hostname + "-" + date_time + ".csv", "w")
    while True:
        # sleep till we change the bw again
        time.sleep(VARIABILITY_INTERVAL)
        # measure what happened in the network
        crnt_traffic = psutil.net_io_counters(pernic=True)["ib0"]
        # check the current traffic
        recent_traffic = get_GBit_sent(initial_traffic.bytes_sent, crnt_traffic.bytes_sent)
        initial_traffic = crnt_traffic
        write_info(log_file, recent_traffic, 0, crnt_bw)
        #change the bw again
        crnt_bw = get_bw_value(distribution)
        limit_bw(crnt_bw)

# intercept the signal and stop the bw limitation
def handler(sign, frame):
    print("going to shutdown, stopping the bw limitation first...")
    Popen("sudo " + WONDERSHAPER + " -c -a ib0", shell=True).communicate()
    exit(0) 

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: traffic_shaper.py [aws | gbit] [initial budget | A-H setup]")
    else:
        # add handler for signal
        signal.signal(signal.SIGUSR1, handler)
        # limit the initial bandwidth
        limit_bw(MAX_BW)
        if sys.argv[1] == "aws":
            emulate_aws(int(sys.argv[2])) 
        elif sys.argv[1] == "gbit":
            emulate_gbit(sys.argv[2])
