# RL-Based Traffic Signal Control Process Diagram

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    URBAN TRAFFIC NETWORK                        │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │Intersection │    │Intersection │    │Intersection │         │
│  │    Agent    │◄──►│    Agent    │◄──►│    Agent    │         │
│  │             │    │             │    │             │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                     │                     │          │
│         └─────────────────────┼─────────────────────┘          │
│                               │                                │
│                    COORDINATION LAYER                         │
└───────────────────────────────┼────────────────────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   TRAFFIC       │
                       │   SIMULATION    │
                       │   (SUMO)        │
                       └─────────────────┘
```

## Detailed Process Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  TRAFFIC STATE  │    │   OBSERVATION   │    │    ACTION       │
│   MONITORING    │───►│   PROCESSING    │───►│   SELECTION     │
│                 │    │                 │    │                 │
│ • Queue lengths │    │ • State vector  │    │ • Phase switch  │
│ • Vehicle speeds│    │ • Normalization │    │ • Safety checks │
│ • Waiting times │    │ • Neighbor info │    │ • Constraints   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       │
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │ REINFORCEMENT   │              │
         │              │   LEARNING      │              │
         │              │                 │              │
         │              │ • Policy Update │              │
         │              │ • Reward Calc   │              │
         │              │ • Experience    │              │
         │              │   Replay        │              │
         └──────────────┼─────────────────┼──────────────┘
                        │                 ▲
                        │                 │
               ┌─────────────────┐       │
               │   ENVIRONMENT   │       │
               │   SIMULATION    │       │
               │                 │       │
               │ • Traffic flow  │       │
               │ • Signal timing │       │
               │ • Vehicle       │       │
               │   movement      │       │
               └─────────────────┘       │
                        │                │
                        └────────────────┘
```

## Agent Decision Cycle

```
┌─────────────┐
│   STEP T    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ OBSERVE     │     │  STATE S_t  │
│ TRAFFIC     │────►│             │
│ STATE       │     │ • Queues    │
│             │     │ • Phases    │
│ • Sensors   │     │ • Neighbors │
│ • Cameras   │     │ • History   │
└─────────────┘     └─────────────┘
       │                    │
       │                    ▼
       │           ┌─────────────┐
       │           │   POLICY    │
       │           │ π_θ(A|S)   │
       │           │            │
       │           │ • DQN      │
       │           │ • PPO      │
       └───────────┼─────────────┘
                   │
                   ▼
          ┌─────────────┐
          │   ACTION    │
          │    A_t      │
          │            │
          │ • Phase     │
          │   switch    │
          │ • Timing    │
          │   adjust    │
          └─────────────┘
                   │
                   ▼
          ┌─────────────┐
          │ EXECUTE IN  │
          │ SIMULATION  │
          │            │
          │ • SUMO      │
          │ • Traffic   │
          │   dynamics  │
          └─────────────┘
                   │
                   ▼
          ┌─────────────┐     ┌─────────────┐
          │  NEXT       │     │   REWARD    │
          │  STATE      │────►│   R_t       │
          │  S_{t+1}    │     │             │
          │             │     │ • Delay     │
          │ • Updated   │     │ • Throughput│
          │   queues    │     │ • Queue len │
          └─────────────┘     └─────────────┘
                   │                    │
                   └────────────────────┘
                            │
                            ▼
                   ┌─────────────┐
                   │   LEARN     │
                   │             │
                   │ • Update θ  │
                   │ • Experience│
                   │   replay    │
                   │ • Gradient  │
                   │   descent   │
                   └─────────────┘
                            │
                            ▼
                   ┌─────────────┐
                   │   STEP      │
                   │  T + 1     │
                   └─────────────┘
```

## Multi-Agent Coordination

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  AGENT i    │    │  AGENT j    │    │  AGENT k    │
│             │    │             │    │             │
│ • Local obs │    │ • Local obs │    │ • Local obs │
│ • Neighbor  │    │ • Neighbor  │    │ • Neighbor  │
│   messages  │    │   messages  │    │   messages  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       │◄────────────────►│◄────────────────►│
       │    LIMITED       │    LIMITED       │
       │  COMMUNICATION   │  COMMUNICATION   │
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ COORDINATED │    │ COORDINATED │    │ COORDINATED │
│   ACTIONS   │    │   ACTIONS   │    │   ACTIONS   │
│             │    │             │    │             │
│ • Phase sync│    │ • Phase sync│    │ • Phase sync│
│ • Flow      │    │ • Flow      │    │ • Flow      │
│   balance   │    │   balance   │    │   balance   │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Key Components Summary

### Traffic Environment Layer
- **Network Model**: Graph G=(V,E) with intersections and roads
- **Simulation Engine**: SUMO microscopic traffic simulator
- **State Observations**: Real-time traffic metrics and signal states

### Learning & Decision Layer
- **RL Algorithms**: DQN, PPO, and other policy optimization methods
- **State Representation**: Compact features capturing local and neighbor conditions
- **Action Space**: Phase switching decisions with safety constraints
- **Reward Design**: Multi-objective function balancing efficiency metrics

### Coordination Layer
- **Communication Protocol**: Limited neighbor information exchange
- **Scalability**: Decentralized execution with optional centralized training
- **Safety**: Rule-based constraints ensuring traffic safety standards

This process enables adaptive, intelligent traffic signal control that learns optimal policies through interaction with realistic traffic environments.
