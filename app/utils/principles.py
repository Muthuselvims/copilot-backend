from __future__ import annotations

MAS_PRINCIPLES = {
    "modularity_encapsulation": "Agents are self-contained; expose comms interfaces; hide internals.",
    "autonomy": "Agents act independently using local knowledge; avoid central control.",
    "communication_protocols": "Use message passing and pub-sub; support FIPA ACL.",
    "coordination_cooperation": "Support negotiation, task allocation, conflict resolution.",
    "scalability": "Decentralized architecture; avoid bottlenecks; horizontal growth.",
    "adaptability_learning": "Agents adapt and learn from environment/peers.",
    "robustness_fault_tolerance": "Recover from failures; retries; fallbacks; DLQ.",
    "security_privacy": "Secure channels; data minimization; access control; auth/trust.",
    "environment_awareness": "Perceive data feeds/sensors; maintain context.",
    "goal_oriented": "Clear objectives; planning/utility-based decisions.",
}


