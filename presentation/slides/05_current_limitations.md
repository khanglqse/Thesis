# Slide 5: Current Limitations & Challenges

## Technical Limitations

### 1. Simulation-to-Reality Gap
- **Training in simulation** (SUMO) may not transfer perfectly
- **Sensor noise** and incomplete real-world data
- **Unpredictable human behavior** not fully captured
- **Limited public benchmarks** for realistic validation

### 2. Scalability Constraints
- **Current evaluation**: Small networks (1-3 intersections)
- **Coordination complexity** grows with network size
- **Communication overhead** in large-scale deployment
- **Computational requirements** for training

### 3. Reward Design Sensitivity
- **Performance depends** on reward weights (α, β, γ)
- **May not correlate perfectly** with real efficiency metrics
- **Risk of overfitting** to specific reward terms
- **Multi-objective balancing** challenges

## Implementation Challenges

### 1. Data & Training Requirements
- **Extensive simulation time** needed for training
- **Limited realistic datasets** available
- **Dependency on accurate** microscopic models
- **Validation scope** currently limited

### 2. Deployment Readiness
- **Safety constraints** and fail-safe mechanisms required
- **Integration complexity** with existing systems
- **Real-time performance** requirements
- **Maintenance and monitoring** needs

### 3. Validation Scope
- **Limited traffic scenarios** tested so far
- **Extreme conditions** not fully evaluated (accidents, events)
- **Mixed traffic patterns** need more validation
- **Long-term stability** not proven

## Research Gaps

### 1. Robustness Issues
- **Non-stationary traffic** patterns (daily/weekly changes)
- **Weather and incident** impacts
- **Continual learning** requirements
- **Domain adaptation** challenges

### 2. Interpretability & Safety
- **Black-box nature** of deep RL models
- **Decision explainability** for operators
- **Formal verification** of policies
- **Human oversight** integration

### 3. Practical Deployment
- **Sensor infrastructure** requirements
- **Communication reliability**
- **Cost-benefit analysis**
- **Regulatory approval** processes

## Current Status Assessment

**✅ Completed:**
- Core methodology and algorithms
- Initial experimental validation
- Performance improvements demonstrated
- Framework architecture established

**🚧 In Progress:**
- Extended validation scenarios
- Scalability testing
- Real-world deployment preparation

**❓ Remaining Challenges:**
- Sim-to-real transfer
- Large-scale coordination
- Safety assurance
- Interpretability

---

*Image suggestion: Gap analysis diagram showing current capabilities vs. requirements*
