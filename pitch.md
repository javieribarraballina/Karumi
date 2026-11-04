# Atlas: 3-Minute Hackathon Defense Script
**Karumi × Comillas Hackathon at ICAI — Track 1: How does it learn to find its way around the app?**  
**Total Allocated Time:** 3 minutes (180 seconds)  
**Team Members:** Javier, Juan, Blanca, Nacho, Andrés  

---

## ⏱️ Speaker & Timeline Overview

| Time Window | Speaker | Section & Topic | Deliverable / Focus |
|---|---|---|---|
| **0:00 – 0:35 (35s)** | **Javier (Lead)** | **1. What We Built & The Problem** | Architecture, zero-training problem, graph model |
| **0:35 – 1:10 (35s)** | **Juan (Explorer) & Nacho (Frontend)** | **Live Demo Walkthrough** | Live UI click, crawl to screen graph, "Where am I?", path finding |
| **1:10 – 1:55 (45s)** | **Andrés (Eval & Deploy)** | **2. What It Proves (Real Data & Benchmark)** | Benchmark scorecard from `results.md`, 80.8% coverage, 92.1% top-1 locate, <$0.01 cost |
| **1:55 – 2:30 (35s)** | **Blanca (Screen Identifier)** | **3. Weakest Part & Failure Modes** | Brutal honesty: SPAs, login gates, template visual collisions |
| **2:30 – 3:00 (30s)** | **Javier & Team** | **4. What We’d Add With One More Week** | Fine-tuned lightweight classifier, auth session capture, live drift detection |

---

## 🎤 Word-for-Word Speaking Script

### Part 1: What We Built (0:00 – 0:35) — 35 seconds
**Speaker: Javier (Lead)**
> "Good afternoon. When an AI sales agent arrives at an enterprise SaaS platform it has never seen before, it usually has zero training data, no DOM sitemap, and only seconds before a prospect leaves.
> 
> We built **Atlas**: an autonomous exploration and screen-mapping engine. 
> 
> You give Atlas a single target URL. With **zero pre-training**, it crawls the application, clusters distinct visual states into deduplicated screen nodes, and maps every interaction as a directed transition graph. It answers the two core questions every sales agent needs: *'Where am I right now?'* and *'How do I click through to show feature X?'*"

---

### Part 2: Clickable Live Demo (0:35 – 1:10) — 35 seconds
**Speakers: Juan (Explorer) & Nacho (Frontend)**

*(Nacho opens the browser interface and switches to the live Cytoscape graph)*

**Juan (0:35 – 0:50):**
> "Under the hood, my crawler dispatches headless Playwright sessions to discover interactive elements and page states, passing raw screenshots and transition edges directly to our deduplication engine without manual selectors."

**Nacho (0:50 – 1:10):**
> "As you can see right here on our live web UI, the entire application has been transformed into a clickable graph. 
> 
> If we upload a fresh screenshot into the *'Where am I?'* tool—*(clicks upload)*—Atlas matches it instantly. 
> 
> And if the user asks: *'Take me to checkout'*, Atlas computes the deterministic click-by-click shortest path across the graph. No hallucinated clicks, no broken steps."

---

### Part 3: What It Proves (1:10 – 1:55) — 45 seconds
**Speaker: Andrés (Eval & Pitch Lead)**
> "Judges score on evidence, not intuition. Here are our hard benchmark numbers evaluated across multiple real-world target sites from `eval/results.md`:
> 
> 1. **80.8% Screen Discovery Coverage:** Within an average of 11.8 seconds of autonomous exploration, Atlas uncovered over 80% of ground-truth app screens.
> 2. **92.1% Top-1 Screen Recognition:** On fresh screenshots taken under different viewports and scroll states, our hybrid pipeline achieved **92.1% Top-1 accuracy** and **100% Top-3 accuracy**.
> 3. **100% Path Replay Success:** Every planned path traversed valid, replayable click sequences to the target destination.
> 4. **Production Viability:** The entire mapping process averaged **$0.007 per site** using structured caching and Claude Haiku, proving this is cost-effective to deploy at scale for every inbound lead."

---

### Part 4: Weakest Part (1:55 – 2:30) — 35 seconds
**Speaker: Blanca (Screen Identifier)**
> "Judges reward knowing your limits. Here is where Atlas currently struggles:
> 
> First, **heavy Single Page Applications (SPAs)** where interactive modals or tabs change internal state without updating the URL or causing full DOM reloads. Perceptual hashing handles part of this, but deep state mutations require client-side DOM mutation tracking.
> 
> Second, **auth-gated screens**: an autonomous agent cannot map what it cannot access without pre-configured session cookies or credential vaults.
> 
> Third, **visually identical templates**: in e-commerce, 50 product pages share identical layouts; our union-find clusters them into one 'Product Detail' screen, but edge transitions require semantic disambiguation."

---

### Part 5: One More Week & Conclusion (2:30 – 3:00) — 30 seconds
**Speaker: Javier (Closing with whole team)**
> "With one more week, we would implement three high-impact additions:
> 
> 1. **A lightweight, fine-tuned 100M vision model** to replace the LLM fallback for sub-50ms screen classification at zero incremental API cost.
> 2. **Session & Auth Injection** to allow the crawler to map authenticated enterprise portals safely.
> 3. **Dynamic Graph Drift Detection**: when an app deploys a new UI update, Atlas incrementally updates only the changed edges without re-crawling the entire application.
> 
> Atlas proves that an AI agent doesn't need prior training to master a software platform—it just needs the right map. Thank you, and we're ready for your questions!"

---

## 🛡️ Judge Q&A Defense Cheat Sheet (Team Backup)

- **Q: How do you prevent infinite loops during crawling?**  
  *Juan:* We maintain a visited URL set with normalized slugs and a strict traversal depth and timeout budget (default 90s, 15 pages max).
- **Q: Why combine perceptual hash with LLM vision?**  
  *Blanca:* pHash executes in <1ms and solves 85% of exact/near-exact screens for free. The vision LLM is only invoked as a fallback when hash distance is ambiguous.
- **Q: How does this help Karumi specifically?**  
  *Andrés:* Instead of human sales engineers spending 2 weeks scripting demos for each new SaaS customer, Karumi's agent can drop onto any customer app URL and immediately know how to demo every key feature.
