#  SULIVAN : Synergistic Understanding and Learning with Interactive robotics,
#            computer Vision, Augmented reality, and Neural networks
#  Copyright 2026 PNU IRLab All rights reserved.
#
#  Made by Jibaek Oh (jibaek8809@pusan.ac.kr), Jihoon Yoon (face5921@pusan.ac.kr),
#          HyeonUk Kang (hwkang0318@pusan.ac.kr)

# Scenario state
STOPPED  = 0
RUNNING  = 1
PAUSED   = 2
CHANGING = 3

# Work process
NOT_STARTED = 0
WORKING     = 1
COMPLETED   = 2

# RPS(가위바위보) special state (확장용, 실제 코어 로직에서는 아래 상수 미사용 가능)
RPS_COUNTDOWN = 10
RPS_PICKING   = 11
RPS_TIE       = 12
RPS_WINNER    = 13