// The consulting packages, smallest first. Each has a fixed scope so the work
// stays contained. Edit the wording here; the page and the form's service list
// both read from this file.
module.exports = {
  calendly: "https://calendly.com/jdcarlston/preliminary-consult",
  offers: [
    {
      id: "architectural-consultation",
      name: "Architectural Consultation",
      step: "Start here",
      format: "One 2-hour working session · written recommendations within a week",
      summary:
        "Bring one hard question: a design you're unsure of, a decision your team keeps reopening, a system that won't hold. We work it through together, using quality attribute scenarios to name what the system actually has to be good at.",
      deliverables: [
        "A focused working session with you and up to four of your people",
        "Written recommendations, with the trade-offs behind each one",
        "The open questions worth answering next",
      ],
      goodFor: "A first look at a problem, or a second opinion before a big call.",
    },
    {
      id: "tech-radar-review",
      name: "Tech Radar Review",
      step: "Get your bearings",
      format: "1 week · two working sessions",
      summary:
        "Map the tools, platforms, frameworks, practices and languages your teams use onto a tech radar, then decide together what to adopt, trial, assess or hold. It focuses and constrains choices so teams stop relitigating them.",
      deliverables: [
        "Your current-state radar, built with your engineers",
        "Adopt, trial, assess and hold calls, each with its reasoning",
        "A short guide for keeping the radar current",
      ],
      goodFor: "Teams with tool sprawl, or a new leader getting oriented.",
    },
    {
      id: "ai-efficiency-review",
      name: "AI Efficiency Review",
      step: "Use AI where it helps",
      format: "2 weeks · interviews, workflow review and a readout",
      summary:
        "Find where AI tools actually speed your teams up and where they quietly add rework. Built on what I learned helping develop Stack Overflow's AI productivity program, including an MCP server and AI hackathons. Humans stay in the loop by design.",
      deliverables: [
        "A map of your delivery workflow, with where AI fits and where it doesn't",
        "Guardrails for quality, security and review",
        "A short list of experiments, each with how you'll know it worked",
      ],
      goodFor: "Leaders paying for AI tools and unsure what they're getting back.",
    },
    {
      id: "domain-boundary-splits",
      name: "Domain Boundary Splits",
      step: "Decide where things belong",
      format: "2-day facilitated session · written boundary decisions",
      summary:
        "EventStorming shows you the domain. Deciding where the boundaries go is the step teams get stuck on. I facilitate it with the Domain Boundary Decision Model I presented at Explore DDD: every boundary serves a promise to someone outside it, every boundary says how sure you are, and every boundary names what would prove it wrong.",
      deliverables: [
        "A facilitated EventStorm with your engineers and subject-matter experts",
        "Boundary decisions marked firm, provisional or not yet",
        "Tripwires: the signals that tell you a boundary needs to move",
      ],
      goodFor: "Splitting a monolith, reorganizing teams, or untangling ownership.",
    },
    {
      id: "legacy-migration-plan",
      name: "Legacy Migration Plan",
      step: "Move without breaking things",
      format: "3–4 weeks · discovery, target architecture and roadmap",
      summary:
        "A plan for getting from the system you have to the one you need, in steps your teams can actually take. I've led this kind of work through a six-month platform redesign onto microservices and microfrontends, delivered on schedule, and through post-merger integrations.",
      deliverables: [
        "A map of the current system and where it hurts",
        "A target architecture sized to your team",
        "A sequenced roadmap with checkpoints and the risks to watch",
      ],
      goodFor: "Aging platforms, mergers, and rewrites that keep stalling.",
    },
  ],
};
