This is a bandwidth emulation script that is able to enforce specific network bandwidth behavior in the server it is running on. The goal is to enable the user to run experiments that emulate real-world cloud network behavior in local/private clusters. This gives the user the possibility to study the interaction between real-world applications and cloud network performance variability.

Types of emulation:
1. Token-buckets, such as Amazon EC2 uses in instances like c5.xlarge, m5.xlarge etc.
2. The A-H variability scenarios for gigabit networks identified in Figure 1 of the work by Ballani et al. [1]


Dependencies:
1. psutil
2. wondershaper [needs sudo rights to run properly] (https://github.com/magnific0/wondershaper.git)

References:
[1] Ballani, Hitesh, Paolo Costa, Thomas Karagiannis, and Ant Rowstron. "Towards predictable datacenter networks." In ACM SIGCOMM computer communication review, vol. 41, no. 4, pp. 242-253. ACM, 2011.
