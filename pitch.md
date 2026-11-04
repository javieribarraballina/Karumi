# Atlas: 3-Minute Hackathon Defense Script
**Karumi × Comillas Hackathon (Track 1) | Total Time: 3:00 (180s)**  
**Speakers:** Javier, Juan, Blanca, Nacho, Andrés  

---

### 1. What We Built (0:00 – 0:35)
**Javier (Lead):**  
An AI sales agent landing on an unseen SaaS app has zero prior training, no sitemap, and only seconds before a prospect leaves. We built **Atlas**: an autonomous exploration and screen-mapping engine. Given just a URL, Atlas crawls the application, clusters raw views into deduplicated screens, and maps every interaction as a directed graph. It answers the two core questions every sales agent needs: *Where am I?* and *How do I get to feature X?*

---

### 2. Live Demo (0:35 – 1:10)
**Juan (Explorer):**  
My crawler uses headless Playwright to discover buttons and links, capturing screenshots and transitions without needing predefined CSS selectors or training data.

**Nacho (Frontend):**  
On our web interface, the app is rendered live as an interactive Cytoscape graph. When an agent captures a screen, *Where am I?* identifies the exact node in milliseconds. When asked *Take me to login*, Atlas computes the deterministic shortest path across the graph—click by click, with zero hallucination.

---

### 3. What It Proves (1:10 – 1:55)
**Andrés (Eval & Pitch):**  
Judges score on evidence, not feelings. Here are our measured benchmark numbers from `eval/results.md`:
- **Speed:** Atlas crawls and maps an unseen application in **15 to 17 seconds**.
- **Paths Found:** Graph search resolved valid paths to target destinations on **100% of tested routes**—13 out of 13 on the-internet, and 5 out of 5 on books.
- **Screen Recognition:** On fresh screenshots under a different viewport (1024×768) and scrolled 300 pixels, image perceptual hashing alone achieved **50% Top-1 and 71% Top-3** recognition on the-internet.
- **Deterministic Navigation:** The agent navigates strictly along verified edges, guaranteeing zero invented paths.

---

### 4. Weakest Part (1:55 – 2:30)
**Blanca (Screen Identifier):**  
Judges reward knowing your limits, and we are completely honest about ours:
1. **Template Collisions:** On pages that share a visual layout—like the books site where all product covers look identical—image fingerprints alone get only **17% Top-1** accuracy. This proves visual hashing alone fails on template-heavy sites; the vision LLM fallback is strictly required to disambiguate.
2. **Dynamic SPAs:** State changes without URL updates or DOM transitions are invisible to standard crawlers.
3. **Login Walls:** Authenticated sections cannot be explored without session injection.

---

### 5. One More Week & Close (2:30 – 3:00)
**Javier & Team:**  
With one more week, we would ship:
1. A fine-tuned lightweight vision model replacing the LLM fallback for sub-50ms screen classification.
2. Session cookie injection for enterprise login flows.
3. Dynamic drift detection to update modified edges without re-crawling.

Atlas proves an AI agent doesn't need prior training—it just needs a map. Thank you!
