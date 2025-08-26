# Known Limitations and Future Work

## Current Implementation Limitations

### 1. Modeling Assumptions
- **No transportation times**: Jobs assumed to be immediately available at next station
- **No machine failures**: 100% availability assumed for all workstations  
- **Fixed routing**: No dynamic re-routing based on machine availability
- **Deterministic structure**: While processing times are stochastic, product structures are known

### 2. Scope Boundaries
- **Scale**: Tested with up to 70 orders and 10 workstations
- **Rules**: Limited to 3 pool sequencing and 3 dispatching rules
- **Priority levels**: Simple 3-level priority system (0, 1, 2)
- **Cost model**: Simplified linear cost structure

## Verified Functionality

The following aspects have been tested and verified:

- LUMS-COR order release mechanism  
- PCAW workload calculations  
- Pool sequencing rules (FCFS, EDD, CR)  
- Dispatching rules (FCFS, SPT, PST)  
- Event sequence generation  
- KPI calculations  
- Workload norm enforcement  

## Potential Extensions / Future Development Opportunities
The modular architecture of this framework supports various extensions that future researchers or developers could implement.

### Suggested Enhancements
- **Extended Rule Sets**: Additional pool sequencing and dispatching strategies
- **Uncertainty Modeling**: Integration of machine failures, worker availability, and transportation times
- **Scale Optimization**: Parallel processing for large-scale systems
- **Data Integration**: Interfaces to integrate real-time shop floor data
- **Enhanced Process Plans**: Support for complex disassembly structures with conditional routing, quality-dependent paths, and partial disassembly decisions

