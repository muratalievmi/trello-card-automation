# Meta-Game Framework: Research & Pattern Analysis

## Part 1: Platform Analysis

### Studied Systems

| Platform | Type | Entity Model | Rule System | Emergence Mechanism |
|----------|------|-------------|-------------|---------------------|
| **Roblox** | 3D sandbox platform | Instance tree (Part, Model, Script) | Luau scripts + physics engine | Composable instances + sandboxed VM |
| **The Sandbox** | Blockchain game builder | NFT assets + Logic Assets | No-code visual scripting + message passing | Component-based behaviours |
| **RPG Maker** | 2D RPG engine | Database entries (Actor, Item, Event) | Switches/Variables + Event Pages (state machine) | Plugin system + formula-driven combat |
| **GameMaker Studio** | 2D game engine | Object-Instance pattern | GML code + event-driven loop | Parent-child inheritance + FSMs |
| **Minecraft** | 3D voxel sandbox | Blocks + Entities (NBT data) | Redstone (Turing-complete) + Commands + Gamerules | Layered complexity: physical → scripted |
| **Hearthstone** | Card game | Cards (stats + effect trees) | Trigger/event system + composite spell pattern | Combinatorial deck space |
| **MTG Arena** | Card game | Cards (typed by Comprehensive Rules) | GRE engine + CLIPS rules + Layer system | Turing-complete rule interactions |
| **Slay the Spire** | Deckbuilder roguelike | Cards + Relics + Potions | Action queue + Power hooks | Relic-card synergy explosion |
| **SC2 Editor** | RTS map editor | Units/Abilities in Data Catalogs | Trigger (Event/Condition/Action) + Galaxy language | Data inheritance + community iteration |
| **WC3 World Editor** | RTS map editor | Object Editor entities | GUI Triggers + JASS scripting | Dummy unit pattern → DotA/MOBA genre |
| **Tabletop Simulator** | Physics sandbox | Physical objects + Lua scripts | Social enforcement OR scripted rules | Sandbox physics + Workshop ecosystem |
| **Board Game Arena** | Web board game platform | SQL rows (key/location/state) | PHP state machine + notifications | Server-authoritative FSM |

---

## Part 2: Cross-Domain Patterns (Extrapolation Method)

### Pattern 1: The Entity-Composition Primitive

**Observation across domains:**
- Physics: elementary particles compose into atoms, molecules, materials
- Language models: tokens compose into words, sentences, meanings
- Biology: cells compose into tissues, organs, organisms
- All studied platforms: simple entities compose into complex game objects

**Extrapolated principle:** Every generative system is built on a vocabulary of atomic primitives that compose through well-defined operations. The power of the system is determined by the expressiveness of its composition operations, not by the complexity of its primitives.

**Application to meta-game:** Define a minimal set of game primitives (Entity, Property, Rule, Goal) that compose through typed operations (attach, trigger, constrain, sequence).

---

### Pattern 2: The Constraint-Creativity Duality

**Observation across domains:**
- Physics: conservation laws constrain motion but enable stable structures
- Language: grammar rules constrain word order but enable infinite sentences
- WC3 Editor: limitations forced the dummy unit pattern, which enabled DotA
- Roblox: sandboxed VM constrains code but enables safe UGC

**Extrapolated principle:** Constraints do not reduce creative possibility — they redirect it. A well-chosen constraint set channels exploration toward productive regions of the possibility space.

**Application to meta-game:** The framework must impose structural constraints (type compatibility, balance bounds, coherence rules) that guide game generation toward playable, interesting designs.

---

### Pattern 3: The Irreducibility Gap

**Observation across domains:**
- Physics: cannot predict a system's state without simulating it (3-body problem)
- Language: cannot predict a text's meaning without reading it
- Games: cannot predict dynamics without playing (MDA gap)
- MTG: proven Turing-complete — win conditions are non-computable

**Extrapolated principle:** The mapping from rules to emergent behavior is computationally irreducible. Any generative system must include a simulation step — generation without evaluation is blind.

**Application to meta-game:** Build a simulation engine that can run generated games with automated agents and evaluate emergent properties.

---

### Pattern 4: The Layered Complexity Gradient

**Observation across domains:**
- Physics: quantum → atomic → molecular → macro → cosmic
- Software: machine code → assembly → high-level → DSL → natural language
- Minecraft: blocks → redstone → commands → data packs → mods
- Roblox: visual placement → constraints → Luau → services → plugins

**Extrapolated principle:** Successful generative systems provide multiple levels of abstraction. Each level hides complexity while exposing control.

**Application to meta-game:** Provide at least 3 layers: visual/declarative (define entities), rule-based (define behaviors), code-level (define custom logic).

---

### Pattern 5: The Feedback Loop Engine

**Observation across domains:**
- Economics: supply-demand equilibrium, boom-bust cycles
- Biology: predator-prey dynamics, homeostasis
- Games: positive feedback (snowballing), negative feedback (rubber-banding)
- Machinations framework: all game dynamics reduce to feedback loop structures

**Extrapolated principle:** Interesting dynamics emerge from the interaction of positive and negative feedback loops. A system with only positive feedback explodes; only negative feedback stagnates; their interaction creates rich behavior.

**Application to meta-game:** Every generated game must be analyzable in terms of its feedback loops. The framework should model and visualize resource flows.

---

### Pattern 6: The Community Amplifier

**Observation across domains:**
- Science: peer review amplifies knowledge quality
- Open source: community contributions amplify capability
- WC3 → DotA: community iteration transformed a mod into a genre
- Roblox: 12.3M developers create content faster than any studio

**Extrapolated principle:** A generative system reaches its potential only when its outputs become inputs for a community of creators. Distribution and sharing mechanisms are as important as creation tools.

**Application to meta-game:** Generated games should be shareable, forkable, and composable with other generated games.

---

### Pattern 7: The Dual Generation Strategy

**Observation across domains:**
- Language: top-down grammar (sentence structure) + bottom-up lexicon (word choice)
- Architecture: top-down floor plan + bottom-up material constraints
- PCG: L-systems (top-down expansion) + WFC (bottom-up constraint satisfaction)

**Extrapolated principle:** Effective generation requires both top-down structure (grammar/rules defining global shape) and bottom-up coherence (constraints ensuring local consistency).

**Application to meta-game:** Use grammars to generate game structure (progression, economy, roles) and constraint satisfaction to fill in details (level layout, balance, encounters).

---

## Part 3: Theoretical Foundation

### The MDA Decomposition

Every game decomposes into:
```
Mechanics  →  Dynamics  →  Aesthetics
(rules)       (behavior)    (experience)
```

The meta-game operates at the Mechanics level: it generates rule sets that produce desired dynamics and aesthetics.

### The ECS Substrate

Games are represented as:
```
Entity    = unique ID
Component = typed data (Position, Health, Inventory, ...)
System    = behavior function over component sets
Game      = {Entities} × {Components} × {Systems} × {Rules}
```

### The Category of Games

Games form a category where:
- Objects = valid game configurations
- Morphisms = game transformations (add mechanic, change rule, modify parameter)
- Composition = sequential application of transformations
- Identity = no-change transformation

### The Three Theorems

1. **Composability**: Game mechanics must be typed morphisms. Only type-compatible mechanics compose.
2. **Irreducibility**: Mechanics→Dynamics mapping requires simulation. No shortcut exists.
3. **Dual Generation**: Both top-down (structure) and bottom-up (coherence) generation are required.

---

## Part 4: Sources & References

### Platforms
- Roblox: create.roblox.com/docs, luau.org
- The Sandbox: docs.sandbox.game
- RPG Maker: rpgmakerweb.com, rpgm.fandom.com
- GameMaker: manual.gamemaker.io
- Minecraft: minecraft.fandom.com

### Academic
- Hunicke, LeBlanc & Zubek — MDA Framework (AAAI 2004)
- Ghani, Hedges et al. — Compositional Game Theory (LiCS 2018)
- Togelius et al. — Search-Based PCG Taxonomy (IEEE 2011)
- Dormans — Machinations / Engineering Emergence (2012)
- Bjork & Holopainen — Patterns in Game Design (2004)
- Salen & Zimmerman — Rules of Play (MIT Press 2004)

### Systems
- Michael Cook — ANGELINA (game-generating AI)
- ECS Architecture — github.com/SanderMertens/ecs-faq
- Wave Function Collapse — github.com/mxgmn/WaveFunctionCollapse
