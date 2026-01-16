"use client";

import { useEffect, useState } from "react";

const GREETINGS = [
  "What would you like to research today?",
  "Ready to dive into market insights?",
  "What financial questions can I help with?",
  "Let's explore the markets together",
  "What investment topics interest you?",
  "Ready to analyze some data?",
  "How can I assist your research today?",
  "What would you like to know about finance?",
];

const EXAMPLE_PROMPTS = [
  "Compare Tesla and Ford stock performance",
  "Analyze Apple's latest earnings report",
  "Should I invest in renewable energy stocks?",
  "What's driving tech stock volatility?",
  "How do Fed interest rates affect inflation?",
  "Explain the impact of AI on the stock market",
];

export default function ChatEmptyState() {
  const [greeting, setGreeting] = useState("What would you like to research today?");
  const [examplePrompt, setExamplePrompt] = useState("Compare Tesla and Ford stock performance");

  useEffect(() => {
    // Set random values only on client side to avoid hydration mismatch
    setGreeting(GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);
    setExamplePrompt(EXAMPLE_PROMPTS[Math.floor(Math.random() * EXAMPLE_PROMPTS.length)]);
  }, []);

  return (
    <div className="empty-state">
      <h1>{greeting}</h1>
      <p className="empty-state-prompt">
        Try: "{examplePrompt}"
      </p>
    </div>
  );
}
